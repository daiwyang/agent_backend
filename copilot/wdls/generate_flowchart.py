#!/usr/bin/env python3
"""
WDL工作流程图生成器
基于WDL JSON Schema生成Mermaid流程图
"""

import json
import re
import subprocess
import os
from typing import Any, Dict, List, Optional, Set, Tuple


class WDLFlowchartGenerator:
    """WDL工作流程图生成器"""

    def __init__(self, json_file: str, graph_direction: str = "LR", use_modern_syntax: bool = True):
        """初始化流程图生成器

        Args:
            json_file: WDL JSON文件路径
            graph_direction: 图的布局方向，可选值：
                - "TD": 从上到下（默认）
                - "LR": 从左到右（推荐，连接线更有序）
                - "RL": 从右到左
                - "BT": 从下到上
            use_modern_syntax: 是否使用现代化的flowchart语法和ELK布局引擎
        """
        self.json_file = json_file
        self.graph_direction = graph_direction
        self.use_modern_syntax = use_modern_syntax
        self.data = self._load_json()
        self.workflow_info = self._get_workflow_info()
        self.workflow_inputs = self._get_workflow_inputs()
        self.workflow_outputs = self._get_workflow_outputs()
        self.workflow_nodes = self._get_workflow_nodes()
        self.tasks = self._get_tasks()

    def _load_json(self) -> Dict[str, Any]:
        """加载JSON数据"""
        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载JSON文件失败: {e}")
            return {}

    def _get_workflow_info(self) -> Dict[str, Any]:
        """获取工作流信息"""
        return self.data.get("workflow", {})

    def _get_workflow_inputs(self) -> List[Dict[str, Any]]:
        """获取工作流输入参数"""
        return self.workflow_info.get("inputs", [])

    def _get_workflow_outputs(self) -> List[Dict[str, Any]]:
        """获取工作流输出参数"""
        return self.workflow_info.get("outputs", [])

    def _get_workflow_nodes(self) -> List[Dict[str, Any]]:
        """获取工作流节点"""
        return self.workflow_info.get("body", [])

    def _get_tasks(self) -> List[Dict[str, Any]]:
        """获取任务定义"""
        return self.data.get("tasks", [])

    def _get_call_nodes(self) -> List[Dict[str, Any]]:
        """获取任务调用节点（包括嵌套在conditional和scatter中的）"""
        call_nodes = []

        def extract_calls_from_nodes(nodes):
            """递归提取节点中的call节点"""
            for node in nodes:
                if node.get("node_type") == "call":
                    call_nodes.append(node)
                elif node.get("node_type") in ["conditional", "scatter"]:
                    # 递归处理嵌套的body节点
                    body_nodes = node.get("body", [])
                    extract_calls_from_nodes(body_nodes)

        extract_calls_from_nodes(self.workflow_nodes)
        return call_nodes

    def _get_variable_definitions(self) -> List[Dict[str, Any]]:
        """获取变量定义节点（包括嵌套在conditional和scatter中的）"""
        var_nodes = []

        def extract_vars_from_nodes(nodes):
            """递归提取节点中的变量定义"""
            for node in nodes:
                if node.get("node_type") == "declaration":
                    var_nodes.append(node)
                elif node.get("node_type") in ["conditional", "scatter"]:
                    # 递归处理嵌套的body节点
                    body_nodes = node.get("body", [])
                    extract_vars_from_nodes(body_nodes)

        extract_vars_from_nodes(self.workflow_nodes)
        return var_nodes

    def _get_conditional_nodes(self) -> List[Dict[str, Any]]:
        """获取条件节点"""
        return [node for node in self.workflow_nodes if node.get("node_type") == "conditional"]

    def _get_scatter_nodes(self) -> List[Dict[str, Any]]:
        """获取并行节点"""
        return [node for node in self.workflow_nodes if node.get("node_type") == "scatter"]

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

    def _is_workflow_input(self, var_name: str) -> bool:
        """检查是否为工作流输入参数"""
        return any(inp.get("name") == var_name for inp in self.workflow_inputs)

    def _generate_mermaid_styles(self) -> List[str]:
        """生成Mermaid样式定义"""
        return [
            "    %% 节点样式定义",
            "    classDef inputNode fill:#e0f2f1,stroke:#00695c,stroke-width:2px",
            "    classDef inputNodeOptional fill:#e0f2f1,stroke:#00695c,stroke-width:2px,stroke-dasharray: 5 3",
            "    classDef outputNode fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px",
            "    classDef outputNodeOptional fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,stroke-dasharray: 5 3",
            "    classDef callNode fill:#e3f2fd,stroke:#1976d2,stroke-width:2px",
            "    classDef varNode fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1px",
            "    classDef varNodeOptional fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1px,stroke-dasharray: 5 3",
            "    classDef conditionalNode fill:#ffecb3,stroke:#f57c00,stroke-width:2px",
            "    classDef scatterNode fill:#f8bbd9,stroke:#ad1457,stroke-width:2px",
        ]

    def _create_input_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建输入节点"""
        nodes = []
        node_ids = set()

        for input_param in self.workflow_inputs:
            input_name = input_param.get("name")
            is_optional = input_param.get("optional", False)

            if not input_name:
                continue

            node_id = f"input_{input_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(input_name, 20)

            nodes.append(f'    {sanitized_id}["Input: {display_name}"]')

            # 根据optional属性设置样式
            if is_optional:
                nodes.append(f"    class {sanitized_id} inputNodeOptional")
            else:
                nodes.append(f"    class {sanitized_id} inputNode")

            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_output_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建输出节点"""
        nodes = []
        node_ids = set()

        # 如果输出节点超过5个，则按模式分组合并
        if len(self.workflow_outputs) > 5:
            # 按输出名称的前缀进行分组
            output_groups = {}

            for output in self.workflow_outputs:
                output_name = output.get("name", "")
                if not output_name:
                    continue

                # 提取前缀
                prefix = "outputs"
                if "_" in output_name:
                    prefix = output_name.split("_")[0]

                if prefix not in output_groups:
                    output_groups[prefix] = []
                output_groups[prefix].append(output)

            # 为每个分组创建输出节点
            for prefix, outputs in output_groups.items():
                group_id = f"output_{prefix}"
                sanitized_id = self._sanitize_node_id(group_id)

                # 检查组内是否有optional输出
                has_optional = any(output.get("optional", False) for output in outputs)

                nodes.append(f'    {sanitized_id}["Output Group: {prefix} - {len(outputs)} items"]')

                # 根据optional属性设置样式
                if has_optional:
                    nodes.append(f"    class {sanitized_id} outputNodeOptional")
                else:
                    nodes.append(f"    class {sanitized_id} outputNode")

                node_ids.add(sanitized_id)
        else:
            # 正常创建每个输出节点
            for output_param in self.workflow_outputs:
                output_name = output_param.get("name")
                is_optional = output_param.get("optional", False)

                if not output_name:
                    continue

                node_id = f"output_{output_name}"
                sanitized_id = self._sanitize_node_id(node_id)
                display_name = self._sanitize_text(output_name, 20)

                nodes.append(f'    {sanitized_id}["{display_name}"]')

                # 根据optional属性设置样式
                if is_optional:
                    nodes.append(f"    class {sanitized_id} outputNodeOptional")
                else:
                    nodes.append(f"    class {sanitized_id} outputNode")

                node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_task_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建任务节点"""
        nodes = []
        node_ids = set()

        call_nodes = self._get_call_nodes()
        for call in call_nodes:
            call_name = call.get("call_name")
            task_name = call.get("callee_task")

            if not call_name:
                continue

            node_id = f"task_{call_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(call_name, 20)

            if task_name and task_name != call_name:
                display_task = self._sanitize_text(task_name, 15)
                nodes.append(f'    {sanitized_id}["{display_name}<br/>Task: {display_task}"]')
            else:
                nodes.append(f'    {sanitized_id}["{display_name}"]')

            nodes.append(f"    class {sanitized_id} callNode")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_variable_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建变量节点"""
        nodes = []
        node_ids = set()

        variable_definitions = self._get_variable_definitions()
        for var_def in variable_definitions:
            var_name = var_def.get("name")
            is_optional = var_def.get("optional", False)

            if not var_name:
                continue

            node_id = f"var_{var_name}"
            sanitized_id = self._sanitize_node_id(node_id)
            display_name = self._sanitize_text(var_name, 20)

            # 显示变量节点（使用圆角矩形）
            nodes.append(f'    {sanitized_id}("{display_name}")')

            # 根据optional属性设置样式
            if is_optional:
                nodes.append(f"    class {sanitized_id} varNodeOptional")
            else:
                nodes.append(f"    class {sanitized_id} varNode")

            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_conditional_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建条件节点"""
        nodes = []
        node_ids = set()

        conditional_nodes = self._get_conditional_nodes()
        for i, cond_node in enumerate(conditional_nodes):
            # 为每个条件节点生成唯一ID
            node_id = f"cond_{i+1}"
            sanitized_id = self._sanitize_node_id(node_id)

            # 获取条件表达式
            condition = cond_node.get("condition", {})
            condition_expr = condition.get("raw_expression", "condition")
            display_condition = self._sanitize_text(condition_expr, 10)

            # 显示条件节点（使用菱形）
            nodes.append(f'    {sanitized_id}{{"{display_condition}"}}')
            nodes.append(f"    class {sanitized_id} conditionalNode")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _create_scatter_nodes(self) -> Tuple[List[str], Set[str]]:
        """创建并行节点"""
        nodes = []
        node_ids = set()

        scatter_nodes = self._get_scatter_nodes()
        for i, scatter_node in enumerate(scatter_nodes):
            # 为每个并行节点生成唯一ID
            node_id = f"scatter_{i+1}"
            sanitized_id = self._sanitize_node_id(node_id)

            # 获取并行变量和表达式
            variable = scatter_node.get("variable", "var")
            expression = scatter_node.get("expression", {})
            expr_text = expression.get("raw_expression", "range")

            # 组合显示文本
            display_text = f"for {variable} in {self._sanitize_text(expr_text, 20)}"

            # 显示并行节点（使用平行四边形）
            nodes.append(f'    {sanitized_id}[/"{display_text}"/]')
            nodes.append(f"    class {sanitized_id} scatterNode")
            node_ids.add(sanitized_id)

        return nodes, node_ids

    def _extract_expression_dependencies(self, expression: Dict[str, Any]) -> Set[str]:
        """从表达式中提取依赖变量"""
        dependencies = set()

        if not expression:
            return dependencies

        # 处理不同类型的表达式
        expr_type = expression.get("type", "")

        if expr_type == "identifier":
            # 直接变量引用
            raw_expr = expression.get("raw_expression", "")
            if raw_expr:
                dependencies.add(raw_expr)

        elif expr_type == "complex":
            # 复杂表达式（如条件表达式）
            raw_expr = expression.get("raw_expression", "")
            if raw_expr:
                # 更完善的变量提取，处理各种情况
                dependencies.update(self._extract_variables_from_expression(raw_expr))

        elif expr_type == "function_call":
            # 函数调用表达式
            raw_expr = expression.get("raw_expression", "")
            if raw_expr:
                dependencies.update(self._extract_variables_from_expression(raw_expr))

        elif expr_type == "literal":
            # 字面量，无依赖
            pass

        return dependencies

    def _extract_variables_from_expression(self, raw_expr: str) -> Set[str]:
        """从原始表达式字符串中提取变量名"""
        variables = set()

        # 1. 首先处理任务输出引用，如 TaskName.outputName（优先级最高）
        task_output_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)\b"
        task_output_matches = re.findall(task_output_pattern, raw_expr)
        variables.update(task_output_matches)

        # 2. 处理数组访问，如 FASTQ[0], FASTQ[index]
        array_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\["
        array_matches = re.findall(array_pattern, raw_expr)
        variables.update(array_matches)

        # 3. 处理函数调用，如 length(FASTQ), size(genomeFile,"GB")
        function_pattern = r"\b[a-zA-Z_][a-zA-Z0-9_]*\(([^)]+)\)"
        function_matches = re.findall(function_pattern, raw_expr)
        for match in function_matches:
            # 递归处理函数参数，但要去除引号内的字符串
            clean_match = re.sub(r'"[^"]*"', "", match)  # 移除字符串字面量
            inner_vars = self._extract_variables_from_expression(clean_match)
            variables.update(inner_vars)

        # 4. 创建已识别的模式，用于从通用变量提取中排除
        recognized_patterns = set()
        for task_output in task_output_matches:
            # 将TaskName.outputName拆分为TaskName和outputName，避免重复提取
            task_name, output_name = task_output.split(".", 1)
            recognized_patterns.add(task_name)
            recognized_patterns.add(output_name)

        # 5. 处理一般的变量名，但排除已识别的模式和关键字
        var_pattern = r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"
        all_vars = re.findall(var_pattern, raw_expr)
        for var in all_vars:
            # 排除关键字、函数名和已识别的模式片段
            if var not in ["if", "then", "else", "true", "false", "length", "size", "range"] and var not in recognized_patterns:
                variables.add(var)

        return variables

    def _resolve_dependency_node(self, dep: str, all_node_ids: Set[str]) -> Optional[str]:
        """解析依赖关系并返回对应的节点ID"""
        # 1. 检查是否为工作流输入参数
        if self._is_workflow_input(dep):
            src_node_id = self._sanitize_node_id(f"input_{dep}")
            if src_node_id in all_node_ids:
                return src_node_id

        # 2. 检查是否为任务调用（task.output格式）
        if "." in dep:
            task_name = dep.split(".")[0]
            src_node_id = self._sanitize_node_id(f"task_{task_name}")
            if src_node_id in all_node_ids:
                return src_node_id

        # 3. 检查是否为变量
        src_node_id = self._sanitize_node_id(f"var_{dep}")
        if src_node_id in all_node_ids:
            return src_node_id

        return None

    def _get_tasks_in_control_structures(self) -> Set[str]:
        """获取位于控制结构中的任务名称"""
        tasks_in_control = set()

        # 检查条件节点中的任务
        for cond_node in self._get_conditional_nodes():
            for body_node in cond_node.get("body", []):
                if body_node.get("node_type") == "call":
                    tasks_in_control.add(body_node.get("call_name"))

        # 检查并行节点中的任务
        for scatter_node in self._get_scatter_nodes():
            for body_node in scatter_node.get("body", []):
                if body_node.get("node_type") == "call":
                    tasks_in_control.add(body_node.get("call_name"))
                # 检查嵌套的条件节点
                elif body_node.get("node_type") == "conditional":
                    for nested_node in body_node.get("body", []):
                        if nested_node.get("node_type") == "call":
                            tasks_in_control.add(nested_node.get("call_name"))

        return tasks_in_control

    def _create_task_input_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建任务输入边"""
        edges = []

        # 获取位于控制结构中的任务
        tasks_in_control = self._get_tasks_in_control_structures()

        call_nodes = self._get_call_nodes()
        for call in call_nodes:
            call_name = call.get("call_name")
            task_inputs = call.get("inputs", {})

            if not call_name:
                continue

            task_node_id = self._sanitize_node_id(f"task_{call_name}")

            for input_name, input_value in task_inputs.items():
                if isinstance(input_value, dict):
                    # 从输入表达式中提取依赖
                    dependencies = self._extract_expression_dependencies(input_value)

                    for dep in dependencies:
                        src_node_id = self._resolve_dependency_node(dep, all_node_ids)

                        if src_node_id and task_node_id in all_node_ids:
                            edge = (src_node_id, task_node_id)
                            if edge not in added_edges:
                                # 对于控制结构中的任务，允许输入参数、变量和任务输出的连接
                                if call_name in tasks_in_control:
                                    # 允许工作流输入参数、变量和任务输出到控制结构中的任务
                                    if src_node_id.startswith("input_") or src_node_id.startswith("var_") or src_node_id.startswith("task_"):
                                        edges.append(f"    {src_node_id} --> {task_node_id}")
                                        added_edges.add(edge)
                                else:
                                    # 非控制结构中的任务，建立所有连接
                                    edges.append(f"    {src_node_id} --> {task_node_id}")
                                    added_edges.add(edge)

        return edges

    def _create_output_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建输出边"""
        edges = []

        # 检查是否使用了分组的输出节点
        grouped_output = len(self.workflow_outputs) > 5

        for output_param in self.workflow_outputs:
            output_name = output_param.get("name")
            expression = output_param.get("expression")

            if not output_name:
                continue

            # 根据是否分组选择输出节点ID
            if grouped_output and output_name:
                # 找到该输出属于哪个分组
                prefix = "outputs"
                if "_" in output_name:
                    prefix = output_name.split("_")[0]

                output_node_id = self._sanitize_node_id(f"output_{prefix}")
            else:
                output_node_id = self._sanitize_node_id(f"output_{output_name}")

            # 从输出表达式中提取依赖
            if expression:
                dependencies = self._extract_expression_dependencies(expression)

                for dep in dependencies:
                    src_node_id = self._resolve_dependency_node(dep, all_node_ids)

                    if src_node_id and output_node_id in all_node_ids:
                        edge = (src_node_id, output_node_id)
                        if edge not in added_edges:
                            edges.append(f"    {src_node_id} --> {output_node_id}")
                            added_edges.add(edge)

        return edges

    def _build_variable_dependency_graph(self) -> Dict[str, Set[str]]:
        """构建变量依赖图"""
        var_deps = {}

        variable_definitions = self._get_variable_definitions()
        for var_def in variable_definitions:
            var_name = var_def.get("name")
            expression = var_def.get("expression")

            if not var_name or not expression:
                continue

            dependencies = self._extract_expression_dependencies(expression)
            var_deps[var_name] = dependencies

        return var_deps

    def _get_variables_in_control_structures(self) -> Set[str]:
        """获取位于控制结构中的变量名称"""
        vars_in_control = set()

        # 检查条件节点中的变量
        for cond_node in self._get_conditional_nodes():
            for body_node in cond_node.get("body", []):
                if body_node.get("node_type") == "declaration":
                    vars_in_control.add(body_node.get("name"))

        # 检查并行节点中的变量
        for scatter_node in self._get_scatter_nodes():
            for body_node in scatter_node.get("body", []):
                if body_node.get("node_type") == "declaration":
                    vars_in_control.add(body_node.get("name"))
                # 检查嵌套的条件节点
                elif body_node.get("node_type") == "conditional":
                    for nested_node in body_node.get("body", []):
                        if nested_node.get("node_type") == "declaration":
                            vars_in_control.add(nested_node.get("name"))

        return vars_in_control

    def _create_task_output_to_variable_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建任务输出到变量的边"""
        edges = []

        variable_definitions = self._get_variable_definitions()
        for var_def in variable_definitions:
            var_name = var_def.get("name")
            expression = var_def.get("expression")

            if not var_name or not expression:
                continue

            var_node_id = self._sanitize_node_id(f"var_{var_name}")
            if var_node_id not in all_node_ids:
                continue

            # 从表达式中提取依赖
            dependencies = self._extract_expression_dependencies(expression)

            for dep in dependencies:
                # 只处理任务输出（包含.的依赖）
                if "." in dep:
                    task_name = dep.split(".")[0]
                    task_node_id = self._sanitize_node_id(f"task_{task_name}")

                    if task_node_id in all_node_ids:
                        edge = (task_node_id, var_node_id)
                        if edge not in added_edges:
                            edges.append(f"    {task_node_id} --> {var_node_id}")
                            added_edges.add(edge)

        return edges

    def _create_control_structure_variable_output_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建控制结构中变量的输出连接"""
        edges = []

        # 获取位于控制结构中的变量
        vars_in_control = self._get_variables_in_control_structures()

        variable_definitions = self._get_variable_definitions()
        for var_def in variable_definitions:
            var_name = var_def.get("name")
            expression = var_def.get("expression")

            if not var_name or not expression:
                continue

            var_node_id = self._sanitize_node_id(f"var_{var_name}")

            # 从表达式中提取依赖
            dependencies = self._extract_expression_dependencies(expression)

            for dep in dependencies:
                # 只处理控制结构中的变量作为依赖
                if dep in vars_in_control:
                    src_node_id = self._sanitize_node_id(f"var_{dep}")

                    if src_node_id in all_node_ids and var_node_id in all_node_ids:
                        edge = (src_node_id, var_node_id)
                        if edge not in added_edges:
                            edges.append(f"    {src_node_id} --> {var_node_id}")
                            added_edges.add(edge)

        return edges

    def _create_variable_dependency_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建变量依赖边"""
        edges = []

        # 获取位于控制结构中的变量
        vars_in_control = self._get_variables_in_control_structures()

        variable_definitions = self._get_variable_definitions()
        for var_def in variable_definitions:
            var_name = var_def.get("name")
            expression = var_def.get("expression")

            if not var_name or not expression:
                continue

            var_node_id = self._sanitize_node_id(f"var_{var_name}")

            # 如果变量在控制结构中，跳过直接连接（应该通过控制节点连接）
            if var_name in vars_in_control:
                continue

            # 从表达式中提取依赖
            dependencies = self._extract_expression_dependencies(expression)

            for dep in dependencies:
                # 跳过任务输出依赖（这些由专门的方法处理）
                if "." in dep:
                    continue
                # 跳过控制结构中的变量依赖（这些由专门的方法处理）
                if dep in vars_in_control:
                    continue

                src_node_id = self._resolve_dependency_node(dep, all_node_ids)

                if src_node_id and var_node_id in all_node_ids:
                    edge = (src_node_id, var_node_id)
                    if edge not in added_edges:
                        edges.append(f"    {src_node_id} --> {var_node_id}")
                        added_edges.add(edge)

        return edges

    def _create_conditional_dependency_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建条件节点依赖边"""
        edges = []

        conditional_nodes = self._get_conditional_nodes()
        for i, cond_node in enumerate(conditional_nodes):
            cond_node_id = self._sanitize_node_id(f"cond_{i+1}")

            # 从条件表达式中提取依赖
            condition = cond_node.get("condition", {})
            if condition:
                dependencies = self._extract_expression_dependencies(condition)

                for dep in dependencies:
                    src_node_id = self._resolve_dependency_node(dep, all_node_ids)

                    if src_node_id and cond_node_id in all_node_ids:
                        edge = (src_node_id, cond_node_id)
                        if edge not in added_edges:
                            edges.append(f"    {src_node_id} --> {cond_node_id}")
                            added_edges.add(edge)

        return edges

    def _create_scatter_dependency_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建并行节点依赖边"""
        edges = []

        scatter_nodes = self._get_scatter_nodes()
        for i, scatter_node in enumerate(scatter_nodes):
            scatter_node_id = self._sanitize_node_id(f"scatter_{i+1}")

            # 从并行表达式中提取依赖
            expression = scatter_node.get("expression", {})
            if expression:
                dependencies = self._extract_expression_dependencies(expression)

                for dep in dependencies:
                    src_node_id = self._resolve_dependency_node(dep, all_node_ids)

                    if src_node_id and scatter_node_id in all_node_ids:
                        edge = (src_node_id, scatter_node_id)
                        if edge not in added_edges:
                            edges.append(f"    {src_node_id} --> {scatter_node_id}")
                            added_edges.add(edge)

        return edges

    def _create_conditional_output_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建条件节点输出边"""
        edges = []

        conditional_nodes = self._get_conditional_nodes()
        for i, cond_node in enumerate(conditional_nodes):
            cond_node_id = self._sanitize_node_id(f"cond_{i+1}")

            # 条件节点连接到其body内的任务和变量节点
            body_nodes = cond_node.get("body", [])

            for body_node in body_nodes:
                if body_node.get("node_type") == "call":
                    # 连接到任务节点
                    call_name = body_node.get("call_name")
                    if call_name:
                        target_node_id = self._sanitize_node_id(f"task_{call_name}")
                        if target_node_id in all_node_ids:
                            edge = (cond_node_id, target_node_id)
                            if edge not in added_edges:
                                edges.append(f"    {cond_node_id} -.-> {target_node_id}")
                                added_edges.add(edge)

                elif body_node.get("node_type") == "declaration":
                    # 连接到变量节点
                    var_name = body_node.get("name")
                    if var_name:
                        target_node_id = self._sanitize_node_id(f"var_{var_name}")
                        if target_node_id in all_node_ids:
                            edge = (cond_node_id, target_node_id)
                            if edge not in added_edges:
                                edges.append(f"    {cond_node_id} -.-> {target_node_id}")
                                added_edges.add(edge)

        return edges

    def _create_scatter_output_edges(self, all_node_ids: Set[str], added_edges: Set[Tuple[str, str]]) -> List[str]:
        """创建并行节点输出边"""
        edges = []

        scatter_nodes = self._get_scatter_nodes()
        for i, scatter_node in enumerate(scatter_nodes):
            scatter_node_id = self._sanitize_node_id(f"scatter_{i+1}")

            # 并行节点连接到其body内的任务和变量节点
            body_nodes = scatter_node.get("body", [])

            for body_node in body_nodes:
                if body_node.get("node_type") == "call":
                    # 连接到任务节点
                    call_name = body_node.get("call_name")
                    if call_name:
                        target_node_id = self._sanitize_node_id(f"task_{call_name}")
                        if target_node_id in all_node_ids:
                            edge = (scatter_node_id, target_node_id)
                            if edge not in added_edges:
                                edges.append(f"    {scatter_node_id} --> {target_node_id}")
                                added_edges.add(edge)

                elif body_node.get("node_type") == "declaration":
                    # 连接到变量节点
                    var_name = body_node.get("name")
                    if var_name:
                        target_node_id = self._sanitize_node_id(f"var_{var_name}")
                        if target_node_id in all_node_ids:
                            edge = (scatter_node_id, target_node_id)
                            if edge not in added_edges:
                                edges.append(f"    {scatter_node_id} --> {target_node_id}")
                                added_edges.add(edge)

        return edges

    def _create_edges(self, all_node_ids: Set[str]) -> List[str]:
        """创建所有边连接"""
        edges = []
        added_edges = set()

        # 1. 变量依赖边（输入和变量之间）
        edges.extend(self._create_variable_dependency_edges(all_node_ids, added_edges))

        # 2. 任务输出到变量的边
        edges.extend(self._create_task_output_to_variable_edges(all_node_ids, added_edges))

        # 3. 控制结构中变量的输出边
        edges.extend(self._create_control_structure_variable_output_edges(all_node_ids, added_edges))

        # 4. 条件节点依赖边（输入）
        edges.extend(self._create_conditional_dependency_edges(all_node_ids, added_edges))

        # 5. 并行节点依赖边（输入）
        edges.extend(self._create_scatter_dependency_edges(all_node_ids, added_edges))

        # 6. 条件节点输出边
        edges.extend(self._create_conditional_output_edges(all_node_ids, added_edges))

        # 7. 并行节点输出边
        edges.extend(self._create_scatter_output_edges(all_node_ids, added_edges))

        # 8. 任务输入边
        edges.extend(self._create_task_input_edges(all_node_ids, added_edges))

        # 9. 输出边
        edges.extend(self._create_output_edges(all_node_ids, added_edges))

        return edges

    def generate_flowchart(self) -> str:
        """生成流程图"""
        if not self.data:
            return "// 数据加载失败"

        if self.use_modern_syntax:
            return self._generate_modern_flowchart()
        else:
            return self._generate_traditional_flowchart()

    def _generate_modern_flowchart(self) -> str:
        """生成现代化的flowchart格式"""
        lines = []

        # 前置配置：使用ELK布局引擎
        lines.extend(["---", "config:", "  layout: elk", "---", f"flowchart {self.graph_direction}"])

        # 创建节点集合
        all_node_ids = set()

        # 收集所有节点ID
        _, input_ids = self._create_input_nodes()
        all_node_ids.update(input_ids)

        _, var_ids = self._create_variable_nodes()
        all_node_ids.update(var_ids)

        _, cond_ids = self._create_conditional_nodes()
        all_node_ids.update(cond_ids)

        _, scatter_ids = self._create_scatter_nodes()
        all_node_ids.update(scatter_ids)

        _, task_ids = self._create_task_nodes()
        all_node_ids.update(task_ids)

        _, output_ids = self._create_output_nodes()
        all_node_ids.update(output_ids)

        # 生成合并的连接语句
        lines.extend(self._generate_modern_connections(all_node_ids))

        # 生成图例说明
        lines.extend(self._generate_legend())

        # 生成样式应用
        lines.extend(self._generate_modern_styles(all_node_ids))

        # 生成样式定义
        lines.extend(self._generate_mermaid_styles())

        return "\n".join(lines)

    def _generate_traditional_flowchart(self) -> str:
        """生成传统的graph格式"""
        mermaid_lines = [f"graph {self.graph_direction}"]

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

        # 条件节点
        cond_nodes, cond_ids = self._create_conditional_nodes()
        mermaid_lines.extend(cond_nodes)
        all_node_ids.update(cond_ids)

        # 并行节点
        scatter_nodes, scatter_ids = self._create_scatter_nodes()
        mermaid_lines.extend(scatter_nodes)
        all_node_ids.update(scatter_ids)

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

    def _generate_modern_connections(self, all_node_ids: Set[str]) -> List[str]:
        """生成现代化的连接语句"""
        lines = []

        # 收集所有连接关系
        connections = {}
        added_edges = set()

        # 使用现有的边创建逻辑
        edges = self._create_edges(all_node_ids)

        for edge in edges:
            if edge.strip().startswith("//") or edge.strip().startswith("%") or not edge.strip():
                continue

            # 解析边连接: "src --> dst" 或 "src -.-> dst"
            edge_clean = edge.strip()
            if " --> " in edge_clean:
                src, dst = edge_clean.split(" --> ", 1)
            elif " -.-> " in edge_clean:
                src, dst = edge_clean.split(" -.-> ", 1)
            else:
                continue

            src = src.strip()
            dst = dst.strip()

            if src not in connections:
                connections[src] = []
            if dst not in connections[src]:
                connections[src].append(dst)

        # 获取节点显示名称
        node_labels = self._get_node_labels()

        # 生成连接语句
        for src_node, dst_nodes in connections.items():
            src_label = node_labels.get(src_node, src_node) or src_node
            src_shape = self._get_node_shape(src_node, src_label)

            if len(dst_nodes) == 1:
                # 单个目标
                dst_node = dst_nodes[0]
                dst_label = node_labels.get(dst_node, dst_node) or dst_node
                dst_shape = self._get_node_shape(dst_node, dst_label)
                lines.append(f"    {src_node}{src_shape} --> {dst_node}{dst_shape}")
            else:
                # 多个目标，使用 & 语法
                dst_parts = []
                for dst_node in dst_nodes:
                    dst_label = node_labels.get(dst_node, dst_node) or dst_node
                    dst_shape = self._get_node_shape(dst_node, dst_label)
                    dst_parts.append(f"{dst_node}{dst_shape}")

                dst_combined = " & ".join(dst_parts)
                lines.append(f"    {src_node}{src_shape} --> {dst_combined}")

        return lines

    def _get_node_shape(self, node_id: str, node_label: str) -> str:
        """根据节点类型返回相应的形状语法"""
        # 输入节点 - 矩形
        if node_id.startswith("input_"):
            return f'["{node_label}"]'
        # 变量节点 - 圆角矩形
        elif node_id.startswith("var_"):
            return f'("{node_label}")'
        # 任务节点 - 矩形
        elif node_id.startswith("task_"):
            return f'["{node_label}"]'
        # 条件节点 - 菱形
        elif node_id.startswith("cond_"):
            return f'{{"{node_label}"}}'
        # 并行节点 - 平行四边形
        elif node_id.startswith("scatter_"):
            return f'[/"{node_label}"/]'
        # 输出节点 - 矩形
        elif node_id.startswith("output_"):
            return f'["{node_label}"]'
        # 图例节点 - 根据类型设置不同形状
        elif node_id.startswith("legend_"):
            if "input" in node_id:
                return f'["{node_label}"]'
            elif "var" in node_id:
                return f'("{node_label}")'
            elif "task" in node_id:
                return f'["{node_label}"]'
            elif "cond" in node_id:
                return f'{{"{node_label}"}}'
            elif "scatter" in node_id:
                return f'[/"{node_label}"/]'
            elif "output" in node_id:
                return f'["{node_label}"]'
            else:
                return f'["{node_label}"]'
        # 默认矩形
        else:
            return f'["{node_label}"]'

    def _get_node_labels(self) -> Dict[str, str]:
        """获取所有节点的显示标签"""
        labels = {}

        # 输入节点标签
        for input_param in self.workflow_inputs:
            input_name = input_param.get("name")
            if input_name:
                node_id = self._sanitize_node_id(f"input_{input_name}")
                display_name = self._sanitize_text(input_name, 20)
                labels[node_id] = f"Input: {display_name}"

        # 变量节点标签
        for var_def in self._get_variable_definitions():
            var_name = var_def.get("name")
            if var_name:
                node_id = self._sanitize_node_id(f"var_{var_name}")
                display_name = self._sanitize_text(var_name, 20)
                labels[node_id] = display_name

        # 任务节点标签
        for call in self._get_call_nodes():
            call_name = call.get("call_name")
            if call_name:
                node_id = self._sanitize_node_id(f"task_{call_name}")
                display_name = self._sanitize_text(call_name, 20)
                labels[node_id] = display_name

        # 条件节点标签
        for i, cond_node in enumerate(self._get_conditional_nodes()):
            node_id = self._sanitize_node_id(f"cond_{i+1}")
            condition = cond_node.get("condition", {})
            condition_expr = condition.get("raw_expression", "condition")
            display_condition = self._sanitize_text(condition_expr, 10)
            labels[node_id] = display_condition

        # 并行节点标签
        for i, scatter_node in enumerate(self._get_scatter_nodes()):
            node_id = self._sanitize_node_id(f"scatter_{i+1}")
            variable = scatter_node.get("variable", "var")
            expression = scatter_node.get("expression", {})
            expr_text = expression.get("raw_expression", "range")
            display_text = f"for {variable} in {self._sanitize_text(expr_text, 20)}"
            labels[node_id] = display_text

        # 输出节点标签
        if len(self.workflow_outputs) > 5:
            # 分组输出
            output_groups = {}
            for output in self.workflow_outputs:
                output_name = output.get("name", "")
                if output_name:
                    prefix = output_name.split("_")[0] if "_" in output_name else "outputs"
                    if prefix not in output_groups:
                        output_groups[prefix] = []
                        node_id = self._sanitize_node_id(f"output_{prefix}")
                        count = len([o for o in self.workflow_outputs if o.get("name", "").startswith(prefix)])
                        labels[node_id] = f"Output Group: {prefix} - {count} items"
        else:
            for output_param in self.workflow_outputs:
                output_name = output_param.get("name")
                if output_name:
                    node_id = self._sanitize_node_id(f"output_{output_name}")
                    display_name = self._sanitize_text(output_name, 20)
                    labels[node_id] = display_name

        return labels

    def _generate_modern_styles(self, all_node_ids: Set[str]) -> List[str]:
        """生成现代化的样式应用语句"""
        lines = []

        # 输入节点样式
        for input_param in self.workflow_inputs:
            input_name = input_param.get("name")
            if input_name:
                node_id = self._sanitize_node_id(f"input_{input_name}")
                is_optional = input_param.get("optional", False)
                style_class = "inputNodeOptional" if is_optional else "inputNode"
                lines.append(f"     {node_id}:::{style_class}")

        # 变量节点样式
        for var_def in self._get_variable_definitions():
            var_name = var_def.get("name")
            if var_name:
                node_id = self._sanitize_node_id(f"var_{var_name}")
                is_optional = var_def.get("optional", False)
                style_class = "varNodeOptional" if is_optional else "varNode"
                lines.append(f"     {node_id}:::{style_class}")

        # 任务节点样式
        for call in self._get_call_nodes():
            call_name = call.get("call_name")
            if call_name:
                node_id = self._sanitize_node_id(f"task_{call_name}")
                lines.append(f"     {node_id}:::callNode")

        # 条件节点样式
        for i, cond_node in enumerate(self._get_conditional_nodes()):
            node_id = self._sanitize_node_id(f"cond_{i+1}")
            lines.append(f"     {node_id}:::conditionalNode")

        # 并行节点样式
        for i, scatter_node in enumerate(self._get_scatter_nodes()):
            node_id = self._sanitize_node_id(f"scatter_{i+1}")
            lines.append(f"     {node_id}:::scatterNode")

        # 输出节点样式
        if len(self.workflow_outputs) > 5:
            # 分组输出
            output_groups = {}
            for output in self.workflow_outputs:
                output_name = output.get("name", "")
                if output_name:
                    prefix = output_name.split("_")[0] if "_" in output_name else "outputs"
                    if prefix not in output_groups:
                        output_groups[prefix] = []
                        node_id = self._sanitize_node_id(f"output_{prefix}")
                        has_optional = any(o.get("optional", False) for o in self.workflow_outputs if o.get("name", "").startswith(prefix))
                        style_class = "outputNodeOptional" if has_optional else "outputNode"
                        lines.append(f"     {node_id}:::{style_class}")
        else:
            for output_param in self.workflow_outputs:
                output_name = output_param.get("name")
                if output_name:
                    node_id = self._sanitize_node_id(f"output_{output_name}")
                    is_optional = output_param.get("optional", False)
                    style_class = "outputNodeOptional" if is_optional else "outputNode"
                    lines.append(f"     {node_id}:::{style_class}")

        # 图例节点样式（这些在_generate_legend中已经定义，这里只是确保一致性）
        legend_styles = [
            "     legend_input:::inputNode",
            "     legend_input_opt:::inputNodeOptional",
            "     legend_var:::varNode",
            "     legend_var_opt:::varNodeOptional",
            "     legend_task:::callNode",
            "     legend_cond:::conditionalNode",
            "     legend_scatter:::scatterNode",
            "     legend_output:::outputNode",
            "     legend_output_opt:::outputNodeOptional",
        ]
        lines.extend(legend_styles)

        return lines

    def _generate_legend(self) -> List[str]:
        """生成图例说明"""
        lines = []

        # 添加图例子图
        lines.extend(
            [
                '    subgraph legend ["📖 图例说明"]',
                "        direction TB",
                '        legend_input["📥 输入参数"]',
                '        legend_input_opt["📥 可选输入"]',
                '        legend_var("🔢 变量") ',
                '        legend_var_opt("🔢 可选变量")',
                '        legend_task["⚙️ 任务"]',
                '        legend_cond{"❓ 条件判断"}',
                '        legend_scatter[/"🔄 并行处理"/]',
                '        legend_output["📤 输出结果"]',
                '        legend_output_opt["📤 可选输出"]',
                "        ",
                "        legend_input:::inputNode",
                "        legend_input_opt:::inputNodeOptional",
                "        legend_var:::varNode",
                "        legend_var_opt:::varNodeOptional",
                "        legend_task:::callNode",
                "        legend_cond:::conditionalNode",
                "        legend_scatter:::scatterNode",
                "        legend_output:::outputNode",
                "        legend_output_opt:::outputNodeOptional",
                "    end",
                "",
            ]
        )

        return lines

    def convert_mmd_to_images(self, mmd_file: str, output_dir: str = ".", formats: List[str] = ["svg", "png"]) -> Dict[str, str]:
        """
        将MMD文件转换为SVG和PNG格式

        Args:
            mmd_file: MMD文件路径
            output_dir: 输出目录
            formats: 要转换的格式列表，支持 'svg', 'png', 'pdf'

        Returns:
            Dict[str, str]: 转换结果，格式为 {format: file_path}
        """
        results = {}

        # 检查mermaid-cli是否已安装
        if not self._check_mermaid_cli():
            print("❌ mermaid-cli 未安装，正在尝试安装...")
            if not self._install_mermaid_cli():
                print("❌ 安装 mermaid-cli 失败，请手动安装:")
                print("   npm install -g @mermaid-js/mermaid-cli")
                return results

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 获取基础文件名
        base_name = os.path.splitext(os.path.basename(mmd_file))[0]

        # 转换为各种格式
        for format_type in formats:
            if format_type not in ["svg", "png", "pdf"]:
                print(f"⚠️  不支持的格式: {format_type}")
                continue

            output_file = os.path.join(output_dir, f"{base_name}.{format_type}")

            try:
                # 使用mmdc命令转换
                cmd = [
                    "mmdc",
                    "-i",
                    mmd_file,
                    "-o",
                    output_file,
                    "-t",
                    "neutral",  # 使用中性主题
                    "-b",
                    "white",  # 白色背景
                    "-w",
                    "1920",  # 宽度
                    "-H",
                    "1080",  # 高度
                ]

                # 如果是PNG格式，设置额外参数
                if format_type == "png":
                    cmd.extend(["-s", "2"])  # 设置缩放比例

                print(f"🔄 正在转换为 {format_type.upper()} 格式...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    results[format_type] = output_file
                    print(f"✅ {format_type.upper()} 转换成功: {output_file}")
                else:
                    print(f"❌ {format_type.upper()} 转换失败:")
                    print(f"   错误信息: {result.stderr}")

            except subprocess.TimeoutExpired:
                print(f"❌ {format_type.upper()} 转换超时")
            except Exception as e:
                print(f"❌ {format_type.upper()} 转换出错: {e}")

        return results

    def _check_mermaid_cli(self) -> bool:
        """检查mermaid-cli是否已安装"""
        try:
            result = subprocess.run(["mmdc", "--version"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _install_mermaid_cli(self) -> bool:
        """尝试安装mermaid-cli"""
        try:
            # 检查npm是否可用
            npm_result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
            if npm_result.returncode != 0:
                print("❌ npm 不可用，无法自动安装 mermaid-cli")
                return False

            # 安装mermaid-cli
            print("📦 正在安装 @mermaid-js/mermaid-cli...")
            install_result = subprocess.run(["npm", "install", "-g", "@mermaid-js/mermaid-cli"], capture_output=True, text=True, timeout=60)

            if install_result.returncode == 0:
                print("✅ mermaid-cli 安装成功")
                return True
            else:
                print(f"❌ mermaid-cli 安装失败: {install_result.stderr}")
                return False

        except Exception as e:
            print(f"❌ 安装过程出错: {e}")
            return False


def main():
    """主函数"""
    json_file = "docs/wdl/SAW-ST-V8.json"

    try:
        # 使用现代化的flowchart语法和ELK布局引擎
        generator = WDLFlowchartGenerator(json_file, graph_direction="TD", use_modern_syntax=False)
        print("生成WDL工作流程图...")

        flowchart = generator.generate_flowchart()

        # 保存到文件
        output_file = "wdl_workflow_flowchart.mmd"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(flowchart)

        print(f"流程图已生成: {output_file}")
        print(f"工作流名称: {generator.workflow_info.get('name', 'Unknown')}")
        print(f"输入参数: {len(generator.workflow_inputs)}")
        print(f"输出参数: {len(generator.workflow_outputs)}")
        print(f"工作流节点: {len(generator.workflow_nodes)}")
        print(f"任务定义: {len(generator.tasks)}")

        # 转换为图片格式
        # print("\n🔄 转换为图片格式...")
        # results = generator.convert_mmd_to_images(output_file, ".", ["svg", "png"])

        # if results:
        #     print("✅ 图片转换完成:")
        #     for format_type, file_path in results.items():
        #         print(f"   📄 {format_type.upper()}: {file_path}")
        # else:
        #     print("⚠️  图片转换失败或未完成")

    except Exception as e:
        print(f"生成流程图时发生错误: {e}")
        import traceback

        traceback.print_exc()


def convert_mmd_file(mmd_file: str, output_dir: str = ".", formats: List[str] = ["svg", "png"]) -> Dict[str, str]:
    """
    独立的MMD文件转换函数，无需创建WDLFlowchartGenerator实例

    Args:
        mmd_file: MMD文件路径
        output_dir: 输出目录
        formats: 要转换的格式列表，支持 'svg', 'png', 'pdf'

    Returns:
        Dict[str, str]: 转换结果，格式为 {format: file_path}
    """
    # 创建一个临时的生成器实例来使用转换方法
    temp_generator = WDLFlowchartGenerator.__new__(WDLFlowchartGenerator)
    return temp_generator.convert_mmd_to_images(mmd_file, output_dir, formats)


if __name__ == "__main__":
    main()
