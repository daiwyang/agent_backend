#!/usr/bin/env python3
"""
根据WDL解析结果生成流程图
"""

import json
import re
from typing import Dict, List, Any

def generate_mermaid_flowchart(json_file: str) -> str:
    """生成Mermaid流程图"""
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    execution_sequence = data.get('execution_structure', {}).get('execution_sequence', [])
    
    if not execution_sequence:
        return "// 未找到execution_sequence数据"
    
    # 生成Mermaid流程图
    mermaid_code = ["graph TD"]
    
    # 节点定义
    for step in execution_sequence:
        step_id = step.get('step_id', 'unknown')
        step_type = step.get('step_type', 'unknown')
        task_name = step.get('task_name', 'unknown')
        execution_order = step.get('execution_order', 0)
        context = step.get('context', {})
        dependencies = step.get('dependencies', [])
        
        # 根据步骤类型设置不同的样式
        if step_type == 'call':
            # 普通调用 - 矩形
            mermaid_code.append(f"    {step_id}[{step_id}<br/>{task_name}]")
        elif step_type == 'conditional_call':
            # 条件调用 - 菱形
            condition = context.get('condition', 'unknown')
            mermaid_code.append(f"    {step_id}{{{step_id}<br/>{task_name}<br/>条件: {condition}}}")
        elif step_type == 'scatter_call':
            # Scatter调用 - 平行四边形
            variable = context.get('variable', 'unknown')
            mermaid_code.append(f"    {step_id}[/{step_id}<br/>{task_name}<br/>scatter: {variable}/]")
    
    # 连接关系
    for step in execution_sequence:
        step_id = step.get('step_id', 'unknown')
        dependencies = step.get('dependencies', [])
        
        # 添加依赖关系
        for dep in dependencies:
            mermaid_code.append(f"    {dep} --> {step_id}")
        
        # 如果没有依赖，连接到前一个步骤（除了第一个）
        if not dependencies and step.get('execution_order', 0) > 1:
            # 找到前一个步骤
            prev_step = None
            for s in execution_sequence:
                if s.get('execution_order', 0) == step.get('execution_order', 0) - 1:
                    prev_step = s
                    break
            
            if prev_step:
                prev_id = prev_step.get('step_id', 'unknown')
                mermaid_code.append(f"    {prev_id} --> {step_id}")
    
    return "\n".join(mermaid_code)

def generate_detailed_flowchart(json_file: str) -> str:
    """生成详细的流程图，包含更多信息"""
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    execution_sequence = data.get('execution_structure', {}).get('execution_sequence', [])
    
    if not execution_sequence:
        return "// 未找到execution_sequence数据"
    
    # 生成Mermaid流程图
    mermaid_code = ["graph TD"]
    
    # 添加样式定义
    mermaid_code.extend([
        "    %% 样式定义",
        "    classDef workflowNode fill:#e1f5fe,stroke:#01579b,stroke-width:2px",
        "    classDef conditionalNode fill:#fff3e0,stroke:#e65100,stroke-width:2px",
        "    classDef scatterNode fill:#f3e5f5,stroke:#4a148c,stroke-width:2px",
        "    classDef dependencyEdge stroke:#ff5722,stroke-width:2px",
        "    classDef sequenceEdge stroke:#4caf50,stroke-width:1px"
    ])
    
    # 节点定义
    for step in execution_sequence:
        step_id = step.get('step_id', 'unknown')
        step_type = step.get('step_type', 'unknown')
        task_name = step.get('task_name', 'unknown')
        execution_order = step.get('execution_order', 0)
        context = step.get('context', {})
        dependencies = step.get('dependencies', [])
        
        # 根据步骤类型设置不同的样式
        if step_type == 'call':
            # 普通调用
            mermaid_code.append(f"    {step_id}[步骤{execution_order}: {step_id}<br/>{task_name}]")
            mermaid_code.append(f"    class {step_id} workflowNode")
        elif step_type == 'conditional_call':
            # 条件调用
            condition = context.get('condition', 'unknown')
            mermaid_code.append(f"    {step_id}{{步骤{execution_order}: {step_id}<br/>{task_name}<br/>条件: {condition}}}")
            mermaid_code.append(f"    class {step_id} conditionalNode")
        elif step_type == 'scatter_call':
            # Scatter调用
            variable = context.get('variable', 'unknown')
            mermaid_code.append(f"    {step_id}[/步骤{execution_order}: {step_id}<br/>{task_name}<br/>scatter: {variable}/]")
            mermaid_code.append(f"    class {step_id} scatterNode")
    
    # 连接关系
    for step in execution_sequence:
        step_id = step.get('step_id', 'unknown')
        dependencies = step.get('dependencies', [])
        
        # 添加依赖关系
        for dep in dependencies:
            mermaid_code.append(f"    {dep} -.->|依赖| {step_id}")
        
        # 如果没有依赖，连接到前一个步骤（除了第一个）
        if not dependencies and step.get('execution_order', 0) > 1:
            # 找到前一个步骤
            prev_step = None
            for s in execution_sequence:
                if s.get('execution_order', 0) == step.get('execution_order', 0) - 1:
                    prev_step = s
                    break
            
            if prev_step:
                prev_id = prev_step.get('step_id', 'unknown')
                mermaid_code.append(f"    {prev_id} -->|顺序| {step_id}")
    
    return "\n".join(mermaid_code)

def main():
    """主函数"""
    json_file = "/data/agent_backend/copilot/wdls/SAW-ST-6.1-alpha3-FFPE-early-access.json"

    print("生成基础流程图...")
    basic_flowchart = generate_mermaid_flowchart(json_file)

    print("生成详细流程图...")
    detailed_flowchart = generate_detailed_flowchart(json_file)

    # 保存到文件
    with open("basic_flowchart.mmd", "w", encoding="utf-8") as f:
        f.write(basic_flowchart)

    with open("detailed_flowchart.mmd", "w", encoding="utf-8") as f:
        f.write(detailed_flowchart)

    print("流程图已生成:")
    print("1. basic_flowchart.mmd - 基础流程图")
    print("2. detailed_flowchart.mmd - 详细流程图")

    # 显示基础流程图
    print("\n=== 基础流程图 ===")
    print(basic_flowchart)

    print("\n=== 详细流程图 ===")
    print(detailed_flowchart)

if __name__ == "__main__":
    main() 
