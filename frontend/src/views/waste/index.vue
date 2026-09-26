<template>
  <section class="page" data-module="waste">
    <header class="page-head">
      <div>
        <h2>实验废液管理</h2>
        <p class="page-desc">维护废液记录，围绕废液编号、废液类别、产生环节、暂存容器做登记、筛选与状态流转；可按当前筛选导出移交台账，改完再导入批量补登记。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记废液记录</button>
        <button class="btn" type="button" @click="exportRows">导出移交台账</button>
        <button class="btn" type="button" @click="triggerImport">导入移交台账</button>
        <input ref="fileInput" type="file" accept=".csv" hidden @change="onImportFile" />
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>废液编号</span>
        <input v-model="filters.keyword" placeholder="按废液编号检索" />
      </label>
      <label class="filter-item">
        <span>废液类别</span>
        <input v-model="filters.category" placeholder="按废液类别检索" />
      </label>
      <label class="filter-item">
        <span>废液状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>移交日期起</span>
        <input v-model="filters.date_from" type="date" />
      </label>
      <label class="filter-item">
        <span>移交日期止</span>
        <input v-model="filters.date_to" type="date" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="importResult" class="import-result" :class="{ failed: !importResult.ok }">
      <p class="import-summary">{{ importResult.message }}</p>
      <ul v-if="importResult.skipped.length" class="import-skipped">
        <li v-for="item in importResult.skipped" :key="item.row">第 {{ item.row }} 行：{{ item.reason }}</li>
      </ul>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无实验废液数据，可先登记废液记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条实验废液记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface SkippedRow {
  row: number
  reason: string
}

interface ImportResult {
  ok: boolean
  message: string
  created: number
  updated: number
  skipped: SkippedRow[]
}

const ENDPOINT = '/api/waste'
const columns = ["废液编号", "废液类别", "产生环节", "暂存容器", "产生日期", "移交日期", "处置单位", "废液状态"]
const actions = ["登记移交", "确认处置", "回单归档"]
const statuses = ["暂存中", "待移交", "已移交", "已处置"]
const stats = [{"label": "暂存废液", "value": 0}, {"label": "待移交废液", "value": 0}, {"label": "已处置废液", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const importResult = ref<ImportResult | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const emptyFilters = () => ({ keyword: '', category: '', status: '', date_from: '', date_to: '' })
const filters = reactive(emptyFilters())

function buildQuery(): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  return params.toString()
}

function resetFilters() {
  Object.assign(filters, emptyFilters())
  void reload()
}

function exportRows() {
  const query = buildQuery()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '废液记录登记入口尚未接入审批流'
}

function triggerImport() {
  fileInput.value?.click()
}

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  errorMessage.value = ''
  const form = new FormData()
  form.append('file', file)
  try {
    const response = await request(`${ENDPOINT}/import`, { method: 'POST', body: form })
    const payload = await response.json()
    if (!response.ok) {
      importResult.value = {
        ok: false,
        message: typeof payload?.detail === 'string' ? payload.detail : '导入失败，台账未做任何改动',
        created: 0,
        updated: 0,
        skipped: [],
      }
    } else {
      importResult.value = payload as ImportResult
    }
    await reload()
  } catch (error) {
    importResult.value = {
      ok: false,
      message: error instanceof Error ? error.message : '导入请求失败',
      created: 0,
      updated: 0,
      skipped: [],
    }
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('实验废液动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '实验废液操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = buildQuery()
  try {
    const response = await request(`${ENDPOINT}${query ? `?${query}` : ''}`)
    if (!response.ok) {
      throw new Error('废液记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '实验废液列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.import-result {
  margin-bottom: 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}
.import-result.failed {
  border-color: #b42318;
}
.import-result.failed .import-summary {
  color: #b42318;
}
.import-summary {
  margin: 0;
}
.import-skipped {
  margin: 6px 0 0;
  padding-left: 18px;
  color: var(--muted);
}
</style>
