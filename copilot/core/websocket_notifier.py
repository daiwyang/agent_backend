"""
WebSocket通知器 - 处理MCP工具执行状态的实时推送
"""

from datetime import datetime, UTC
from typing import Any, Dict

from copilot.utils.logger import logger


class WebSocketNotifier:
    """WebSocket通知器 - 负责向前端推送MCP工具执行状态"""
    
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
    async def notify_tool_execution_start(session_id: str, tool_info: Dict[str, Any]):
        """通知前端工具开始执行"""
        try:
            from copilot.utils.websocket_manager import connection_manager
            
            message = {
                "type": "mcp_tool_execution_start",
                "data": {
                    "tool_name": tool_info["tool_name"],
                    "parameters": tool_info["parameters"],
                    "risk_level": tool_info.get("risk_level", "medium"),
                    "start_time": tool_info["start_time"],
                    "status": "executing"
                }
            }
            
            await connection_manager.send_to_session(session_id, message)
            logger.debug(f"Notified tool execution start: {tool_info['tool_name']}")
            
        except Exception as e:
            logger.warning(f"Failed to notify tool execution start: {e}")

    @staticmethod
    async def notify_tool_waiting_permission(session_id: str, tool_info: Dict[str, Any]):
        """通知前端工具等待权限确认"""
        try:
            from copilot.utils.websocket_manager import connection_manager
            
            message = {
                "type": "mcp_tool_waiting_permission",
                "data": {
                    "tool_name": tool_info["tool_name"],
                    "parameters": tool_info["parameters"],
                    "risk_level": tool_info.get("risk_level", "medium"),
                    "start_time": tool_info["start_time"],
                    "status": "waiting_permission"
                }
            }
            
            await connection_manager.send_to_session(session_id, message)
            logger.debug(f"Notified tool waiting permission: {tool_info['tool_name']}")
            
        except Exception as e:
            logger.warning(f"Failed to notify tool waiting permission: {e}")

    @staticmethod
    async def notify_tool_execution_complete(session_id: str, tool_info: Dict[str, Any], 
                                           result: Any, success: bool):
        """通知前端工具执行完成"""
        try:
            from copilot.utils.websocket_manager import connection_manager
            
            # 处理结果数据
            if success:
                from copilot.core.tool_result_processor import ToolResultProcessor
                processed_result = ToolResultProcessor.process_for_frontend(result)
            else:
                processed_result = {
                    "error": str(result),
                    "success": False
                }
            
            message = {
                "type": "mcp_tool_execution_complete",
                "data": {
                    "tool_name": tool_info["tool_name"],
                    "parameters": tool_info["parameters"],
                    "risk_level": tool_info.get("risk_level", "medium"),
                    "start_time": tool_info["start_time"],
                    "end_time": datetime.now(UTC).isoformat(),
                    "success": success,
                    "result": processed_result,
                    "status": "completed" if success else "failed"
                }
            }
            
            await connection_manager.send_to_session(session_id, message)
            logger.debug(f"Notified tool execution complete: {tool_info['tool_name']} - {'success' if success else 'failed'}")
            
        except Exception as e:
            logger.warning(f"Failed to notify tool execution complete: {e}") 