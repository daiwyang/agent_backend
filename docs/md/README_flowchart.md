# SAW工作流流程图

## 概述

本目录包含了基于WDL解析结果生成的SAW-ST-6.1-alpha3-FFPE-early-access工作流流程图。

## 文件说明

### 1. 自动生成的流程图
- `basic_flowchart.mmd` - 基础流程图（自动生成）
- `detailed_flowchart.mmd` - 详细流程图（自动生成）

### 2. 手动优化的流程图
- `saw_workflow_flowchart.mmd` - 针对SAW工作流优化的流程图

## 流程图说明

### 节点类型
- **矩形节点** `[任务名]` - 工作流级别的直接调用
- **菱形节点** `{任务名}` - 条件调用（需要满足特定条件）
- **平行四边形节点** `[/任务名/]` - Scatter调用（并行执行）

### 颜色编码
- **蓝色** - 工作流节点（普通任务）
- **橙色** - 条件节点（条件执行）
- **紫色** - Scatter节点（并行执行）
- **绿色** - 最终节点（报告生成）

## 工作流阶段

### 1. 数据预处理阶段
- `RefRead` - 参考基因组读取
- `SplitBarcodeBin` - 条码分箱（条件：!whetherPE）
- `GetFQlist` - 获取文件列表
- `BcNumCountPE/BcNumCountSE` - 条码计数（根据PE/SE模式）

### 2. 核心分析阶段
- `BarcodeMappingAndStar` - 条码映射和比对（scatter并行）
- `GetExpSE/GetExpPE` - 表达量计算（根据PE/SE模式）
- `MergeBarcodeReadsCount` - 合并条码读数

### 3. 空间分析阶段
- `Register_vea` - 空间配准
- `TissueCut_vea` - 组织切割
- `ReadsUnmappedRmHost` - 去宿主序列（scatter并行）
- `MicrobiomeAnalysis` - 微生物分析（条件：Micro == 1）
- `SpatialCluster` - 空间聚类

### 4. 细胞分析阶段
- `CellCut` - 细胞切割（条件：DoCellbin）
- `CellCluster` - 细胞聚类（条件：DoCellbin）

### 5. 质控和报告
- `Saturation` - 饱和度分析
- `Report_v2` - 最终报告

## 执行条件

### 主要条件变量
- `whetherPE` - 是否为双端测序
- `Micro` - 是否进行微生物分析
- `DoCellbin` - 是否进行细胞分析

### 条件分支
- **PE模式**：执行 `BcNumCountPE` 和 `GetExpPE`
- **SE模式**：执行 `SplitBarcodeBin`、`BcNumCountSE` 和 `GetExpSE`
- **微生物分析**：当 `Micro == 1` 时执行
- **细胞分析**：当 `DoCellbin` 为真时执行

## 使用方法

### 1. 在线查看
将 `.mmd` 文件内容复制到 [Mermaid Live Editor](https://mermaid.live/) 中查看

### 2. 本地生成
```bash
# 安装mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# 生成PNG图片
mmdc -i saw_workflow_flowchart.mmd -o saw_workflow_flowchart.png

# 生成SVG图片
mmdc -i saw_workflow_flowchart.mmd -o saw_workflow_flowchart.svg
```

### 3. 重新生成
```bash
# 重新解析WDL并生成流程图
python wdl_parser.py
python generate_flowchart.py
```

## 技术细节

### 依赖关系
- 实线箭头：表示执行顺序
- 虚线箭头：表示数据依赖关系

### 并行执行
- Scatter节点会并行执行多个实例
- 每个实例处理不同的数据子集

### 条件执行
- 条件节点只有在满足条件时才会执行
- 不影响整体执行顺序

## 注意事项

1. 流程图基于WDL解析结果自动生成
2. 实际执行可能因条件分支而有所不同
3. 并行执行的scatter节点在图中显示为单个节点
4. 条件节点的实际执行取决于运行时参数 