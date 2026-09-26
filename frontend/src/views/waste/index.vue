<template>
  <section class="page" data-module="waste">
    <header class="page-head">
      <div>
        <h2>实验废液管理</h2>
        <p class="page-desc">维护废液记录，围绕废液编号、废液类别、产生环节、暂存容器做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记废液记录</button>
        <button class="btn" type="button" @click="exportRows">导出实验废液清单</button>
        <button class="btn" type="button" @click="triggerImport">导入移交台账</button>
        <input
          ref="importInput"
          type="file"
          accept=".csv,text/csv"
          class="hidden-file"
          @change="handleImportFile"
        />
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input
          v-model="filters[field.key]"
          :type="field.type"
          :placeholder="field.type === 'text' ? `按${field.label}检索` : ''"
        />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="importResult" class="import-result">
      <div class="import-result-head">
        <strong>导入结果</strong>
        <button class="link" type="button" @click="importResult = null">关闭</button>
      </div>
      <p>
        共扫描 {{ importResult.scanned }} 行：按编号对上账并更新移交日期、处置单位
        {{ importResult.updated }} 条，补登为暂存中 {{ importResult.created }} 条，整行跳过
        {{ importResult.skipped.length }} 条。
      </p>
      <ul v-if="importResult.skipped.length" class="skip-list">
        <li v-for="item in importResult.skipped" :key="item.line">
          第 {{ item.line }} 行：{{ item.reason }}
        </li>
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
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface SkippedRow {
  line: number
  reason: string
}

interface ImportResult {
  scanned: number
  updated: number
  created: number
  skipped: SkippedRow[]
}

interface FilterField {
  key: string
  label: string
  type: 'text' | 'date'
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
const importInput = ref<HTMLInputElement | null>(null)
// 筛选字段的 key 与后端查询参数一一对应：导出时原样带走同一套条件。
const filterFields: FilterField[] = [
  { key: 'keyword', label: '废液编号', type: 'text' },
  { key: 'category', label: '废液类别', type: 'text' },
  { key: 'transfer_start', label: '移交日期起', type: 'date' },
  { key: 'transfer_end', label: '移交日期止', type: 'date' },
]
const filters = ref<Record<string, string>>({})

function buildQuery() {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters.value[field.key]?.trim()
    if (value) {
      params.set(field.key, value)
    }
  }
  return params.toString()
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  // 导出走当前筛选条件：移交日期区间、废液类别等参数都拼在 URL 上一起带走。
  const query = buildQuery()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function triggerImport() {
  errorMessage.value = ''
  importInput.value?.click()
}

async function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // 选完即清空，同一份文件改完后可以再次选择触发导入。
  input.value = ''
  if (!file) {
    return
  }
  errorMessage.value = ''
  importResult.value = null
  try {
    // 文件按原始 CSV 字节发送，由后端整份解析校验；格式不对时后端不会写入任何数据。
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': 'text/csv; charset=utf-8' },
    })
    if (!response.ok) {
      let detail = ''
      try {
        detail = String((await response.json())?.detail ?? '')
      } catch {
        detail = ''
      }
      throw new Error(detail || `导入失败（HTTP ${response.status}），台账未做任何改动`)
    }
    importResult.value = (await response.json()) as ImportResult
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '实验废液台账导入失败'
  }
}

function openCreate() {
  errorMessage.value = '废液记录登记入口尚未接入审批流'
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
.hidden-file {
  display: none;
}
.import-result {
  background: #fff;
  border: 1px solid var(--border);
  border-left: 4px solid var(--brand);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.import-result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.import-result p {
  margin: 4px 0;
}
.skip-list {
  margin: 6px 0 0;
  padding-left: 18px;
  color: var(--muted);
}
</style>
