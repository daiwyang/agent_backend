"""
流式通知器 - 通过聊天流发送MCP工具状态和权限请求
"""

import uuid
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from copilot.model.chat_model import ToolPermissionRequest, ToolExecutionStatus, ToolPermissionRequestMessage, ToolExecutionStatusMessage
from copilot.utils.logger import logger


class StreamNotifier:
    """流式通知器 - 通过聊天流发送工具权限和状态通知"""

    # 存储待发送的流式消息队列 (session_id -> list of messages)
    _pending_messages = {}

    @staticmethod
    def extract_tool_parameters(args, kwargs=None, tool_name=None) -> Dict[str, Any]:
        """
        从工具参数中提取可显示的参数信息 - 增强版本，支持多种参数传递方式

        Args:
            args: 工具调用的位置参数
            kwargs: 工具调用的关键字参数（可选）
            tool_name: 工具名称（用于调试）

        Returns:
            Dict[str, Any]: 提取的参数信息
        """
        try:
            # 详细的调试信息
            logger.debug(f"Extracting parameters for tool {tool_name}:")
            logger.debug(f"  args type: {type(args)}")
            logger.debug(f"  args content: {args}")
            logger.debug(f"  kwargs type: {type(kwargs)}")
            logger.debug(f"  kwargs content: {kwargs}")
            
            extracted_params = {}
            
            # 方式1: 从 args 中提取（优先级最高）
            if args:
                logger.debug(f"  Extracting from args...")
                if len(args) == 1 and isinstance(args[0], dict):
                    # 单个字典参数
                    for key, value in args[0].items():
                        if isinstance(value, str) and len(value) > 200:
                            extracted_params[key] = f"{value[:200]}... (truncated)"
                        else:
                            extracted_params[key] = value
                    logger.debug(f"  Extracted from single dict arg: {extracted_params}")
                else:
                    # 多个参数或非字典参数
                    extracted_params["args"] = [str(arg)[:100] + "..." if len(str(arg)) > 100 else str(arg) for arg in args]
                    logger.debug(f"  Extracted from multiple args: {extracted_params}")
                
                # 如果从args中提取到参数，直接返回
                if extracted_params:
                    logger.debug(f"  Final extracted parameters from args: {extracted_params}")
                    return extracted_params
            
            # 方式2: 检查kwargs中的特殊参数字段（优先于普通kwargs）
            if kwargs:
                logger.debug(f"  Checking special parameter fields in kwargs...")
                common_param_fields = ['input', 'query', 'text', 'data', 'content', 'params', 'parameters']
                for field in common_param_fields:
                    if field in kwargs:
                        param_value = kwargs[field]
                        if isinstance(param_value, dict):
                            # 如果参数值是字典，展开其内容
                            extracted_params.update(param_value)
                            logger.debug(f"  Extracted and expanded from {field} field: {extracted_params}")
                        else:
                            # 如果参数值不是字典，保留字段名
                            extracted_params[field] = param_value
                            logger.debug(f"  Extracted from {field} field: {extracted_params}")
                        
                        # 找到特殊字段就返回，不继续检查
                        if extracted_params:
                            logger.debug(f"  Final extracted parameters from special field: {extracted_params}")
                            return extracted_params
            
            # 方式3: 从普通 kwargs 中提取（最后的选择）
            if kwargs:
                logger.debug(f"  Extracting from regular kwargs...")
                # 过滤掉内部配置参数
                filtered_kwargs = {}
                for key, value in kwargs.items():
                    if key not in ['config', 'run_manager', 'callbacks']:
                        if isinstance(value, str) and len(value) > 200:
                            filtered_kwargs[key] = f"{value[:200]}... (truncated)"
                        else:
                            filtered_kwargs[key] = value
                
                if filtered_kwargs:
                    extracted_params = filtered_kwargs
                    logger.debug(f"  Extracted from regular kwargs: {extracted_params}")
            
            # 如果仍然没有参数，记录详细信息
            if not extracted_params:
                logger.info(f"No parameters extracted for tool {tool_name}")
                logger.debug(f"  This might be normal for tools with no parameters or using default values")
                return {}
            
            logger.debug(f"  Final extracted parameters: {extracted_params}")
            return extracted_params

        except Exception as e:
            logger.warning(f"Error extracting tool parameters for {tool_name}: {e}")
            logger.debug(f"  args: {args}")
            logger.debug(f"  kwargs: {kwargs}")
            return {"args": "parameter extraction failed", "error": str(e)}

    @staticmethod
    async def add_stream_message(session_id: str, message):
        """添加消息到流式队列"""
        try:
            if session_id not in StreamNotifier._pending_messages:
                StreamNotifier._pending_messages[session_id] = []

            StreamNotifier._pending_messages[session_id].append(message)
            logger.debug(f"Added stream message for session {session_id}: {type(message).__name__}")

        except Exception as e:
            logger.warning(f"Failed to add stream message: {e}")

    @staticmethod
    def get_pending_messages(session_id: str) -> list:
        """获取并清空待发送的消息"""
        try:
            messages = StreamNotifier._pending_messages.get(session_id, [])
            StreamNotifier._pending_messages[session_id] = []
            return messages
        except Exception as e:
            logger.warning(f"Failed to get pending messages: {e}")
            return []

    @staticmethod
    async def send_tool_permission_request(
        session_id: str, tool_name: str, parameters: Dict[str, Any], risk_level: str = "medium", reasoning: Optional[str] = None
    ) -> str:
        """发送工具权限请求消息"""
        try:
            request_id = str(uuid.uuid4())

            # 创建权限请求数据
            permission_request = ToolPermissionRequest(
                request_id=request_id,
                tool_name=tool_name,
                tool_description=f"工具 {tool_name} 需要执行",
                parameters=parameters,
                risk_level=risk_level,
                reasoning=reasoning,
            )

            # 创建流式消息
            message = ToolPermissionRequestMessage(session_id=session_id, timestamp=datetime.now(UTC), data=permission_request)

            # 添加到流式队列
            await StreamNotifier.add_stream_message(session_id, message)

            logger.info(f"Sent tool permission request for session {session_id}: {tool_name}")
            return request_id

        except Exception as e:
            logger.error(f"Failed to send tool permission request: {e}")
            return ""

    @staticmethod
    async def send_tool_execution_status(
        session_id: str,
        request_id: str,
        tool_name: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        progress: Optional[int] = None,
    ):
        """发送工具执行状态消息"""
        try:
            # 创建执行状态数据
            execution_status = ToolExecutionStatus(
                request_id=request_id, tool_name=tool_name, status=status, result=result, error=error, progress=progress
            )

            # 创建流式消息
            message = ToolExecutionStatusMessage(session_id=session_id, timestamp=datetime.now(UTC), data=execution_status)

            # 添加到流式队列
            await StreamNotifier.add_stream_message(session_id, message)

            logger.debug(f"Sent tool execution status for session {session_id}: {tool_name} - {status}")

        except Exception as e:
            logger.error(f"Failed to send tool execution status: {e}")

    # 提供与SimpleNotifier兼容的接口
    @staticmethod
    async def notify_tool_execution_start(session_id: str, tool_info: Dict[str, Any]):
        """通知工具开始执行"""
        request_id = tool_info.get("request_id", str(uuid.uuid4()))
        await StreamNotifier.send_tool_execution_status(
            session_id=session_id, request_id=request_id, tool_name=tool_info["tool_name"], status="executing"
        )

    @staticmethod
    async def notify_tool_waiting_permission(session_id: str, tool_info: Dict[str, Any]):
        """通知工具等待权限确认"""
        # 发送权限请求
        request_id = await StreamNotifier.send_tool_permission_request(
            session_id=session_id,
            tool_name=tool_info["tool_name"],
            parameters=tool_info["parameters"],
            risk_level=tool_info.get("risk_level", "medium"),
        )

        # 更新工具信息中的request_id
        tool_info["request_id"] = request_id

        # 发送等待状态
        await StreamNotifier.send_tool_execution_status(
            session_id=session_id, request_id=request_id, tool_name=tool_info["tool_name"], status="waiting"
        )

    @staticmethod
    async def notify_tool_execution_complete(session_id: str, tool_info: Dict[str, Any], result: Any, success: bool):
        """通知工具执行完成"""
        request_id = tool_info.get("request_id", str(uuid.uuid4()))

        if success:
            # 直接使用工具的原始结果对象，保持数据结构
            await StreamNotifier.send_tool_execution_status(
                session_id=session_id, request_id=request_id, tool_name=tool_info["tool_name"], status="completed", result=result  # 直接传递原始对象
            )
        else:
            # 处理失败结果
            await StreamNotifier.send_tool_execution_status(
                session_id=session_id, request_id=request_id, tool_name=tool_info["tool_name"], status="failed", error=str(result)
            )
