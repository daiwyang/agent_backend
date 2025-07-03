"""
简单通知器 - 基于Redis的轻量级MCP工具状态管理
支持SSE实时推送
"""

import json
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from copilot.utils.logger import logger
from copilot.utils.redis_client import redis_client


class SimpleNotifier:
    """简单通知器 - 基于Redis的状态管理，支持SSE实时推送"""

    # Redis键前缀
    TOOL_STATUS_PREFIX = "tool_status:"
    PERMISSION_REQUEST_PREFIX = "permission_request:"
    TOOL_RESULT_PREFIX = "tool_result:"

    # Redis发布频道
    SSE_CHANNEL = "sse_events"

    @staticmethod
    def extract_tool_parameters(args) -> Dict[str, Any]:
        """
        从工具参数中提取可显示的参数信息

        Args:
            args: 工具调用参数

        Returns:
            Dict[str, Any]: 提取的参数信息
        """
        try:
            if not args:
                return {}

            if len(args) == 1 and isinstance(args[0], dict):
                # 过滤掉可能很大的值
                filtered_params = {}
                for key, value in args[0].items():
                    if isinstance(value, str) and len(value) > 200:
                        filtered_params[key] = f"{value[:200]}... (truncated)"
                    else:
                        filtered_params[key] = value
                return filtered_params
            else:
                return {"args": [str(arg)[:100] + "..." if len(str(arg)) > 100 else str(arg) for arg in args]}

        except Exception as e:
            logger.warning(f"Error extracting tool parameters: {e}")
            return {"args": "unable to extract"}

    @staticmethod
    def _get_tool_status_key(session_id: str) -> str:
        """获取工具状态Redis键"""
        return f"{SimpleNotifier.TOOL_STATUS_PREFIX}{session_id}"

    @staticmethod
    def _get_permission_key(session_id: str) -> str:
        """获取权限请求Redis键"""
        return f"{SimpleNotifier.PERMISSION_REQUEST_PREFIX}{session_id}"

    @staticmethod
    def _get_result_key(session_id: str) -> str:
        """获取工具结果Redis键"""
        return f"{SimpleNotifier.TOOL_RESULT_PREFIX}{session_id}"

    @staticmethod
    async def _publish_sse_event(session_id: str, event_type: str, data: Dict[str, Any]):
        """发布SSE事件到Redis"""
        try:
            event = {"session_id": session_id, "type": event_type, "data": data, "timestamp": datetime.now(UTC).isoformat()}

            await redis_client.publish(SimpleNotifier.SSE_CHANNEL, json.dumps(event))
            logger.debug(f"Published SSE event: {event_type} for session {session_id}")

        except Exception as e:
            logger.warning(f"Failed to publish SSE event: {e}")

    @staticmethod
    async def set_tool_status(session_id: str, status: str, tool_name: str, details: Dict[str, Any] = None):
        """设置工具执行状态"""
        try:
            status_data = {"status": status, "tool_name": tool_name, "timestamp": datetime.now(UTC).isoformat(), "details": details or {}}

            key = SimpleNotifier._get_tool_status_key(session_id)
            await redis_client.setex(key, 300, json.dumps(status_data))  # 5分钟过期

            # 发布SSE事件
            await SimpleNotifier._publish_sse_event(session_id, "tool_status", status_data)

            logger.debug(f"Tool status set for session {session_id}: {status}")

        except Exception as e:
            logger.warning(f"Failed to set tool status: {e}")

    @staticmethod
    async def get_tool_status(session_id: str) -> Optional[Dict[str, Any]]:
        """获取工具执行状态"""
        try:
            key = SimpleNotifier._get_tool_status_key(session_id)
            data = await redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.warning(f"Failed to get tool status: {e}")
            return None

    @staticmethod
    async def set_permission_request(session_id: str, tool_name: str, parameters: Dict[str, Any], risk_level: str = "medium"):
        """设置权限请求"""
        try:
            request_data = {
                "tool_name": tool_name,
                "parameters": parameters,
                "risk_level": risk_level,
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "pending",
            }

            key = SimpleNotifier._get_permission_key(session_id)
            await redis_client.setex(key, 600, json.dumps(request_data))  # 10分钟过期

            # 发布SSE事件
            await SimpleNotifier._publish_sse_event(session_id, "permission_request", request_data)

            logger.debug(f"Permission request set for session {session_id}: {tool_name}")

        except Exception as e:
            logger.warning(f"Failed to set permission request: {e}")

    @staticmethod
    async def get_permission_request(session_id: str) -> Optional[Dict[str, Any]]:
        """获取权限请求"""
        try:
            key = SimpleNotifier._get_permission_key(session_id)
            data = await redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.warning(f"Failed to get permission request: {e}")
            return None

    @staticmethod
    async def clear_permission_request(session_id: str):
        """清除权限请求"""
        try:
            key = SimpleNotifier._get_permission_key(session_id)
            await redis_client.delete(key)

            # 发布清除事件
            await SimpleNotifier._publish_sse_event(session_id, "permission_cleared", {"message": "权限请求已处理"})

        except Exception as e:
            logger.warning(f"Failed to clear permission request: {e}")

    @staticmethod
    async def set_tool_result(session_id: str, tool_name: str, result: Any, success: bool):
        """设置工具执行结果"""
        try:
            # 处理结果数据
            if success:
                from copilot.core.tool_result_processor import ToolResultProcessor

                processed_result = ToolResultProcessor.process_for_frontend(result)
            else:
                processed_result = {"error": str(result), "success": False}

            result_data = {"tool_name": tool_name, "result": processed_result, "success": success, "timestamp": datetime.now(UTC).isoformat()}

            key = SimpleNotifier._get_result_key(session_id)
            await redis_client.setex(key, 300, json.dumps(result_data))  # 5分钟过期

            # 发布SSE事件
            await SimpleNotifier._publish_sse_event(session_id, "tool_result", result_data)

            logger.debug(f"Tool result set for session {session_id}: {tool_name}")

        except Exception as e:
            logger.warning(f"Failed to set tool result: {e}")

    @staticmethod
    async def get_tool_result(session_id: str) -> Optional[Dict[str, Any]]:
        """获取工具执行结果"""
        try:
            key = SimpleNotifier._get_result_key(session_id)
            data = await redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.warning(f"Failed to get tool result: {e}")
            return None

    @staticmethod
    async def clear_tool_result(session_id: str):
        """清除工具结果"""
        try:
            key = SimpleNotifier._get_result_key(session_id)
            await redis_client.delete(key)

            # 发布清除事件
            await SimpleNotifier._publish_sse_event(session_id, "result_cleared", {"message": "工具结果已清除"})

        except Exception as e:
            logger.warning(f"Failed to clear tool result: {e}")

    # 提供WebSocket兼容的接口，现在支持SSE实时推送
    @staticmethod
    async def notify_tool_execution_start(session_id: str, tool_info: Dict[str, Any]):
        """通知工具开始执行"""
        await SimpleNotifier.set_tool_status(
            session_id,
            "executing",
            tool_info["tool_name"],
            {"parameters": tool_info["parameters"], "risk_level": tool_info.get("risk_level", "medium"), "start_time": tool_info["start_time"]},
        )

    @staticmethod
    async def notify_tool_waiting_permission(session_id: str, tool_info: Dict[str, Any]):
        """通知工具等待权限确认"""
        await SimpleNotifier.set_tool_status(
            session_id,
            "waiting_permission",
            tool_info["tool_name"],
            {"parameters": tool_info["parameters"], "risk_level": tool_info.get("risk_level", "medium")},
        )

        # 同时设置权限请求
        await SimpleNotifier.set_permission_request(
            session_id, tool_info["tool_name"], tool_info["parameters"], tool_info.get("risk_level", "medium")
        )

    @staticmethod
    async def notify_tool_execution_complete(session_id: str, tool_info: Dict[str, Any], result: Any, success: bool):
        """通知工具执行完成"""
        await SimpleNotifier.set_tool_status(
            session_id,
            "completed" if success else "failed",
            tool_info["tool_name"],
            {"parameters": tool_info["parameters"], "end_time": datetime.now(UTC).isoformat(), "success": success},
        )

        # 设置结果
        await SimpleNotifier.set_tool_result(session_id, tool_info["tool_name"], result, success)
