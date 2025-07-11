import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import WDL
from WDL.Expr import Base
from WDL.Tree import Call, Conditional, Decl, Document, Gather, Scatter, Task, Workflow, WorkflowNode, DocImport


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

    def get_workflow_summary(self) -> Dict[str, Any]:

        if not self.doc or not self.doc.workflow:
            return {}

        summary = {
            "version": self._parse_version(self.doc),
            "workflow": self._parse_workflow(self.doc.workflow),
            "tasks": self._parse_tasks(self.doc.tasks),
            "imports": self._parse_imports(self.doc.imports),
            "structs": self._parse_structs(self.doc),
            "global_variables": self._parse_global_variables(self.doc),
        }

        return summary

    def _parse_version(self, doc: Document) -> Dict[str, Any]:
        """解析WDL版本信息"""
        return {
            "version": doc.effective_wdl_version,
            "source_location": str(doc.pos) if hasattr(doc, "pos") else None,
        }

    def _parse_structs(self, doc: Document) -> List[Dict[str, Any]]:
        """解析结构体定义 - 使用miniwdl内置的解析结果"""
        structs = []

        # 使用miniwdl的内置方法获取结构体定义
        if hasattr(doc, "struct_typedefs") and doc.struct_typedefs:
            # 直接访问结构体定义
            struct_defs = doc.struct_typedefs

            # 使用 miniwdl 的字符串表示来获取结构体信息
            struct_info = {
                "name": "parsed_structs",
                "raw_content": str(struct_defs),
                "type": type(struct_defs).__name__,
                "available_methods": [method for method in dir(struct_defs) if not method.startswith("_")],
            }
            structs.append(struct_info)

        return structs

    def _parse_global_variables(self, doc: Document) -> List[Dict[str, Any]]:
        """解析全局变量定义 - 使用miniwdl内置的解析结果"""
        global_vars = []

        # 使用miniwdl的内置方法获取全局变量定义
        # 检查文档的可用属性
        doc_attrs = [attr for attr in dir(doc) if not attr.startswith("_")]

        # 查找可能的全局变量相关属性
        global_related_attrs = [attr for attr in doc_attrs if "env" in attr.lower() or "global" in attr.lower()]

        if global_related_attrs:
            env_info = {
                "name": "document_globals",
                "type": type(doc).__name__,
                # "available_attrs": doc_attrs,
                "global_related_attrs": global_related_attrs,
            }
            global_vars.append(env_info)

        # 检查是否有顶层声明
        if hasattr(doc, "workflow") and doc.workflow and hasattr(doc.workflow, "inputs"):
            # 工作流输入可以视为全局可访问的变量
            for input_decl in doc.workflow.inputs or []:
                var_info = self._parse_decl(input_decl)
                var_info["scope"] = "workflow_input"
                global_vars.append(var_info)

        return global_vars

    def _parse_workflow(self, workflow: Workflow) -> Dict[str, Any]:
        workflow_info = {
            "name": workflow.name,
            "inputs": self._parse_decls(workflow.inputs),
            "outputs": self._parse_decls(workflow.outputs),
            "body": self._parse_workflow_nodes(workflow.body),
            "parameter_meta": workflow.parameter_meta,
            "meta": workflow.meta,
            "effective_wdl_version": workflow.effective_wdl_version,
        }
        return workflow_info

    def _parse_imports(self, imports: List[DocImport]) -> List[Dict[str, Any]]:
        """解析导入列表，提取所有导入的详细信息"""
        parsed_imports = []

        for doc_import in imports:
            import_info = self._parse_import(doc_import)
            parsed_imports.append(import_info)

        return parsed_imports

    def _parse_import(self, doc_import: DocImport) -> Dict[str, Any]:
        """解析单个导入语句，提取导入的详细信息"""
        import_info = {
            "uri": doc_import.uri,  # 导入的文件路径
            "namespace": doc_import.namespace,  # 导入的命名空间
            "pos": str(doc_import.pos) if hasattr(doc_import, "pos") else None,  # 位置信息
            "imported_tasks": [],  # 导入的任务列表
            "imported_workflows": [],  # 导入的工作流列表
        }

        # 如果存在导入的文档对象，解析其中的任务和工作流
        if hasattr(doc_import, "doc") and doc_import.doc is not None:
            imported_doc = doc_import.doc

            # 解析导入文档中的任务
            if hasattr(imported_doc, "tasks") and imported_doc.tasks:
                for task in imported_doc.tasks:
                    import_info["imported_tasks"].append(
                        {
                            "name": task.name,
                            "full_name": f"{doc_import.namespace}.{task.name}" if doc_import.namespace else task.name,
                            "inputs": self._parse_decls(task.inputs),
                            "outputs": self._parse_decls(task.outputs),
                            "runtime": self._parse_runtime(task.runtime) if task.runtime else {},
                            "parameter_meta": task.parameter_meta,
                            "meta": task.meta,
                        }
                    )

            # 解析导入文档中的工作流
            if hasattr(imported_doc, "workflow") and imported_doc.workflow:
                workflow = imported_doc.workflow
                import_info["imported_workflows"].append(
                    {
                        "name": workflow.name,
                        "full_name": f"{doc_import.namespace}.{workflow.name}" if doc_import.namespace else workflow.name,
                        "inputs": self._parse_decls(workflow.inputs),
                        "outputs": self._parse_decls(workflow.outputs),
                        "parameter_meta": workflow.parameter_meta,
                        "meta": workflow.meta,
                    }
                )

            # 解析导入文档中的其他导入（嵌套导入）
            if hasattr(imported_doc, "imports") and imported_doc.imports:
                import_info["nested_imports"] = self._parse_imports(imported_doc.imports)

        return import_info

    def _parse_workflow_nodes(self, nodes: List[WorkflowNode]) -> List[Dict[str, Any]]:
        parsed_nodes = []
        for node in nodes:
            parsed_nodes.append(self._parse_workflow_node(node))
        return parsed_nodes

    def _parse_workflow_node(self, node: WorkflowNode) -> Dict[str, Any]:
        """解析WorkflowNode，提取节点的详细信息和依赖关系"""

        base_info = {
            "workflow_node_id": node.workflow_node_id,
            "type": type(node).__name__,
            "scatter_depth": node.scatter_depth,
            "dependencies": list(node.workflow_node_dependencies) if hasattr(node, "workflow_node_dependencies") else [],
        }

        if isinstance(node, Decl):
            # 变量声明节点
            decl_info = self._parse_decl(node)
            base_info.update(decl_info)
            base_info["node_type"] = "declaration"

        elif isinstance(node, Call):
            # 任务调用节点
            base_info.update(
                {
                    "node_type": "call",
                    "call_name": node.name,
                    "callee_id": node.callee_id,
                    "after": node.after,
                    "inputs": self._parse_call_inputs(node.inputs),
                    "callee_task": node.callee.name if node.callee else None,
                }
            )

        elif isinstance(node, Scatter):
            # Scatter并行执行节点
            base_info.update(
                {
                    "node_type": "scatter",
                    "variable": node.variable,
                    "expression": self._parse_expression_value(node.expr),
                    "body": self._parse_workflow_nodes(node.body),
                    "gathers": {k: v.workflow_node_id for k, v in node.gathers.items()},
                }
            )

        elif isinstance(node, Conditional):
            # 条件执行节点
            base_info.update(
                {
                    "node_type": "conditional",
                    "condition": self._parse_expression_value(node.expr),
                    "body": self._parse_workflow_nodes(node.body),
                    "gathers": {k: v.workflow_node_id for k, v in node.gathers.items()},
                }
            )

        elif isinstance(node, Gather):
            # Gather收集节点
            gather_node = node  # 类型提示，确保是Gather类型
            base_info.update(
                {
                    "node_type": "gather",
                    "referee_id": gather_node.referee.workflow_node_id,
                    "section_id": gather_node.section.workflow_node_id,
                    "final_referee": gather_node.final_referee.workflow_node_id,
                }
            )

        else:
            # 其他未知类型的节点
            base_info["node_type"] = "unknown"

        return base_info

    def _parse_call_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """解析Call节点的输入参数"""
        return {input_name: self._parse_expression_value(input_expr) for input_name, input_expr in inputs.items()}

    def _parse_decl(self, inp: Decl) -> Dict[str, Any]:
        input_info = {
            "name": inp.name,
            "type": str(inp.type),
            "optional": inp.type.optional,
            "expression": None,
        }

        if hasattr(inp, "expr") and inp.expr is not None:
            input_info["expression"] = self._parse_expression_value(inp.expr)

        return input_info

    def _parse_decls(self, decls: List[Decl] | None) -> List[Dict[str, Any]]:
        if decls is None:
            return []
        return [self._parse_decl(decl) for decl in decls]

    def _parse_expression_value(self, expr: Base) -> Dict[str, Any]:
        """解析表达式值 - 使用miniwdl内置的解析能力"""
        # 获取表达式基本信息
        expr_class = type(expr).__name__
        raw_expr = str(expr)

        # 使用miniwdl的内置解析能力
        expr_info = {
            "type": "expression",
            "expression_class": expr_class,
            "raw_expression": raw_expr,
            "is_literal": False,
            "value": None,
        }

        # 1. 使用miniwdl的literal属性检查字面量
        if hasattr(expr, "literal") and expr.literal is not None:
            literal_value = expr.literal
            actual_value = literal_value.value if hasattr(literal_value, "value") else str(literal_value)
            expr_info.update({"type": "literal", "value": actual_value, "is_literal": True, "literal_type": type(literal_value).__name__})
            return expr_info

        # 2. 使用miniwdl的类型信息和内置属性
        if hasattr(expr, "type") and expr.type:
            expr_info["data_type"] = str(expr.type)

        # 3. 处理不同类型的表达式（使用miniwdl的类型系统）
        if expr_class in ["Ident", "Get"]:
            # 标识符或成员访问
            identifier_name = self._extract_identifier_name_from_expr(expr)
            expr_info.update({"type": "identifier", "value": identifier_name, "identifier_type": expr_class})
        elif hasattr(expr, "function_name"):
            # 函数调用
            function_name = getattr(expr, "function_name", "unknown")
            expr_info.update({"type": "function_call", "value": function_name, "function_name": function_name})
        elif hasattr(expr, "value"):
            # 直接值访问
            value = getattr(expr, "value", None)
            expr_info.update({"type": "direct_value", "value": value})
        else:
            # 复杂表达式 - 使用miniwdl的字符串表示
            expr_info.update(
                {
                    "type": "complex",
                    "value": self._describe_complex_expression(expr),
                    # "available_attrs": [attr for attr in dir(expr) if not attr.startswith("_")],
                }
            )

        return expr_info

    def _extract_identifier_name_from_expr(self, expr: Base) -> str:
        """从表达式中提取标识符名称"""
        if hasattr(expr, "name"):
            return str(getattr(expr, "name"))
        elif hasattr(expr, "_ident"):
            return str(getattr(expr, "_ident"))
        else:
            return str(expr)

    def _describe_complex_expression(self, expr: Base) -> str:
        """描述复杂表达式的类型"""
        expr_class = type(expr).__name__

        # 根据miniwdl的表达式类型分类
        if expr_class == "Apply":
            function_name = getattr(expr, "function_name", "unknown")
            return f"function_call({function_name})"
        elif expr_class == "IfThenElse":
            return "conditional_expression"
        elif expr_class == "Placeholder":
            return "string_interpolation"
        elif expr_class in ["Array", "Pair", "Map", "Struct"]:
            return f"compound_literal({expr_class.lower()})"
        else:
            return f"complex_expression({expr_class.lower()})"

    def _parse_command(self, command) -> Dict[str, Any]:
        """解析任务命令，提取命令模板和变量信息"""
        if not command:
            return {"raw_command": None, "has_placeholders": False, "placeholders": []}

        command_str = str(command)
        command_info = {
            "raw_command": command_str,
            "has_placeholders": False,
            "placeholders": [],
            "command_parts": [],
        }

        # 检查是否包含占位符（WDL使用${variable}格式）
        import re

        placeholder_pattern = r"\$\{([^}]+)\}"
        placeholders = re.findall(placeholder_pattern, command_str)

        if placeholders:
            command_info["has_placeholders"] = True
            command_info["placeholders"] = placeholders

            # 分割命令为静态部分和动态部分
            parts = re.split(placeholder_pattern, command_str)
            command_info["command_parts"] = parts

        return command_info

    def _parse_runtime(self, runtime: Dict[str, Base]) -> Dict[str, Any]:
        """解析runtime表达式字典"""
        return {key: self._parse_expression_value(expr) for key, expr in runtime.items()}

    def _parse_tasks(self, tasks: List[Task] | None) -> List[Dict[str, Any]]:
        if tasks is None:
            return []
        return [self._parse_task(task) for task in tasks]

    def _parse_task(self, task: Task) -> Dict[str, Any]:
        """解析Task对象，提取任务的详细信息"""
        return {
            "name": task.name,
            "inputs": self._parse_decls(task.inputs),
            "postinputs": self._parse_decls(task.postinputs),
            "outputs": self._parse_decls(task.outputs),
            "command": self._parse_command(task.command),
            "runtime": self._parse_runtime(task.runtime),
            "parameter_meta": task.parameter_meta,
            "meta": task.meta,
            "private_declarations": self._parse_decls(getattr(task, "private_declarations", [])),
        }


if __name__ == "__main__":
    # 使用简化的解析器
    parser = SimpleWDLParser("/data/agent_backend/docs/wdl/SAW-ST-V6-reregist-autotest.wdl")

    summary = parser.get_workflow_summary()

    summary = json.dumps(summary, indent=4)

    with open("/data/agent_backend/docs/wdl/SAW-ST-V6-reregist-autotest.json", "w") as f:
        f.write(summary)
