# WDL解析JSON Schema文档

## 概述

本文档定义了WDL（Workflow Description Language）工作流解析后的JSON结构规范。该schema描述了工作流的完整结构，包括输入输出、任务调用、执行流程等所有组件。

## 根级别结构

```json
{
  "name": "工作流名称",
  "inputs": [...],
  "outputs": [...],
  "tasks_used": [...],
  "calls": [...],
  "conditionals": [...],
  "scatters": [...],
  "execution_structure": {...},
  "imports": [...],
  "tasks": [...]
}
```

### 根级别节点说明

| 节点 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `name` | string | ✅ | 工作流名称 |
| `inputs` | array | ✅ | 工作流输入参数列表 |
| `outputs` | array | ✅ | 工作流输出参数列表 |
| `tasks_used` | array | ✅ | 工作流中使用的任务名称列表 |
| `calls` | array | ✅ | 工作流中的所有任务调用 |
| `conditionals` | array | ✅ | 条件执行块列表 |
| `scatters` | array | ✅ | 并行执行块列表 |
| `execution_structure` | object | ✅ | 工作流执行结构（核心组件） |
| `imports` | array | ❌ | 导入的WDL文件列表 |
| `tasks` | array | ❌ | 任务定义列表 |

## 详细节点定义

### 1. 工作流输入参数 (WorkflowInput)

```json
{
  "name": "参数名称",
  "type": "参数类型",
  "optional": true/false,
  "default_value": "默认值",
  "help": "帮助信息"
}
```

#### 属性说明

| 属性 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| `name` | string | ✅ | 参数名称 | `"sampleid"` |
| `type` | string | ✅ | 参数类型 | `"String"`, `"File?"`, `"Array[File]"` |
| `optional` | boolean | ✅ | 是否为可选参数 | `true`, `false` |
| `default_value` | string/number/null | ❌ | 默认值 | `"0"`, `null` |
| `help` | string/null | ❌ | 帮助信息 | `"样本ID"`, `null` |

#### 类型示例

```json
{
  "name": "sampleid",
  "type": "String",
  "optional": false,
  "default_value": null,
  "help": null
},
{
  "name": "Micro",
  "type": "Int", 
  "optional": false,
  "default_value": "0",
  "help": null
},
{
  "name": "imageTAR",
  "type": "File?",
  "optional": true,
  "default_value": null,
  "help": null
}
```

### 2. 工作流输出参数 (WorkflowOutput)

```json
{
  "name": "输出名称",
  "type": "输出类型",
  "expression": "输出表达式"
}
```

#### 属性说明

| 属性 | 类型 | 必需 | 描述 | 示例 |
|------|------|------|------|------|
| `name` | string | ✅ | 输出名称 | `"out00_mapping_runStat"` |
| `type` | string | ✅ | 输出类型 | `"Array[File]?"` |
| `expression` | string | ❌ | 输出表达式 | `"BarcodeMappingAndStar.bcStat"` |

#### 示例

```json
{
  "name": "out00_mapping_runStat",
  "type": "Array[File]?",
  "expression": "BarcodeMappingAndStar.bcStat"
},
{
  "name": "out02_count_summary",
  "type": "File?",
  "expression": "if whetherPE then GetExpPE.summary else GetExpSE.summary"
}
```

### 3. 执行上下文 (Context)

```json
{
  "type": "上下文类型",
  "id": "上下文标识符",
  "level": 嵌套层级,
  "condition": "条件表达式",
  "parent": "父级上下文ID",
  "variable": "循环变量",
  "collection": "集合表达式"
}
```

#### 属性说明

| 属性 | 类型 | 必需 | 描述 | 可选值 |
|------|------|------|------|--------|
| `type` | string | ✅ | 上下文类型 | `"workflow"`, `"conditional"`, `"scatter"` |
| `id` | string | ✅ | 上下文标识符 | `"root"`, `"cond_1"`, `"scatter_index"` |
| `level` | integer | ✅ | 嵌套层级 | `0`, `1`, `2` |
| `condition` | string | ❌ | 条件表达式 | `"!whetherPE"`, `"Micro == 1"` |
| `parent` | string | ❌ | 父级上下文ID | `"root"`, `"scatter_index"` |
| `variable` | string | ❌ | 循环变量 | `"index"` |
| `collection` | string | ❌ | 集合表达式 | `"range(jobN)"` |

#### 上下文类型示例

**工作流根级别**
```json
{
  "type": "workflow",
  "id": "root",
  "level": 0
}
```

**条件执行**
```json
{
  "type": "conditional",
  "id": "cond_1",
  "level": 1,
  "condition": "!whetherPE",
  "parent": "root"
}
```

**并行执行**
```json
{
  "type": "scatter",
  "id": "scatter_index",
  "level": 1,
  "variable": "index",
  "collection": "range(jobN)",
  "parent": "root"
}
```

### 4. 输入参数类型 (InputParameter)

输入参数有多种类型，每种类型有不同的属性结构：

#### 4.1 变量引用 (variable)
```json
{
  "type": "variable",
  "name": "变量名"
}
```

#### 4.2 字符串值 (string)
```json
{
  "type": "string",
  "value": "字符串值"
}
```

#### 4.3 数值 (number)
```json
{
  "type": "number",
  "value": "数值"
}
```

#### 4.4 布尔值 (boolean)
```json
{
  "type": "boolean",
  "value": "布尔值"
}
```

#### 4.5 条件表达式 (conditional)
```json
{
  "type": "conditional",
  "expression": "条件表达式",
  "variables": ["变量列表"]
}
```

#### 4.6 函数调用 (function)
```json
{
  "type": "function",
  "name": "函数名",
  "expression": "函数表达式",
  "variables": ["变量列表"]
}
```

#### 输入参数示例

```json
{
  "dockerUrl": {
    "type": "variable",
    "name": "dockerUrl"
  },
  "referenceFile": {
    "type": "string",
    "value": "/jdfssz2/ST_BIGDATA/Stomics/warehouse/prd/ods/STOmics/Reference_Sequencing/spatialRNAreference.json"
  },
  "mismatch": {
    "type": "number",
    "value": "1"
  },
  "rawExp": {
    "type": "conditional",
    "expression": "if whetherPE then GetExpPE.exp else GetExpSE.exp",
    "variables": ["whetherPE"]
  }
}
```

### 5. 任务调用 (Call)

```json
{
  "name": "调用名称",
  "task": "任务名称",
  "context": {...},
  "inputs": {...},
  "outputs": {...},
  "position": 执行位置
}
```

#### 属性说明

| 属性 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `name` | string | ✅ | 调用名称 |
| `task` | string | ✅ | 任务名称 |
| `context` | object | ✅ | 执行上下文 |
| `inputs` | object | ✅ | 输入参数映射 |
| `outputs` | object | ✅ | 输出参数映射 |
| `position` | integer | ✅ | 执行位置（从0开始） |

#### 示例

```json
{
  "name": "RefRead",
  "task": "RefRead",
  "context": {
    "type": "workflow",
    "id": "call_0_RefRead",
    "level": 0
  },
  "inputs": {
    "dockerUrl": {
      "type": "variable",
      "name": "dockerUrl"
    },
    "referenceFile": {
      "type": "string",
      "value": "/path/to/reference.json"
    }
  },
  "outputs": {
    "referenceMap": {
      "name": "referenceMap",
      "type": "Map[String,Array[String]]",
      "expression": "read_json(\"~{referenceFile}\")"
    }
  },
  "position": 0
}
```

### 6. 条件执行块 (Conditional)

```json
{
  "id": "条件块ID",
  "condition": "条件表达式",
  "calls_inside": 内部调用数量,
  "calls": [...]
}
```

#### 属性说明

| 属性 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `id` | string | ✅ | 条件块标识符 |
| `condition` | string | ✅ | 条件表达式 |
| `calls_inside` | integer | ✅ | 条件块内的调用数量 |
| `calls` | array | ✅ | 条件块内的任务调用列表 |

#### 示例

```json
{
  "id": "conditional_1",
  "condition": "!whetherPE",
  "calls_inside": 1,
  "calls": [
    {
      "name": "SplitBarcodeBin",
      "task": "SplitBarcodeBin"
    }
  ]
}
```

### 7. 并行执行块 (Scatter)

```json
{
  "variable": "循环变量名",
  "collection": "集合表达式",
  "calls_inside": 内部调用数量,
  "calls": [...]
}
```

#### 属性说明

| 属性 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `variable` | string | ✅ | 循环变量名 |
| `collection` | string | ✅ | 集合表达式 |
| `calls_inside` | integer | ✅ | 并行块内的调用数量 |
| `calls` | array | ✅ | 并行块内的任务调用列表 |

#### 示例

```json
{
  "variable": "index",
  "collection": "range(jobN)",
  "calls_inside": 2,
  "calls": [
    {
      "name": "BcNumCountSE",
      "task": "BcNumCountSE"
    },
    {
      "name": "BarcodeMappingAndStar",
      "task": "BarcodeMappingAndStar_v2"
    }
  ]
}
```

### 8. 执行结构 (ExecutionStructure)

执行结构是工作流的核心组件，包含四个主要部分：

```json
{
  "workflow_level_calls": [...],
  "conditional_blocks": [...],
  "scatter_blocks": [...],
  "execution_flow": [...]
}
```

#### 8.1 工作流级别调用 (WorkflowLevelCall)

只包含根级别（level 0）的任务调用：

```json
{
  "name": "任务名称",
  "task": "任务类型",
  "context": {...},
  "inputs": {...},
  "outputs": {...},
  "position": 位置
}
```

#### 8.2 条件块 (ConditionalBlock)

详细的条件执行块信息：

```json
{
  "id": "条件块ID",
  "condition": "条件表达式",
  "calls": [...],
  "detailed_calls": [...]
}
```

#### 8.3 并行块 (ScatterBlock)

详细的并行执行块信息：

```json
{
  "variable": "循环变量",
  "collection": "集合表达式",
  "calls_inside": 调用数量,
  "calls": [...],
  "detailed_calls": [...]
}
```

#### 8.4 执行流程 (ExecutionFlowItem)

完整的执行流程，按顺序排列：

```json
{
  "type": "call",
  "name": "任务名称",
  "task": "任务类型",
  "context": {...},
  "conditional": {...},
  "scatter": {...}
}
```

**条件信息**
```json
{
  "conditional": {
    "condition": "条件表达式",
    "level": 嵌套层级,
    "parent": "上级上下文ID"
  }
}
```

**并行信息**
```json
{
  "scatter": {
    "variable": "循环变量",
    "level": 嵌套层级,
    "parent": "上级上下文ID"
  }
}
```

### 9. 导入 (Import)

```json
{
  "uri": "导入文件URI",
  "namespace": "命名空间",
  "doc": "文档说明"
}
```

### 10. 任务定义 (Task)

```json
{
  "name": "任务名称",
  "inputs": [...],
  "outputs": [...],
  "runtime": {...},
  "meta": {...}
}
```

## 关键概念映射

| WDL概念 | JSON节点 | 描述 |
|---------|----------|------|
| **工作流定义** | `name`, `inputs`, `outputs` | 工作流的基本信息 |
| **任务调用** | `calls` | 工作流中的任务执行实例 |
| **条件执行** | `conditionals`, `context.type="conditional"` | WDL中的if语句 |
| **并行执行** | `scatters`, `context.type="scatter"` | WDL中的scatter语句 |
| **执行顺序** | `position`, `execution_flow`数组索引 | 任务的实际执行顺序 |
| **嵌套层级** | `context.level` | 控制结构的嵌套深度 |
| **依赖关系** | `inputs`中的变量引用 | 任务间的数据依赖 |

## 执行流程示例

```json
{
  "execution_flow": [
    {
      "type": "call",
      "name": "RefRead",
      "task": "RefRead",
      "context": {
        "type": "workflow",
        "id": "root",
        "level": 0
      }
    },
    {
      "type": "call",
      "name": "SplitBarcodeBin",
      "task": "SplitBarcodeBin",
      "context": {
        "type": "conditional",
        "id": "cond_1",
        "level": 1,
        "condition": "!whetherPE",
        "parent": "root"
      },
      "conditional": {
        "condition": "!whetherPE",
        "level": 1,
        "parent": "root"
      }
    },
    {
      "type": "call",
      "name": "BarcodeMappingAndStar",
      "task": "BarcodeMappingAndStar_v2",
      "context": {
        "type": "scatter",
        "id": "scatter_index",
        "level": 1,
        "variable": "index",
        "collection": "range(jobN)",
        "parent": "root"
      },
      "scatter": {
        "variable": "index",
        "level": 1,
        "parent": "root"
      }
    }
  ]
}
```

## 使用场景

### 1. 工作流分析
- 分析任务依赖关系
- 识别并行执行机会
- 计算执行时间估算

### 2. 可视化
- 绘制工作流图
- 显示执行路径
- 展示条件分支

### 3. 验证
- 检查工作流完整性
- 验证参数配置
- 发现潜在问题

### 4. 优化
- 识别性能瓶颈
- 优化资源分配
- 改进执行策略

## 注意事项

1. **position字段**：表示任务在工作流中的解析顺序，但不一定等于执行顺序
2. **level字段**：表示嵌套深度，level 0为根级别
3. **context.parent**：指向父级上下文，用于构建层次关系
4. **execution_flow**：按position排序，提供完整的执行视图
5. **workflow_level_calls**：只包含根级别任务，用于快速概览

## 版本信息

- **Schema版本**: 1.0
- **WDL版本**: 支持WDL 1.0及以上
- **更新日期**: 2024年
- **维护者**: WDL解析器开发团队 