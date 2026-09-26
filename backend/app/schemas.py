"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ImportSkippedRow(BaseModel):
    """导入时被整行跳过的记录：行号按文件实际行数（表头为第 1 行）。"""

    row: int
    reason: str


class ImportResult(BaseModel):
    """批量导入结果：更新与补登数量、被跳过的行明细。"""

    ok: bool
    message: str
    created: int = 0
    updated: int = 0
    skipped: list[ImportSkippedRow] = Field(default_factory=list)



class SampleEntry(BaseModel):
    """检测样品明细结构。"""

    field_0: str | None = None  # 样品编号
    field_1: str | None = None  # 样品名称
    field_2: str | None = None  # 委托单位
    field_3: str | None = None  # 采样人
    field_4: str | None = None  # 采样日期
    field_5: str | None = None  # 送检日期
    field_6: str | None = None  # 检测类别
    field_7: str | None = None  # 样品状态

class ContractEntry(BaseModel):
    """委托合同明细结构。"""

    field_0: str | None = None  # 合同编号
    field_1: str | None = None  # 委托单位
    field_2: str | None = None  # 检测项目
    field_3: str | None = None  # 合同金额
    field_4: str | None = None  # 签订日期
    field_5: str | None = None  # 约定周期
    field_6: str | None = None  # 联系人
    field_7: str | None = None  # 合同状态

class TaskEntry(BaseModel):
    """检测任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 关联样品
    field_2: str | None = None  # 检测项目
    field_3: str | None = None  # 检测方法
    field_4: str | None = None  # 标准编号
    field_5: str | None = None  # 执行人员
    field_6: str | None = None  # 计划完成日
    field_7: str | None = None  # 任务状态

class MethodEntry(BaseModel):
    """检测方法明细结构。"""

    field_0: str | None = None  # 方法编号
    field_1: str | None = None  # 方法名称
    field_2: str | None = None  # 标准编号
    field_3: str | None = None  # 适用范围
    field_4: str | None = None  # 检出限
    field_5: str | None = None  # 精密度
    field_6: str | None = None  # 版本号
    field_7: str | None = None  # 方法状态

class InstrumentEntry(BaseModel):
    """仪器明细结构。"""

    field_0: str | None = None  # 仪器编号
    field_1: str | None = None  # 仪器名称
    field_2: str | None = None  # 规格型号
    field_3: str | None = None  # 所属实验室
    field_4: str | None = None  # 检定日期
    field_5: str | None = None  # 下次检定日
    field_6: str | None = None  # 保管人
    field_7: str | None = None  # 仪器状态

class StandardEntry(BaseModel):
    """标准物质明细结构。"""

    field_0: str | None = None  # 标物编号
    field_1: str | None = None  # 标物名称
    field_2: str | None = None  # 证书编号
    field_3: str | None = None  # 浓度范围
    field_4: str | None = None  # 有效期至
    field_5: str | None = None  # 存放条件
    field_6: str | None = None  # 开封日期
    field_7: str | None = None  # 标物状态

class ResultEntry(BaseModel):
    """检测结果明细结构。"""

    field_0: str | None = None  # 结果编号
    field_1: str | None = None  # 关联任务
    field_2: str | None = None  # 检测项目
    field_3: str | None = None  # 检测值
    field_4: str | None = None  # 检出限
    field_5: str | None = None  # 评价标准
    field_6: str | None = None  # 判定结论
    field_7: str | None = None  # 结果状态

class ReportEntry(BaseModel):
    """检测报告明细结构。"""

    field_0: str | None = None  # 报告编号
    field_1: str | None = None  # 关联任务
    field_2: str | None = None  # 编制人
    field_3: str | None = None  # 审核人
    field_4: str | None = None  # 签发人
    field_5: str | None = None  # 报告日期
    field_6: str | None = None  # 报告类型
    field_7: str | None = None  # 报告状态

class BoundaryEntry(BaseModel):
    """分包记录明细结构。"""

    field_0: str | None = None  # 分包编号
    field_1: str | None = None  # 分包原因
    field_2: str | None = None  # 分包方名称
    field_3: str | None = None  # 资质编号
    field_4: str | None = None  # 分包项目
    field_5: str | None = None  # 送样日期
    field_6: str | None = None  # 回样日期
    field_7: str | None = None  # 分包状态

class AbnormalEntry(BaseModel):
    """不符合项明细结构。"""

    field_0: str | None = None  # 不符合编号
    field_1: str | None = None  # 发现环节
    field_2: str | None = None  # 不符合描述
    field_3: str | None = None  # 严重程度
    field_4: str | None = None  # 原因分析
    field_5: str | None = None  # 纠正措施
    field_6: str | None = None  # 验证人员
    field_7: str | None = None  # 处置状态

class EnvEntry(BaseModel):
    """环境记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 监测区域
    field_2: str | None = None  # 温度值
    field_3: str | None = None  # 湿度值
    field_4: str | None = None  # 压差值
    field_5: str | None = None  # 监测时间
    field_6: str | None = None  # 记录人员
    field_7: str | None = None  # 记录状态

class BlindEntry(BaseModel):
    """盲样明细结构。"""

    field_0: str | None = None  # 盲样编号
    field_1: str | None = None  # 考核人员
    field_2: str | None = None  # 检测项目
    field_3: str | None = None  # 标准值
    field_4: str | None = None  # 实测值
    field_5: str | None = None  # 判定结果
    field_6: str | None = None  # 考核日期
    field_7: str | None = None  # 考核状态

class AbilityEntry(BaseModel):
    """能力验证明细结构。"""

    field_0: str | None = None  # 验证编号
    field_1: str | None = None  # 组织方
    field_2: str | None = None  # 检测项目
    field_3: str | None = None  # 参加人员
    field_4: str | None = None  # 样品编号
    field_5: str | None = None  # 上报日期
    field_6: str | None = None  # 结果评定
    field_7: str | None = None  # 验证状态

class IntermediateEntry(BaseModel):
    """中间液明细结构。"""

    field_0: str | None = None  # 配制编号
    field_1: str | None = None  # 母液编号
    field_2: str | None = None  # 目标浓度
    field_3: str | None = None  # 配制定容
    field_4: str | None = None  # 配制日期
    field_5: str | None = None  # 失效日期
    field_6: str | None = None  # 配制人员
    field_7: str | None = None  # 配制状态

class AuditEntry(BaseModel):
    """内审记录明细结构。"""

    field_0: str | None = None  # 内审编号
    field_1: str | None = None  # 内审日期
    field_2: str | None = None  # 内审部门
    field_3: str | None = None  # 检查条款
    field_4: str | None = None  # 检查结果
    field_5: str | None = None  # 不符合项
    field_6: str | None = None  # 整改期限
    field_7: str | None = None  # 内审状态

class CertificationEntry(BaseModel):
    """资质认定明细结构。"""

    field_0: str | None = None  # 认定编号
    field_1: str | None = None  # 认定类型
    field_2: str | None = None  # 发证机构
    field_3: str | None = None  # 认定范围
    field_4: str | None = None  # 获证日期
    field_5: str | None = None  # 有效期至
    field_6: str | None = None  # 证书编号
    field_7: str | None = None  # 认定状态

class QualityEntry(BaseModel):
    """质控样明细结构。"""

    field_0: str | None = None  # 质控样编号
    field_1: str | None = None  # 参数名称
    field_2: str | None = None  # 标准值
    field_3: str | None = None  # 不确定度
    field_4: str | None = None  # 检验周期
    field_5: str | None = None  # 批量编号
    field_6: str | None = None  # 进库日期
    field_7: str | None = None  # 质控状态

class Reagent2Entry(BaseModel):
    """试剂明细结构。"""

    field_0: str | None = None  # 试剂编号
    field_1: str | None = None  # 试剂名称
    field_2: str | None = None  # 规格等级
    field_3: str | None = None  # 存放方位
    field_4: str | None = None  # 有效期至
    field_5: str | None = None  # 瓶数余量
    field_6: str | None = None  # 领用记录
    field_7: str | None = None  # 试剂状态

class WasteEntry(BaseModel):
    """废液记录明细结构。"""

    field_0: str | None = None  # 废液编号
    field_1: str | None = None  # 废液类别
    field_2: str | None = None  # 产生环节
    field_3: str | None = None  # 暂存容器
    field_4: str | None = None  # 产生日期
    field_5: str | None = None  # 移交日期
    field_6: str | None = None  # 处置单位
    field_7: str | None = None  # 废液状态

class OpinionEntry(BaseModel):
    """反馈记录明细结构。"""

    field_0: str | None = None  # 反馈编号
    field_1: str | None = None  # 委托单位
    field_2: str | None = None  # 反馈类型
    field_3: str | None = None  # 反馈内容
    field_4: str | None = None  # 处理人员
    field_5: str | None = None  # 处理结果
    field_6: str | None = None  # 反馈日期
    field_7: str | None = None  # 反馈状态
