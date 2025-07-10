import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import WDL
from WDL.Expr import Base
from WDL.Tree import Call, Conditional, Decl, Document, Scatter, Task, Workflow


class WDLParseError(Exception):
    """WDL解析错误"""

    pass


class SimpleWDLParser:
    """改进的WDL解析器，支持更完整的WDL特性"""

    def __init__(self, wdl_path: str):
        """
        初始化WDL解析器

        Args:
            wdl_path: WDL文件路径

        Raises:
            WDLParseError: 当文件不存在或解析失败时
        """
        self.wdl_path = Path(wdl_path)
        self.doc: Optional[Document] = None
        self._cached_summary: Optional[Dict] = None

        # 添加表达式解析缓存
        self._expression_cache: Dict[int, Dict[str, Any]] = {}
        self._variables_cache: Dict[int, List[str]] = {}

        # 新增：变量定义和使用追踪
        self.variable_definitions: Dict[str, Dict[str, Any]] = {}
        self.variable_usage: Dict[str, List[Dict[str, Any]]] = {}
        self.assignment_nodes: List[Dict[str, Any]] = []
        self.dependency_graph: Dict[str, Dict[str, Any]] = {}

        # 验证文件存在性
        if not self.wdl_path.exists():
            raise WDLParseError(f"WDL文件不存在: {wdl_path}")

        # 解析WDL文件
        self._parse_wdl_file()

    def _parse_wdl_file(self):
        """解析WDL文件，包含完整的错误处理"""
        try:
            # 尝试使用更多参数的版本
            self.doc = WDL.load(str(self.wdl_path), check_quant=True)
        except TypeError:
            try:
                # 如果不支持 check_quant 参数，使用基础版本
                self.doc = WDL.load(str(self.wdl_path))
            except Exception as e:
                raise WDLParseError(f"解析WDL文件时发生未知错误: {e}")
        except Exception as e:
            raise WDLParseError(f"解析WDL文件时发生未知错误: {e}")

        # 验证文档是否包含工作流
        if not self.doc.workflow:
            raise WDLParseError("WDL文件中未找到工作流定义")

    def get_workflow_summary(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取工作流摘要，支持缓存

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            工作流摘要字典
        """
        if self._cached_summary is not None and not force_refresh:
            return self._cached_summary

        if not self.doc or not self.doc.workflow:
            return {}

        workflow = self.doc.workflow

        # 1. 分析变量定义和使用
        self._analyze_variables()

        # 2. 构建依赖图
        self._build_dependency_graph()

        # 3. 收集所有信息
        calls = self._get_all_calls()
        conditionals = self._get_conditionals()
        scatters = self._get_scatters()
        tasks = self._get_tasks_used()

        summary = {
            "name": workflow.name,
            "inputs": self._parse_workflow_inputs(workflow.inputs),
            "outputs": self._parse_workflow_outputs(workflow.outputs),
            "tasks_used": tasks,
            "calls": calls,
            "conditionals": conditionals,
            "scatters": scatters,
            "variable_definitions": self.variable_definitions,
            "variable_usage": self.variable_usage,
            "assignment_nodes": self.assignment_nodes,
            "dependency_graph": self.dependency_graph,
            "execution_structure": self._build_execution_structure(calls, conditionals, scatters),
            "imports": self._get_imports(),
            "tasks": self._get_task_definitions(),
        }

        self._cached_summary = summary
        return summary

    def _safe_parse(self, parse_func, *args, **kwargs):
        """安全的解析函数，统一错误处理

        Args:
            parse_func: 要执行的解析函数
            *args, **kwargs: 传递给解析函数的参数

        Returns:
            解析结果或错误信息
        """
        try:
            return parse_func(*args, **kwargs)
        except Exception as e:
            return {"type": "error", "error": str(e)}

    def _parse_workflow_inputs(self, inputs: List[Decl] | None) -> List[Dict[str, Any]]:
        """解析工作流输入，使用安全解析"""
        parsed_inputs = []

        if inputs is None:
            return []

        for inp in inputs:

            def parse_input():
                input_info = {
                    "name": inp.name,
                    "type": str(inp.type),
                    "optional": self._safe_getattr(inp.type, "optional", False),
                    "default_value": None,
                }

                if hasattr(inp, "expr") and inp.expr is not None:
                    input_info["default_value"] = self._parse_expression_value(inp.expr)

                return input_info

            result = self._safe_parse(parse_input)
            if isinstance(result, dict) and result.get("type") == "error":
                self._safe_warning(f"解析输入 {self._safe_getattr(inp, 'name', 'unknown')} 时出错: {result['error']}")
                continue
            parsed_inputs.append(result)

        return parsed_inputs

    def _parse_workflow_outputs(self, outputs: List[Decl] | None) -> List[Dict[str, Any]]:
        """解析工作流输出，使用安全解析"""
        parsed_outputs = []

        if outputs is None:
            return []

        for outp in outputs:

            def parse_output():
                return {
                    "name": outp.name,
                    "type": str(outp.type),
                    "expression": self._parse_expression_value(outp.expr) if outp.expr else None,
                }

            result = self._safe_parse(parse_output)
            if isinstance(result, dict) and result.get("type") == "error":
                self._safe_warning(f"解析输出 {self._safe_getattr(outp, 'name', 'unknown')} 时出错: {result['error']}")
                continue
            parsed_outputs.append(result)

        return parsed_outputs

    def _parse_expression_value(self, expr) -> Any:
        """解析表达式的值，保持原始类型

        这个方法用于解析WDL表达式，并尽可能保持原始数据类型：

        Args:
            expr: WDL表达式对象

        Returns:
            解析后的值，可能是原始类型或字符串
        """
        try:
            if expr is None:
                return None

            # 如果是字面量，尝试解析为原始类型
            if hasattr(expr, "value"):
                return expr.value
            # 对于复杂表达式（变量引用、条件表达式、函数调用等），
            # 返回字符串表示以保持表达式的完整性和可读性
            if hasattr(expr, "literal") and expr.literal is not None:
                return expr.literal.value
            return str(expr)
        except Exception as e:
            return f"<expression_error: {str(e)}>"

    def _get_tasks_used(self) -> List[str]:
        """获取工作流中使用的所有任务"""
        tasks = set()

        def collect_tasks(elements):
            for elem in elements:
                if isinstance(elem, Call):
                    if elem.callee is not None:
                        tasks.add(elem.callee.name)
                elif hasattr(elem, "body") and elem.body:
                    collect_tasks(elem.body)

        if self.doc and self.doc.workflow:
            collect_tasks(self.doc.workflow.body)

        return sorted(list(tasks))

    def _get_all_calls(self) -> List[Dict[str, Any]]:
        """获取所有调用信息，改进的上下文管理"""
        calls = []
        context_stack = []
        call_counter = 0  # 用于生成唯一ID
        conditional_counter = 0  # 用于生成条件块ID

        def collect_calls(elements, context_info=None):
            nonlocal call_counter, conditional_counter
            if context_info is None:
                context_info = {"type": "workflow", "id": "root", "level": 0}

            for elem in elements:
                if isinstance(elem, Call):
                    # 为每个任务调用分配唯一的ID
                    unique_id = f"call_{call_counter}_{elem.name}"
                    call_counter += 1

                    # 更新上下文ID
                    current_context = context_info.copy()
                    if current_context["type"] == "workflow":
                        current_context["id"] = unique_id
                        # 工作流级别的调用，parent指向root
                        current_context["parent"] = "root"
                    else:
                        # 非工作流级别的调用保持原有的parent
                        pass

                    call_info = {
                        "name": elem.name,
                        "task": elem.callee.name if elem.callee is not None else None,
                        "context": current_context,
                        "inputs": self._parse_call_inputs(elem.inputs) if elem.inputs else {},
                        "outputs": self._parse_call_outputs(elem.callee) if elem.callee else {},
                        "position": len(calls),
                    }
                    calls.append(call_info)
                elif isinstance(elem, Conditional):
                    # 创建新的上下文，使用统一的条件ID
                    conditional_counter += 1
                    cond_id = f"conditional_{conditional_counter}"
                    new_context = {
                        "type": "conditional",
                        "id": cond_id,
                        "level": context_info["level"] + 1,
                        "condition": self._parse_expression_value(elem.expr),
                        "parent": context_info["id"],
                    }
                    context_stack.append(new_context)
                    collect_calls(elem.body, new_context)
                    context_stack.pop()
                elif isinstance(elem, Scatter):
                    # 创建新的上下文，使用统一的scatter ID格式
                    scatter_id = f"scatter_{elem.variable}"
                    new_context = {
                        "type": "scatter",
                        "id": scatter_id,
                        "level": context_info["level"] + 1,
                        "variable": elem.variable,
                        "collection": self._parse_expression_value(elem.expr),
                        "parent": context_info["id"],
                    }
                    context_stack.append(new_context)
                    collect_calls(elem.body, new_context)
                    context_stack.pop()
                elif hasattr(elem, "body") and elem.body:
                    collect_calls(elem.body, context_info)

        if self.doc and self.doc.workflow:
            collect_calls(self.doc.workflow.body)

        return calls

    def _parse_call_inputs(self, inputs) -> Dict[str, Any]:
        """解析调用输入，改进的表达式处理"""
        parsed_inputs = {}

        for key, expr in inputs.items():
            try:
                parsed_inputs[key] = self._parse_expression_advanced(expr)
            except Exception as e:
                parsed_inputs[key] = {"type": "error", "error": str(e), "raw": self._parse_expression_value(expr)}

        return parsed_inputs

    def _parse_call_outputs(self, task) -> Dict[str, Any]:
        """解析调用输出，从任务定义中获取输出信息"""
        parsed_outputs = {}

        if not task or not hasattr(task, "outputs"):
            return parsed_outputs

        try:
            for output in task.outputs:
                output_info = {
                    "name": output.name,
                    "type": str(output.type),
                    "expression": self._parse_expression_value(output.expr) if output.expr else None,
                }
                parsed_outputs[output.name] = output_info
        except Exception as e:
            self._safe_warning(f"解析调用输出时出错: {e}")

        return parsed_outputs

    def _parse_expression_advanced(self, expr: Base) -> Dict[str, Any]:
        """优化的表达式解析，使用缓存和统一映射表"""
        try:
            # 使用对象ID作为缓存键
            expr_id = id(expr)

            # 检查表达式缓存
            if expr_id in self._expression_cache:
                return self._expression_cache[expr_id]

            expr_type = type(expr).__name__

            # 缓存表达式字符串和变量提取结果
            expr_str = str(expr)
            variables = self._extract_variables_from_ast(expr)

            # 统一的表达式类型映射表
            expression_handlers = {
                # 基础类型
                "Get": lambda: {"type": "variable", "name": self._extract_variable_name_from_get(expr)},
                "String": lambda: self._parse_string_expression(expr_str),
                "Int": lambda: {"type": "number", "value": expr_str},
                "Float": lambda: {"type": "number", "value": expr_str},
                "Boolean": lambda: {"type": "boolean", "value": expr_str},
                # 算术操作符
                "Add": lambda: self._create_operator_result("operation", "+", expr_str, variables),
                "Sub": lambda: self._create_operator_result("operation", "-", expr_str, variables),
                "Mul": lambda: self._create_operator_result("operation", "*", expr_str, variables),
                "Div": lambda: self._create_operator_result("operation", "/", expr_str, variables),
                "Mod": lambda: self._create_operator_result("operation", "%", expr_str, variables),
                # 逻辑操作符
                "LogicalAnd": lambda: self._create_operator_result("logical", "logicaland", expr_str, variables),
                "LogicalOr": lambda: self._create_operator_result("logical", "logicalor", expr_str, variables),
                "LogicalNot": lambda: self._create_operator_result("logical", "logicalnot", expr_str, variables),
                # 比较操作符
                "Eq": lambda: self._create_operator_result("comparison", "eq", expr_str, variables),
                "Ne": lambda: self._create_operator_result("comparison", "ne", expr_str, variables),
                "Lt": lambda: self._create_operator_result("comparison", "lt", expr_str, variables),
                "Lte": lambda: self._create_operator_result("comparison", "lte", expr_str, variables),
                "Gt": lambda: self._create_operator_result("comparison", "gt", expr_str, variables),
                "Gte": lambda: self._create_operator_result("comparison", "gte", expr_str, variables),
                # 复合类型
                "ArrayAccess": lambda: self._create_operator_result("array_access", None, expr_str, variables),
                "Array": lambda: self._create_operator_result("array", None, expr_str, variables),
                "Pair": lambda: self._create_operator_result("pair", None, expr_str, variables),
                "IfThenElse": lambda: self._create_operator_result("conditional", None, expr_str, variables),
            }

            # 直接查找处理器
            if expr_type in expression_handlers:
                result = expression_handlers[expr_type]()
                # 缓存结果
                self._expression_cache[expr_id] = result
                return result

            # 特殊处理Apply（函数调用）
            if expr_type == "Apply":
                result = self._handle_apply_expression(expr, expr_str, variables)
                # 缓存结果
                self._expression_cache[expr_id] = result
                return result

            # 默认情况
            result = {"type": "expression", "expression": expr_str, "variables": variables}
            # 缓存结果
            self._expression_cache[expr_id] = result
            return result

        except Exception as e:
            error_result = {"type": "error", "error": str(e)}
            # 缓存错误结果以避免重复解析
            self._expression_cache[expr_id] = error_result
            return error_result

    def _create_operator_result(self, op_type: str, operator: Optional[str], expr_str: str, variables: List[str]) -> Dict[str, Any]:
        """创建操作符结果的统一方法"""
        result = {"type": op_type, "expression": expr_str, "variables": variables}
        if operator:
            result["operator"] = operator
        return result

    def _handle_apply_expression(self, expr, expr_str: str, variables: List[str]) -> Dict[str, Any]:
        """处理Apply表达式的特殊逻辑"""
        function_name = self._safe_getattr(expr, "function")

        # 检查是否是操作符函数
        operators = {"+", "-", "*", "/", "%"}
        if function_name and function_name in operators:
            return self._create_operator_result("operation", str(function_name), expr_str, variables)

        # 普通函数调用
        function_name_str = self._extract_function_name_from_apply(expr)
        return {"type": "function", "name": function_name_str, "expression": expr_str, "variables": variables}

    def _extract_token_value(self, token_obj) -> str:
        """从Token对象中提取字符串值"""
        if token_obj is None:
            return ""
        try:
            if hasattr(token_obj, "value"):
                return str(token_obj.value)
            elif hasattr(token_obj, "text"):
                return str(token_obj.text)
            elif hasattr(token_obj, "source"):
                return str(token_obj.source)
            elif hasattr(token_obj, "string"):
                return str(token_obj.string)
            elif isinstance(token_obj, str):
                return token_obj
            else:
                return str(token_obj)
        except Exception as e:
            print(f"警告: 提取Token值失败: {e}")
            return str(token_obj)

    def _extract_variable_name_from_get(self, expr) -> str:
        """从Get表达式中提取变量名"""
        try:
            if hasattr(expr, "name"):
                return self._extract_token_value(expr.name)
            elif hasattr(expr, "expr"):
                if hasattr(expr.expr, "name"):
                    return str(expr.expr.name)
                else:
                    return str(expr.expr)
            else:
                return str(expr)
        except Exception as e:
            print(f"警告: 提取变量名失败: {e}")
            return str(expr)

    def _extract_function_name_from_apply(self, expr) -> str:
        """从Apply表达式中提取函数名"""
        try:
            if hasattr(expr, "function"):
                return str(expr.function)
            elif hasattr(expr, "name"):
                return str(expr.name)
            else:
                return "unknown"
        except Exception:
            return "unknown"

    def _traverse_ast(self, node, visitor_func):
        """通用AST遍历器

        Args:
            node: AST节点
            visitor_func: 访问函数，接收节点和深度参数
        """

        def traverse(node, depth=0):
            if node is None:
                return

            visitor_func(node, depth)

            # 获取所有可能的子节点属性
            child_attrs = [
                "left",
                "right",
                "expr",
                "condition",
                "then_expr",
                "else_expr",
                "array",
                "index",
                "arguments",
                "items",
                "left_expr",
                "right_expr",
                "body",
            ]

            for attr_name in child_attrs:
                if hasattr(node, attr_name):
                    attr_value = getattr(node, attr_name)
                    if attr_value is not None:
                        if isinstance(attr_value, list):
                            for item in attr_value:
                                traverse(item, depth + 1)
                        else:
                            traverse(attr_value, depth + 1)

        traverse(node)

    def _extract_variables_from_ast(self, expr) -> List[str]:
        """从AST中提取变量名，使用缓存优化"""
        # 使用对象ID作为缓存键
        expr_id = id(expr)

        # 检查缓存
        if expr_id in self._variables_cache:
            return self._variables_cache[expr_id]

        variables = set()

        def visitor(node, depth):
            if hasattr(node, "__class__") and node.__class__.__name__ == "Get":
                variable_name = self._extract_variable_name_from_get(node)
                if variable_name and variable_name not in variables:
                    variables.add(str(variable_name))

        try:
            self._traverse_ast(expr, visitor)
            result = sorted(list(variables))
            # 缓存结果
            self._variables_cache[expr_id] = result
            return result
        except Exception as e:
            print(f"警告: AST遍历失败: {e}")
            return []

    def _extract_variables_from_string_interpolation(self, string_value: str) -> List[str]:
        """从字符串插值表达式中提取变量名"""
        variables = set()

        # 匹配 ~{变量名} 格式
        pattern = r"~\{([^}]+)\}"
        matches = re.findall(pattern, string_value)

        for match in matches:
            # 简单的变量名提取，去除空格
            var_name = match.strip()
            # 如果包含复杂表达式，只提取简单的变量名
            if " " not in var_name and "+" not in var_name and "-" not in var_name:
                variables.add(var_name)
            else:
                # 对于复杂表达式，尝试提取所有单词（可能的变量名）
                words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", var_name)
                variables.update(words)

        return sorted(list(variables))

    def _parse_string_expression(self, expr_str: str) -> Dict[str, Any]:
        """解析字符串表达式，检查是否为字符串插值"""
        string_value = expr_str.strip('"').strip("'")
        if "~{" in string_value and "}" in string_value:
            # 字符串插值表达式，提取变量
            variables = self._extract_variables_from_string_interpolation(string_value)
            return {"type": "string_interpolation", "expression": string_value, "variables": variables}
        else:
            return {"type": "string", "value": string_value}

    def _collect_calls_from_elements(self, elements) -> List[Dict[str, Any]]:
        """从元素列表中收集调用信息"""
        calls = []

        def collect(elements):
            for elem in elements:
                if isinstance(elem, Call):
                    calls.append({"name": elem.name, "task": elem.callee.name if elem.callee is not None else None})
                elif hasattr(elem, "body") and elem.body:
                    collect(elem.body)

        collect(elements)
        return calls

    def clear_caches(self):
        """清理所有缓存"""
        self._cached_summary = None
        self._expression_cache.clear()
        self._variables_cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            "expression_cache_size": len(self._expression_cache),
            "variables_cache_size": len(self._variables_cache),
            "summary_cached": self._cached_summary is not None,
        }

    def _safe_getattr(self, obj, attr_name, default=None):
        """安全地获取对象属性"""
        try:
            return getattr(obj, attr_name, default)
        except Exception:
            return default

    def _safe_warning(self, message: str):
        """统一的警告输出"""
        print(f"警告: {message}")

    def _analyze_variables(self):
        """分析变量定义和使用"""
        if not self.doc or not self.doc.workflow:
            return

        # 遍历工作流体，收集变量定义
        self._collect_variable_definitions(self.doc.workflow.body)

        # 遍历所有调用，收集变量使用
        self._collect_variable_usage(self.doc.workflow.body)

    def _collect_variable_definitions(self, elements):
        """收集变量定义

        遍历工作流元素，收集所有变量声明和赋值信息。
        使用 _parse_expression_value 方法解析表达式，保持原始数据类型。

        收集的信息包括：
        - 变量名称和类型
        - 表达式值（保持原始类型）
        - 依赖关系
        - 位置信息

        同时创建赋值节点，用于构建执行依赖图。
        """
        for elem in elements:
            if isinstance(elem, Decl):
                # 变量声明
                var_name = elem.name
                var_type = str(elem.type)
                # 使用新的表达式解析方法，保持原始数据类型
                var_expr = self._parse_expression_value(elem.expr) if elem.expr else None

                self.variable_definitions[var_name] = {
                    "type": var_type,
                    "expression": var_expr,
                    "location": "workflow_level",
                    "dependencies": self._extract_variables_from_expression(elem.expr) if elem.expr else [],
                }

                # 创建赋值节点，用于依赖分析
                assignment_node = {
                    "type": "variable_assignment",
                    "name": var_name,
                    "variable_type": var_type,
                    "expression": var_expr,
                    "dependencies": self._extract_variables_from_expression(elem.expr) if elem.expr else [],
                    "location": "workflow_level",
                }
                self.assignment_nodes.append(assignment_node)

            elif isinstance(elem, Conditional):
                # 条件块内的变量
                self._collect_variable_definitions(elem.body)

            elif isinstance(elem, Scatter):
                # Scatter块内的变量
                self._collect_variable_definitions(elem.body)

    def _collect_variable_usage(self, elements):
        """收集变量使用"""
        for elem in elements:
            if isinstance(elem, Call):
                # 调用中的变量使用
                inputs = elem.inputs if hasattr(elem, "inputs") else {}
                for input_name, input_expr in inputs.items():
                    variables = self._extract_variables_from_expression(input_expr)
                    for var in variables:
                        if var not in self.variable_usage:
                            self.variable_usage[var] = []
                        self.variable_usage[var].append(
                            {"call": elem.name, "input": input_name, "expression": self._parse_expression_value(input_expr)}
                        )

            elif isinstance(elem, Conditional):
                # 条件块内的变量使用
                self._collect_variable_usage(elem.body)

            elif isinstance(elem, Scatter):
                # Scatter块内的变量使用
                self._collect_variable_usage(elem.body)

    def _extract_variables_from_expression(self, expr) -> List[str]:
        """从表达式中提取变量

        使用AST遍历来准确提取变量引用，避免将字符串字面量误识别为变量。
        """
        if not expr:
            return []

        # 使用更准确的AST遍历方法
        return self._extract_variables_from_ast(expr)

    def _build_dependency_graph(self):
        """构建依赖图"""
        # 初始化依赖图
        all_nodes = set()

        # 添加所有赋值节点
        for assignment in self.assignment_nodes:
            node_name = f"assign_{assignment['name']}"
            all_nodes.add(node_name)
            self.dependency_graph[node_name] = {"type": "variable_assignment", "dependencies": assignment["dependencies"], "info": assignment}

        # 添加所有调用节点
        calls = self._get_all_calls()
        for call in calls:
            node_name = call["name"]
            all_nodes.add(node_name)
            self.dependency_graph[node_name] = {"type": "call", "dependencies": call.get("dependencies", []), "info": call}

        # 构建依赖关系
        for node_name, node_info in self.dependency_graph.items():
            dependencies = []
            for dep in node_info["dependencies"]:
                # 检查是否是变量赋值
                if f"assign_{dep}" in all_nodes:
                    dependencies.append(f"assign_{dep}")
                # 检查是否是任务调用
                elif dep in all_nodes:
                    dependencies.append(dep)

            node_info["dependencies"] = dependencies

    def _traverse_workflow_elements(self, elements, visitor_func, parent_context=None):
        """通用的工作流元素遍历器

        Args:
            elements: 要遍历的元素列表
            visitor_func: 访问函数，接收元素和父上下文
            parent_context: 父上下文信息
        """
        if not elements:
            return

        for elem in elements:
            visitor_func(elem, parent_context)

            # 递归处理有body的元素
            if hasattr(elem, "body") and elem.body:
                self._traverse_workflow_elements(elem.body, visitor_func, parent_context)

    def _get_conditionals(self) -> List[Dict[str, Any]]:
        """获取所有条件块，使用通用遍历器"""
        conditionals = []
        conditional_counter = 0

        def visit_conditional(elem, parent_context):
            nonlocal conditional_counter

            if isinstance(elem, Conditional):
                conditional_counter += 1
                calls_in_conditional = self._collect_calls_from_elements(elem.body)

                conditionals.append(
                    {
                        "id": f"conditional_{conditional_counter}",
                        "condition": self._parse_expression_value(elem.expr),
                        "calls_inside": len(calls_in_conditional),
                        "calls": calls_in_conditional,
                        "parent": parent_context,
                    }
                )

                # 递归处理嵌套结构，传递当前条件块的ID作为parent_context
                self._traverse_workflow_elements(elem.body, visit_conditional, f"conditional_{conditional_counter}")

        if self.doc and self.doc.workflow:
            # 顶层条件块的parent_context为"root"
            self._traverse_workflow_elements(self.doc.workflow.body, visit_conditional, "root")

        return conditionals

    def _get_scatters(self) -> List[Dict[str, Any]]:
        """获取所有scatter块，使用通用遍历器"""
        scatters = []

        def visit_scatter(elem, parent_context):
            if isinstance(elem, Scatter):
                calls_in_scatter = self._collect_calls_from_elements(elem.body)

                scatters.append(
                    {
                        "variable": elem.variable,
                        "collection": self._parse_expression_value(elem.expr),
                        "calls_inside": len(calls_in_scatter),
                        "calls": calls_in_scatter,
                        "parent": parent_context,
                    }
                )

                # 递归处理嵌套结构，传递当前scatter的ID作为parent_context
                self._traverse_workflow_elements(elem.body, visit_scatter, f"scatter_{elem.variable}")

        if self.doc and self.doc.workflow:
            # 顶层scatter块的parent_context为"root"
            self._traverse_workflow_elements(self.doc.workflow.body, visit_scatter, "root")

        return scatters

    def _build_execution_structure(self, calls: List, conditionals: List, scatters: List) -> Dict[str, Any]:
        """构建执行结构，清晰表示执行顺序"""
        structure = {"workflow_level_calls": [], "conditional_blocks": [], "scatter_blocks": [], "execution_sequence": []}  # 新的执行序列

        # 按上下文分组调用
        calls_by_context = {}
        for call in calls:
            context_id = call["context"]["id"]
            if context_id not in calls_by_context:
                calls_by_context[context_id] = []
            calls_by_context[context_id].append(call)

        # 工作流级别的调用
        structure["workflow_level_calls"] = [call for call in calls if call["context"]["type"] == "workflow" and call["context"]["level"] == 0]

        # 条件块
        for conditional in conditionals:
            context_id = conditional["id"]
            conditional_structure = {
                "id": context_id,
                "condition": conditional["condition"],
                "calls": conditional["calls"],
                "detailed_calls": calls_by_context.get(context_id, []),
            }
            structure["conditional_blocks"].append(conditional_structure)

        # Scatter块
        for scatter in scatters:
            context_id = f"scatter_{scatter['variable']}"
            scatter_structure = {
                "variable": scatter["variable"],
                "collection": scatter["collection"],
                "calls_inside": scatter["calls_inside"],
                "calls": scatter["calls"],
                "detailed_calls": calls_by_context.get(context_id, []),
            }
            structure["scatter_blocks"].append(scatter_structure)

        # 构建清晰的执行序列
        structure["execution_sequence"] = self._build_execution_sequence(calls, conditionals, scatters)

        return structure

    def _build_execution_sequence(self, calls: List, conditionals: List, scatters: List) -> List[Dict[str, Any]]:
        """构建增强的执行序列，包含变量赋值和调用"""
        sequence = []

        # 1. 添加变量赋值节点
        for assignment in self.assignment_nodes:
            sequence_item = {
                "step_type": "variable_assignment",
                "step_id": f"assign_{assignment['name']}",
                "variable_name": assignment["name"],
                "variable_type": assignment["variable_type"],
                "expression": assignment["expression"],
                "dependencies": assignment["dependencies"],
                "execution_order": len(sequence) + 1,
                "context": {"type": "workflow_level", "parent": "root"},
            }
            sequence.append(sequence_item)

        # 2. 添加调用节点
        # 按位置排序调用
        sorted_calls = sorted(calls, key=lambda x: x.get("position", 0))

        # 创建条件块和scatter块的映射
        conditional_map = {cond["id"]: cond for cond in conditionals}
        scatter_map = {f"scatter_{scatter['variable']}": scatter for scatter in scatters}

        for call in sorted_calls:
            context = call["context"]
            context_type = context["type"]

            if context_type == "workflow":
                # 工作流级别的直接调用
                sequence_item = {
                    "step_type": "call",
                    "step_id": call["name"],
                    "task_name": call["task"],
                    "execution_order": len(sequence) + 1,
                    "context": {"type": "workflow_level", "parent": context["parent"]},
                    "dependencies": self._extract_dependencies(call),
                    "inputs": call["inputs"],
                    "outputs": call["outputs"],
                }
                sequence.append(sequence_item)

            elif context_type == "conditional":
                # 条件块内的调用
                conditional_id = context["id"]
                conditional_info = conditional_map.get(conditional_id, {})

                sequence_item = {
                    "step_type": "conditional_call",
                    "step_id": call["name"],
                    "task_name": call["task"],
                    "execution_order": len(sequence) + 1,
                    "context": {
                        "type": "conditional",
                        "conditional_id": conditional_id,
                        "condition": conditional_info.get("condition", "unknown"),
                        "parent": context["parent"],
                    },
                    "dependencies": self._extract_dependencies(call),
                    "inputs": call["inputs"],
                    "outputs": call["outputs"],
                }
                sequence.append(sequence_item)

            elif context_type == "scatter":
                # Scatter块内的调用
                scatter_id = context["id"]
                scatter_info = scatter_map.get(scatter_id, {})

                sequence_item = {
                    "step_type": "scatter_call",
                    "step_id": call["name"],
                    "task_name": call["task"],
                    "execution_order": len(sequence) + 1,
                    "context": {
                        "type": "scatter",
                        "scatter_id": scatter_id,
                        "variable": scatter_info.get("variable", "unknown"),
                        "collection": scatter_info.get("collection", "unknown"),
                        "parent": context["parent"],
                    },
                    "dependencies": self._extract_dependencies(call),
                    "inputs": call["inputs"],
                    "outputs": call["outputs"],
                }
                sequence.append(sequence_item)

        return sequence

    def _extract_dependencies(self, call: Dict[str, Any]) -> List[str]:
        """提取任务的依赖关系"""
        dependencies = []

        # 从输入参数中提取依赖
        inputs = call.get("inputs", {})
        for input_name, input_info in inputs.items():
            if input_info.get("type") == "variable":
                var_name = input_info.get("name", "")
                # 检查是否是其他任务的输出
                if "." in var_name:
                    task_name = var_name.split(".")[0]
                    dependencies.append(task_name)

        return list(set(dependencies))  # 去重

    def _get_imports(self) -> List[Dict[str, str]]:
        """获取导入信息"""
        imports = []

        if self.doc and hasattr(self.doc, "imports"):
            for imp in self.doc.imports:
                import_info = {
                    "uri": self._safe_getattr(imp, "uri", ""),
                    "namespace": self._safe_getattr(imp, "namespace", ""),
                    "doc": self._safe_getattr(imp, "doc"),
                }
                imports.append(import_info)

        return imports

    def _get_task_definitions(self) -> List[Dict[str, Any]]:
        """获取任务定义"""
        tasks = []

        if self.doc and hasattr(self.doc, "tasks"):
            for task in self.doc.tasks:
                task_info = {
                    "name": task.name,
                    "inputs": self._parse_task_inputs(task.inputs) if hasattr(task, "inputs") else [],
                    "outputs": self._parse_task_outputs(task.outputs) if hasattr(task, "outputs") else [],
                    "runtime": self._parse_runtime(task.runtime) if hasattr(task, "runtime") else {},
                    "meta": self._safe_getattr(task, "meta", {}),
                }
                tasks.append(task_info)

        return tasks

    def _parse_task_inputs(self, inputs: Optional[List[Decl]]) -> List[Dict[str, Any]]:
        """解析任务输入"""
        parsed_inputs = []

        if inputs is not None:
            for inp in inputs:
                try:
                    input_info = {"name": inp.name, "type": str(inp.type), "optional": self._safe_getattr(inp.type, "optional", False)}
                    parsed_inputs.append(input_info)
                except Exception as e:
                    self._safe_warning(f"解析任务输入时出错: {e}")
                    continue

        return parsed_inputs

    def _parse_task_outputs(self, outputs: List[Decl]) -> List[Dict[str, Any]]:
        """解析任务输出"""
        parsed_outputs = []

        for outp in outputs:
            try:
                output_info = {
                    "name": outp.name,
                    "type": str(outp.type),
                    "expression": self._parse_expression_value(outp.expr) if outp.expr else None,
                }
                parsed_outputs.append(output_info)
            except Exception as e:
                self._safe_warning(f"解析任务输出时出错: {e}")
                continue

        return parsed_outputs

    def _parse_runtime(self, runtime: Dict[str, Base]) -> Dict[str, Any]:
        """解析运行时配置，统一用表达式解析器"""
        if not runtime:
            return {}

        runtime_info = {}
        try:
            for key, value in runtime.items():
                runtime_info[key] = self._parse_expression_advanced(value)
        except Exception as e:
            self._safe_warning(f"解析运行时配置时出错: {e}")

        return runtime_info

    def validate_workflow(self) -> Dict[str, Any]:
        """验证工作流"""
        try:
            # 基本验证
            if not self.doc:
                return {"valid": False, "errors": ["文档未加载"]}

            if not self.doc.workflow:
                return {"valid": False, "errors": ["未找到工作流定义"]}

            # 检查是否有任务定义
            if not self.doc.tasks:
                return {"valid": False, "errors": ["未找到任务定义"]}

            # 检查工作流中引用的任务是否存在
            workflow_tasks = set(self._get_tasks_used())
            available_tasks = {task.name for task in self.doc.tasks}
            missing_tasks = workflow_tasks - available_tasks

            if missing_tasks:
                return {"valid": False, "errors": [f"工作流引用了未定义的任务: {', '.join(missing_tasks)}"]}

            return {"valid": True, "errors": []}

        except Exception as e:
            return {"valid": False, "errors": [f"验证过程中发生错误: {e}"]}


if __name__ == "__main__":
    print("开始解析WDL文件...")
    # 使用简化的解析器
    parser = SimpleWDLParser("/data/agent_backend/docs/wdl/SAW-ST-V8.wdl")
    print("解析器创建成功")

    summary = parser.get_workflow_summary()

    summary = json.dumps(summary, indent=4)

    with open("/data/agent_backend/docs/wdl/SAW-ST-V8.json", "w") as f:
        f.write(summary)
