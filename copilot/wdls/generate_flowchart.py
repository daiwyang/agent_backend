#!/usr/bin/env python3
"""
WDL工作流程图生成器
基于WDL JSON Schema生成Mermaid流程图
"""

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class WDLFlowchartGenerator:
    """WDL工作流程图生成器"""

    def __init__(self, json_file: str):
        """初始化流程图生成器"""
        self.json_file = json_file
        self.data = self._load_json()
        self.workflow_inputs = self._get_workflow_inputs()
        self.workflow_outputs = self._get_workflow_outputs()
        self.variable_definitions = self._get_variable_definitions()
        self.calls = self._get_calls()
        self.tasks = self._get_tasks()

    def _load_json(self) -> Dict[str, Any]:
        """加载JSON数据"""
        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载JSON文件失败: {e}")
            return {}

    def _get_workflow_inputs(self) -> List[Dict[str, Any]]:
        """获取工作流输入参数"""
        return self.data.get("inputs", [])

    def _get_workflow_outputs(self) -> List[Dict[str, Any]]:
        """获取工作流输出参数"""
        return self.data.get("outputs", [])

    def _get_variable_definitions(self) -> Dict[str, Dict[str, Any]]:
        """获取变量定义"""
        return self.data.get("variable_definitions", {})

    def _get_calls(self) -> List[Dict[str, Any]]:
        """获取任务调用"""
        return self.data.get("calls", [])

    def _get_tasks(self) -> List[Dict[str, Any]]:
        """获取任务定义"""
        return self.data.get("tasks", [])

    def _sanitize_node_id(self, node_id: str) -> str:
        """清理节点ID，确保Mermaid兼容"""
        if not node_id:
            return "unknown"
        # 移除或替换特殊字符
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", str(node_id))
        # 确保不以数字开头
        if sanitized and sanitized[0].isdigit():
            sanitized = "node_" + sanitized
        return sanitized

    def _sanitize_text(self, text: Any, max_length: int = 20) -> str:
        """清理并截断文本"""
        if text is None:
            return ""

        text_str = str(text)
        if len(text_str) > max_length:
            text_str = text_str[: max_length - 3] + "..."

        # 移除或替换特殊字符，避免转义问题
        text_str = text_str.replace('"', "'")
        text_str = text_str.replace("[", "")
        text_str = text_str.replace("]", "")
        text_str = text_str.replace("(", "")
        text_str = text_str.replace(")", "")
        text_str = text_str.replace("{", "")
        text_str = text_str.replace("}", "")
        text_str = text_str.replace("<", "lt")
        text_str = text_str.replace(">", "gt")
        text_str = text_str.replace("\\", "")

        return text_str

    def _get_variable_type_color(self, var_type: str) -> str:
        """根据变量类型获取颜色类"""
        if not var_type:
            return "defaultVar"

        base_type = var_type.split("[")[0].lower()
        type_colors = {"int": "intVar", "float": "floatVar", "string": "stringVar", "boolean": "boolVar", "array": "arrayVar", "file": "fileVar"}
        return type_colors.get(base_type, "defaultVar")

    def _is_workflow_input(self, var_name: str) -> bool:
        """检查是否为工作流输入参数"""
        return any(inp.get("name") == var_name for inp in self.workflow_inputs)

    def _generate_mermaid_styles(self) -> List[str]:
        """生成Mermaid样式定义"""
        return [
            "    %% 节点样式定义",
            "    classDef inputNode fill:#fff9c4,stroke:#f57f17,stroke-width:2px,stroke-dasharray: 5 3",
            "    classDef outputNode fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px",
            "    classDef callNode fill:#e3f2fd,stroke:#1976d2,stroke-width:2px",
            "    classDef intVar fill:#e8f5e8,stroke:#388e3c,stroke-width:1px",
            "    classDef floatVar fill:#e8f5e8,stroke:#388e3c,stroke-width:1px",
            "    classDef stringVar fill:#e1f5fe,stroke:#0277bd,stroke-width:1px",
            "    classDef boolVar fill:#fff3e0,stroke:#ef6c00,stroke-width:1px",
            "    classDef arrayVar fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1px",
            "    classDef fileVar fill:#fce4ec,stroke:#c2185b,stroke-width:1px",
            "    classDef defaultVar fill:#f5f5f5,stroke:#616161,stroke-width:1px",
        ]

    def _create_input_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建输入节点"""
        nodes = []
        node_ids = set()

        for input_param in self.workflow_inputs:
            input_name = input_param.get("name")
            optional = input_param.get("optional", False)

            if not input_name:
                continue

            node_id = f"input_{input_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(input_name, 20)

            nodes.append(f"    {sanitized_id}[{display_name}]")
            nodes.append(f"    class {sanitized_id} inputNode")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_output_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建输出节点"""
        nodes = []
        node_ids = set()

        for output_param in self.workflow_outputs:
            output_name = output_param.get("name")

            if not output_name:
                continue

            node_id = f"output_{output_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(output_name, 20)

            nodes.append(f"    {sanitized_id}[输出: {display_name}]")
            nodes.append(f"    class {sanitized_id} outputNode")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_variable_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建变量节点"""
        nodes = []
        node_ids = set()

        for var_name, var_def in self.variable_definitions.items():
            var_type = var_def.get("type", "")

            node_id = f"var_{var_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(var_name, 20)

            color_class = self._get_variable_type_color(var_type)

            # 只显示变量名，不显示复杂的表达式
            nodes.append(f"    {sanitized_id}(({display_name}))")
            nodes.append(f"    class {sanitized_id} {color_class}")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_task_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建任务节点"""
        nodes = []
        node_ids = set()

        for call in self.calls:
            call_name = call.get("name")
            task_name = call.get("task")

            if not call_name:
                continue

            node_id = f"task_{call_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(call_name, 20)

            if task_name and task_name != call_name:
                display_task = self._sanitize_text(task_name, 15)
                nodes.append(f"    {sanitized_id}[{display_name}<br/>任务: {display_task}]")
            else:
                nodes.append(f"    {sanitized_id}[{display_name}]")

            nodes.append(f"    class {sanitized_id} callNode")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_edges(self, all_node_ids: Set[str]) -> List[str]:
        """创建边连接"""
        edges = []
        added_edges = set()

        # 1. 变量依赖边
        for var_name, var_def in self.variable_definitions.items():
            var_node_id = self._sanitize_node_id(f"var_{var_name}")
            dependencies = var_def.get("dependencies", [])

            for dep in dependencies:
                # 检查是否为输入参数
                if self._is_workflow_input(dep):
                    dep_node_id = self._sanitize_node_id(f"input_{dep}")
                else:
                    dep_node_id = self._sanitize_node_id(f"var_{dep}")

                if dep_node_id in all_node_ids and var_node_id in all_node_ids:
                    edge = (dep_node_id, var_node_id)
                    if edge not in added_edges:
                        edges.append(f"    {dep_node_id} --> {var_node_id}")
                        added_edges.add(edge)

        # 2. 任务输入边
        for call in self.calls:
            call_name = call.get("name")
            task_inputs = call.get("inputs", {})
            task_node_id = self._sanitize_node_id(f"task_{call_name}")

            for input_name, input_value in task_inputs.items():
                if isinstance(input_value, dict) and "name" in input_value:
                    var_name = input_value["name"]

                    # 检查是否为输入参数
                    if self._is_workflow_input(var_name):
                        src_node_id = self._sanitize_node_id(f"input_{var_name}")
                    else:
                        src_node_id = self._sanitize_node_id(f"var_{var_name}")

                    if src_node_id in all_node_ids and task_node_id in all_node_ids:
                        edge = (src_node_id, task_node_id)
                        if edge not in added_edges:
                            edges.append(f"    {src_node_id} --> {task_node_id}")
                            added_edges.add(edge)

        # 3. 输出边
        for output_param in self.workflow_outputs:
            output_name = output_param.get("name")
            expression = output_param.get("expression", "")
            output_node_id = self._sanitize_node_id(f"output_{output_name}")

            # 查找表达式中的所有任务名
            # 匹配模式：task_name.output_name 或 task_name['output_name']
            task_patterns = [
                r"([a-zA-Z_][a-zA-Z0-9_]*)\.[a-zA-Z_][a-zA-Z0-9_]*",  # task_name.output_name
                r"([a-zA-Z_][a-zA-Z0-9_]*)\['[^']*'\]",  # task_name['output_name']
                r"([a-zA-Z_][a-zA-Z0-9_]*)\[[^]]*\]"  # task_name[output_name]
            ]
            
            found_tasks = set()
            for pattern in task_patterns:
                matches = re.findall(pattern, expression)
                found_tasks.update(matches)
            
            # 为每个找到的任务创建边
            for task_name in found_tasks:
                src_node_id = self._sanitize_node_id(f"task_{task_name}")
                
                if src_node_id in all_node_ids and output_node_id in all_node_ids:
                    edge = (src_node_id, output_node_id)
                    if edge not in added_edges:
                        edges.append(f"    {src_node_id} --> {output_node_id}")
                        added_edges.add(edge)

        # 4. Runtime变量边
        for call in self.calls:
            call_name = call.get("name")
            task_name = call.get("task")
            task_node_id = self._sanitize_node_id(f"task_{call_name}")

            # 查找对应的任务定义以获取runtime信息
            if task_name:
                for task in self.tasks:
                    if task.get("name") == task_name:
                        runtime = task.get("runtime", {})
                        for key, value in runtime.items():
                            if isinstance(value, dict) and "name" in value:
                                var_name = value["name"]
                                if self._is_workflow_input(var_name):
                                    src_node_id = self._sanitize_node_id(f"input_{var_name}")
                                else:
                                    src_node_id = self._sanitize_node_id(f"var_{var_name}")

                                if src_node_id in all_node_ids and task_node_id in all_node_ids:
                                    edge = (src_node_id, task_node_id)
                                    if edge not in added_edges:
                                        edges.append(f"    {src_node_id} --> {task_node_id}")
                                        added_edges.add(edge)
                            elif isinstance(value, dict) and "variables" in value:
                                variables = value.get("variables", [])
                                for var_name in variables:
                                    if self._is_workflow_input(var_name):
                                        src_node_id = self._sanitize_node_id(f"input_{var_name}")
                                    else:
                                        src_node_id = self._sanitize_node_id(f"var_{var_name}")

                                    if src_node_id in all_node_ids and task_node_id in all_node_ids:
                                        edge = (src_node_id, task_node_id)
                                        if edge not in added_edges:
                                            edges.append(f"    {src_node_id} --> {task_node_id}")
                                            added_edges.add(edge)
                        break

        return edges

    def generate_flowchart(self) -> str:
        """生成流程图"""
        if not self.data:
            return "// 数据加载失败"

        mermaid_lines = ["graph TD"]

        # 添加样式
        mermaid_lines.extend(self._generate_mermaid_styles())
        mermaid_lines.append("")

        # 创建节点
        all_node_ids = set()

        # 输入节点
        input_nodes, input_ids = self._create_input_nodes()
        mermaid_lines.extend(input_nodes)
        all_node_ids.update(input_ids)

        # 变量节点
        var_nodes, var_ids = self._create_variable_nodes()
        mermaid_lines.extend(var_nodes)
        all_node_ids.update(var_ids)

        # 任务节点
        task_nodes, task_ids = self._create_task_nodes()
        mermaid_lines.extend(task_nodes)
        all_node_ids.update(task_ids)

        # 输出节点
        output_nodes, output_ids = self._create_output_nodes()
        mermaid_lines.extend(output_nodes)
        all_node_ids.update(output_ids)

        mermaid_lines.append("")

        # 创建边
        edges = self._create_edges(all_node_ids)
        mermaid_lines.extend(edges)

        return "\n".join(mermaid_lines)


def main():
    """主函数"""
    json_file = "docs/wdl/st_pipeline.json"

    generator = WDLFlowchartGenerator(json_file)
    print("生成WDL工作流程图...")

    flowchart = generator.generate_flowchart()

    # 保存到文件
    output_file = "wdl_workflow_flowchart.mmd"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(flowchart)

    print(f"流程图已生成: {output_file}")
    print(f"工作流名称: {generator.data.get('name', 'Unknown')}")
    print(f"输入参数: {len(generator.workflow_inputs)}")
    print(f"输出参数: {len(generator.workflow_outputs)}")
    print(f"变量定义: {len(generator.variable_definitions)}")
    print(f"任务调用: {len(generator.calls)}")


if __name__ == "__main__":
    main()
