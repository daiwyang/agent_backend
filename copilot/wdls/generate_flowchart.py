#!/usr/bin/env python3
"""
WDL解析结果流程图生成器
基于JSON schema结构，生成可渲染的Mermaid流程图
"""

import json
import re
from typing import Dict, List, Any, Optional


class FlowchartGenerator:
    """流程图生成器"""

    def __init__(self, json_file: str):
        """初始化流程图生成器"""
        self.json_file = json_file
        self.data = self._load_json()

    def _load_json(self) -> Dict[str, Any]:
        """加载JSON数据"""
        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载JSON文件失败: {e}")
            return {}

    def _get_execution_sequence(self) -> List[Dict[str, Any]]:
        """获取执行序列"""
        return self.data.get("execution_structure", {}).get("execution_sequence", [])

    def _sanitize_node_id(self, node_id: str) -> str:
        """清理节点ID，确保Mermaid兼容"""
        # 移除或替换可能导致问题的字符
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", node_id)
        # 确保不以数字开头
        if sanitized and sanitized[0].isdigit():
            sanitized = "node_" + sanitized
        return sanitized

    def _sanitize_text(self, text: Any) -> str:
        """清理文本，确保Mermaid兼容"""
        if text is None:
            return ""

        text_str = str(text)
        # 转义特殊字符
        text_str = text_str.replace('"', '\\"')
        text_str = text_str.replace("'", "\\'")
        text_str = text_str.replace("[", "\\[")
        text_str = text_str.replace("]", "\\]")
        text_str = text_str.replace("{", "\\{")
        text_str = text_str.replace("}", "\\}")
        text_str = text_str.replace("(", "\\(")
        text_str = text_str.replace(")", "\\)")
        text_str = text_str.replace("|", "\\|")
        text_str = text_str.replace(">", "\\>")
        text_str = text_str.replace("<", "\\<")
        text_str = text_str.replace("&", "&amp;")
        text_str = text_str.replace("#", "\\#")
        text_str = text_str.replace("!", "\\!")
        text_str = text_str.replace("?", "\\?")
        text_str = text_str.replace(":", "\\:")
        text_str = text_str.replace(";", "\\;")
        text_str = text_str.replace(",", "\\,")
        text_str = text_str.replace(".", "\\.")
        text_str = text_str.replace("=", "\\=")
        text_str = text_str.replace("+", "\\+")
        text_str = text_str.replace("-", "\\-")
        text_str = text_str.replace("*", "\\*")
        text_str = text_str.replace("/", "\\/")
        text_str = text_str.replace("\\", "\\\\")
        text_str = text_str.replace("^", "\\^")
        text_str = text_str.replace("$", "\\$")
        text_str = text_str.replace("@", "\\@")
        text_str = text_str.replace("%", "\\%")
        text_str = text_str.replace("~", "\\~")
        text_str = text_str.replace("`", "\\`")

        return text_str

    def _truncate_text(self, text: Any, max_length: int = 15) -> str:
        """截断文本，避免节点过大"""
        if isinstance(text, str):
            sanitized = self._sanitize_text(text)
            if len(sanitized) > max_length:
                return sanitized[: max_length - 3] + "..."
            return sanitized
        else:
            sanitized = self._sanitize_text(str(text))
            return sanitized[:max_length]

    def _get_node_color_class(self, step_type: str, variable_type: Optional[str] = None) -> str:
        """根据步骤类型和变量类型获取颜色类"""
        if step_type == "variable_assignment" and variable_type:
            # 根据变量类型设置颜色
            type_colors = {"Int": "intVar", "Float": "intVar", "String": "stringVar", "Boolean": "booleanVar", "Array": "arrayVar", "File": "fileVar"}
            base_type = variable_type.split("[")[0]
            return type_colors.get(base_type, "stringVar")

        # 根据步骤类型设置颜色
        type_colors = {
            "call": "callNode",
            "conditional_call": "conditionalNode",
            "scatter_call": "scatterNode",
            "variable_assignment": "variableNode",
        }
        return type_colors.get(step_type, "defaultNode")

    def _extract_variables_from_expression(self, expression: str) -> List[str]:
        """从表达式中提取变量名"""
        if not isinstance(expression, str):
            return []
        
        import re
        variables = []
        
        # 匹配 ${variable_name} 模式
        dollar_vars = re.findall(r'\$\{([^}]+)\}', expression)
        variables.extend(dollar_vars)
        
        # 匹配直接变量名，包括 !variable 模式
        # 先处理 !variable 模式
        not_vars = re.findall(r'!([a-zA-Z_][a-zA-Z0-9_]*)', expression)
        variables.extend(not_vars)
        
        # 匹配普通变量名（排除字符串字面量和已处理的变量）
        # 排除常见的操作符和关键字
        excluded_words = {'if', 'then', 'else', 'true', 'false', 'length', 'read_json', 'read_int', 'read_lines', 'glob', 'stdout'}
        direct_vars = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expression)
        
        for var in direct_vars:
            if var not in excluded_words and var not in variables:
                variables.append(var)
        
        return list(set(variables))  # 去重

    def _find_variable_nodes(self, variable_names: List[str], all_node_ids: set) -> List[str]:
        """根据变量名找到对应的节点ID"""
        variable_nodes = []
        for var_name in variable_names:
            # 查找以 assign_ 开头的节点
            for node_id in all_node_ids:
                if node_id.startswith("assign_") and var_name in node_id:
                    variable_nodes.append(node_id)
                    break
            
            # 如果没有找到assign节点，检查是否是工作流输入参数
            if not any(node_id.startswith("assign_") and var_name in node_id for node_id in all_node_ids):
                # 检查是否是工作流输入参数
                if self._is_workflow_input(var_name):
                    # 为工作流输入创建虚拟节点ID
                    input_node_id = f"input_{var_name}"
                    if input_node_id not in all_node_ids:
                        # 这里我们暂时跳过，因为工作流输入没有对应的assign节点
                        pass
        return variable_nodes

    def _is_workflow_input(self, variable_name: str) -> bool:
        """检查变量是否是工作流输入参数"""
        if not hasattr(self, '_workflow_inputs'):
            self._workflow_inputs = set()
            inputs = self.data.get("inputs", [])
            for input_param in inputs:
                if isinstance(input_param, dict) and "name" in input_param:
                    self._workflow_inputs.add(input_param["name"])
        
        return variable_name in self._workflow_inputs

    def _get_task_input_variables(self, step: Dict) -> List[str]:
        """获取任务输入参数中使用的变量"""
        variables = []
        # 1. 优先从 step 顶层找 inputs
        inputs = step.get("inputs", {})
        # 2. 如果没有，再从 context 里找
        if not inputs:
            context = step.get("context", {})
            inputs = context.get("inputs", {})
        for param_name, param_value in inputs.items():
            if isinstance(param_value, str):
                vars_in_param = self._extract_variables_from_expression(param_value)
                variables.extend(vars_in_param)
            elif isinstance(param_value, dict):
                # 处理复杂对象 - 检查是否有 name 字段（变量引用）
                if "name" in param_value:
                    variables.append(param_value["name"])
                # 检查其他字段中的变量
                for key, value in param_value.items():
                    if isinstance(value, str):
                        vars_in_param = self._extract_variables_from_expression(value)
                        variables.extend(vars_in_param)
        # 检查条件表达式
        context = step.get("context", {})
        condition = context.get("condition", "")
        if condition:
            vars_in_condition = self._extract_variables_from_expression(condition)
            variables.extend(vars_in_condition)
        # 检查散点变量
        scatter_var = context.get("variable", "")
        if scatter_var:
            variables.append(scatter_var)
        return list(set(variables))  # 去重

    def _get_valid_dependencies(self, dependencies: List[str], all_node_ids: set) -> List[str]:
        """获取有效的依赖关系"""
        valid_deps = []
        for dep in dependencies:
            # 检查是否是有效的节点ID
            if dep in all_node_ids:
                valid_deps.append(dep)
            else:
                # 尝试查找匹配的节点
                for node_id in all_node_ids:
                    if dep in node_id or node_id.endswith(dep):
                        valid_deps.append(node_id)
                        break
        return valid_deps

    def _filter_valid_connections(self, connections: List[tuple], all_node_ids: set) -> List[tuple]:
        """过滤有效的连接关系，避免自循环和无效连接"""
        valid_connections = []
        for from_node, to_node in connections:
            # 避免自循环
            if from_node == to_node:
                continue

            # 确保两个节点都存在
            if from_node in all_node_ids and to_node in all_node_ids:
                valid_connections.append((from_node, to_node))

        return valid_connections

    def _find_previous_step(self, execution_sequence: List[Dict], current_step: Dict) -> Optional[Dict]:
        """找到前一个步骤"""
        current_order = current_step.get("execution_order", 0)
        for step in execution_sequence:
            if step.get("execution_order", 0) == current_order - 1:
                return step
        return None

    def generate_flowchart(self) -> str:
        """生成流程图"""
        execution_sequence = self._get_execution_sequence()

        if not execution_sequence:
            return "// 未找到execution_sequence数据"

        mermaid_code = ["graph TD"]

        # 添加样式定义
        mermaid_code.extend(
            [
                "    %% 样式定义",
                "    classDef callNode fill:#e1f5fe,stroke:#01579b,stroke-width:2px",
                "    classDef conditionalNode fill:#fff3e0,stroke:#e65100,stroke-width:2px",
                "    classDef scatterNode fill:#f3e5f5,stroke:#4a148c,stroke-width:2px",
                "    classDef intVar fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px",
                "    classDef stringVar fill:#e3f2fd,stroke:#1976d2,stroke-width:2px",
                "    classDef booleanVar fill:#fff3e0,stroke:#f57c00,stroke-width:2px",
                "    classDef arrayVar fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px",
                "    classDef fileVar fill:#fce4ec,stroke:#c2185b,stroke-width:2px",
                "    classDef inputNode fill:#fffde7,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 3;",
                "    classDef outputNode fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,stroke-dasharray: 6 2;",
            ]
        )

        # 收集所有有效的节点ID
        all_node_ids = set()
        for step in execution_sequence:
            step_id = self._sanitize_node_id(step.get("step_id", "unknown"))
            all_node_ids.add(step_id)

        # 收集所有被引用的workflow输入参数
        referenced_inputs = set()
        for step in execution_sequence:
            step_type = step.get("step_type", "unknown")
            if step_type in ["call", "conditional_call", "scatter_call"]:
                input_variables = self._get_task_input_variables(step)
                for var in input_variables:
                    if self._is_workflow_input(var):
                        referenced_inputs.add(var)
            # 条件表达式也可能在dependencies里
            dependencies = step.get("dependencies", [])
            for dep in dependencies:
                if self._is_workflow_input(dep):
                    referenced_inputs.add(dep)

        # 收集所有workflow输出参数
        workflow_outputs = self.data.get("outputs", [])
        output_nodes = []
        output_edges = []
        for output in workflow_outputs:
            out_name = output.get("name")
            out_expr = output.get("expression")
            if not out_name or not out_expr:
                continue
            output_node_id = f"output_{out_name}"
            output_nodes.append((output_node_id, out_name))
            
            import re
            # 1. 提取所有 task.output 或 assign_xxx
            # 支持条件表达式、嵌套表达式等
            task_matches = re.findall(r'([a-zA-Z0-9_]+)\s*\.\s*[a-zA-Z0-9_]+', out_expr)
            assign_matches = re.findall(r'assign_([a-zA-Z0-9_]+)', out_expr)
            all_matches = set(task_matches + assign_matches)
            # 兼容 if ... then ... else ...
            if not all_matches:
                # 也可能是直接 task/assign 变量
                simple_matches = re.findall(r'([a-zA-Z0-9_]+)', out_expr)
                all_matches = set(simple_matches)
            for match in all_matches:
                match = match.strip()
                # assign节点
                assign_id = f"assign_{match}"
                if assign_id in all_node_ids:
                    output_edges.append((assign_id, output_node_id))
                # 任务节点模糊匹配
                for node_id in all_node_ids:
                    if node_id == match or node_id.endswith(match):
                        output_edges.append((node_id, output_node_id))

        # 解析全局参数映射，补充变量到任务的连线（虚线）
        global_param_edges = []
        for var_name, mapping_list in self.data.items():
            # 跳过非参数映射
            if not isinstance(mapping_list, list):
                continue
            for mapping in mapping_list:
                if not isinstance(mapping, dict):
                    continue
                call = mapping.get("call")
                expr = mapping.get("expression")
                # 只处理 expression 直接等于 var_name 的映射
                if expr == var_name and call:
                    # assign节点
                    assign_id = f"assign_{var_name}"
                    if assign_id in all_node_ids:
                        global_param_edges.append((assign_id, call, "dashed"))
                    # 输入节点
                    input_id = f"input_{var_name}"
                    if input_id in all_node_ids:
                        global_param_edges.append((input_id, call, "dashed"))

        # Mermaid 连线去重
        added_edges = set()

        # assign 节点与输入节点的连线（只根据 variable_definitions 的 dependencies 字段）
        variable_definitions = self.data.get("variable_definitions", {})
        for var_name, var_def in variable_definitions.items():
            deps = var_def.get("dependencies", [])
            for dep in deps:
                edge = (f"input_{dep}", f"assign_{var_name}")
                if edge not in added_edges:
                    mermaid_code.append(f"    input_{dep} --> assign_{var_name}")
                    added_edges.add(edge)

        # 节点定义
        for step in execution_sequence:
            step_id = self._sanitize_node_id(step.get("step_id", "unknown"))
            step_type = step.get("step_type", "unknown")
            execution_order = step.get("execution_order", 0)
            context = step.get("context", {})

            if step_type == "call":
                task_name = step.get("task_name", "unknown")
                display_name = self._truncate_text(task_name)
                mermaid_code.append(f"    {step_id}[{execution_order}: {display_name}]")
                mermaid_code.append(f"    class {step_id} callNode")
            elif step_type == "conditional_call":
                task_name = step.get("task_name", "unknown")
                condition = context.get("condition", "unknown")
                display_name = self._truncate_text(task_name)
                display_condition = self._truncate_text(condition, 10)
                mermaid_code.append(f"    {step_id}{{{execution_order}: {display_name}<br/>条件: {display_condition}}}")
                mermaid_code.append(f"    class {step_id} conditionalNode")
            elif step_type == "scatter_call":
                task_name = step.get("task_name", "unknown")
                variable = context.get("variable", "unknown")
                display_name = self._truncate_text(task_name)
                display_variable = self._truncate_text(variable, 10)
                mermaid_code.append(f"    {step_id}[/{execution_order}: {display_name}<br/>scatter: {display_variable}/]")
                mermaid_code.append(f"    class {step_id} scatterNode")
            elif step_type == "variable_assignment":
                variable_name = step.get("variable_name", "unknown")
                variable_type = step.get("variable_type", "unknown")
                color_class = self._get_node_color_class(step_type, variable_type)
                display_name = self._truncate_text(variable_name, 10)
                display_type = self._truncate_text(variable_type, 8)
                mermaid_code.append(f"    {step_id}(({execution_order}: {display_name}<br/>{display_type}))")
                mermaid_code.append(f"    class {step_id} {color_class}")

        # 输入参数节点定义
        for input_name in referenced_inputs:
            input_node_id = f"input_{input_name}"
            display_name = self._truncate_text(input_name, 12)
            mermaid_code.append(f"    {input_node_id}(" + display_name + ")")
            mermaid_code.append(f"    class {input_node_id} inputNode")
            all_node_ids.add(input_node_id)

        # 输出参数节点定义
        for output_node_id, out_name in output_nodes:
            display_name = self._truncate_text(out_name, 16)
            mermaid_code.append(f"    {output_node_id}[输出: {display_name}]")
            mermaid_code.append(f"    class {output_node_id} outputNode")
            all_node_ids.add(output_node_id)

        # 连接关系
        connections = []
        for step in execution_sequence:
            step_id = self._sanitize_node_id(step.get("step_id", "unknown"))
            step_type = step.get("step_type", "unknown")
            dependencies = step.get("dependencies", [])

            # 获取有效的依赖关系
            valid_deps = self._get_valid_dependencies(dependencies, all_node_ids)

            # 添加依赖关系（直接依赖，实线）
            for dep in valid_deps:
                dep_id = self._sanitize_node_id(dep)
                connections.append((dep_id, step_id, "solid"))

            # 对于任务节点，添加变量输入连接（直接依赖，实线）
            if step_type in ["call", "conditional_call", "scatter_call"]:
                # 获取任务输入中使用的变量
                input_variables = self._get_task_input_variables(step)
                
                # 调试信息：打印提取到的变量
                if step_id == "count":
                    print(f"DEBUG: count task input variables: {input_variables}")
                
                # 为每个输入变量添加连接
                for var_name in input_variables:
                    # 查找对应的变量节点
                    variable_nodes = self._find_variable_nodes([var_name], all_node_ids)
                    
                    # 调试信息：打印找到的变量节点
                    if step_id == "count":
                        print(f"DEBUG: variable {var_name} -> nodes: {variable_nodes}")
                    
                    # 添加变量节点到任务的连接
                    for var_node in variable_nodes:
                        connections.append((var_node, step_id, "solid"))
                    
                    # 如果是workflow输入参数，连接input节点
                    if self._is_workflow_input(var_name):
                        input_node_id = f"input_{var_name}"
                        connections.append((input_node_id, step_id, "solid"))

            # 对于条件节点，强制将condition变量作为依赖连线（间接依赖，虚线）
            if step_type == "conditional_call":
                context = step.get("context", {})
                condition_expr = context.get("condition", "")
                cond_vars = self._extract_variables_from_expression(condition_expr)
                for cond_var in cond_vars:
                    # assign节点
                    cond_assign_nodes = self._find_variable_nodes([cond_var], all_node_ids)
                    for cond_node in cond_assign_nodes:
                        connections.append((cond_node, step_id, "dashed"))
                    # workflow输入参数
                    if self._is_workflow_input(cond_var):
                        input_node_id = f"input_{cond_var}"
                        connections.append((input_node_id, step_id, "dashed"))

            # 如果没有依赖，连接到前一个步骤（除了第一个）（直接依赖，实线）
            if not valid_deps and step.get("execution_order", 0) > 1:
                prev_step = self._find_previous_step(execution_sequence, step)
                if prev_step:
                    prev_id = self._sanitize_node_id(prev_step.get("step_id", "unknown"))
                    connections.append((prev_id, step_id, "solid"))

        # 添加output连线
        for src, out_node in output_edges:
            connections.append((src, out_node, "solid"))

        # 添加全局参数映射的连线
        connections.extend(global_param_edges)

        # 过滤有效的连接关系
        valid_connections = self._filter_valid_connections([(a, b) for a, b, _ in connections], all_node_ids)
        valid_connections_set = set(valid_connections)

        # 添加连接关系到Mermaid代码，区分实线和虚线（加去重）
        for from_node, to_node, style in connections:
            if (from_node, to_node) not in valid_connections_set:
                continue
            edge = (from_node, to_node)
            if edge in added_edges:
                valid_connections_set.remove((from_node, to_node))
                continue
            if style == "solid":
                mermaid_code.append(f"    {from_node} --> {to_node}")
            elif style == "dashed":
                mermaid_code.append(f"    {from_node} -.-> {to_node}")
            added_edges.add(edge)
            # 防止重复
            valid_connections_set.remove((from_node, to_node))

        return "\n".join(mermaid_code)


def main():
    """主函数"""
    json_file = "docs/wdl/SAW-ST-V8.json"

    generator = FlowchartGenerator(json_file)

    print("生成流程图...")
    flowchart = generator.generate_flowchart()

    # 保存到文件
    with open("workflow_flowchart.mmd", "w", encoding="utf-8") as f:
        f.write(flowchart)

    print("流程图已生成: workflow_flowchart.mmd")

    # 显示流程图
    print("\n=== 流程图 ===")
    print(flowchart)


if __name__ == "__main__":
    main()
