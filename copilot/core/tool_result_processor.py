"""
工具结果处理器 - 处理和格式化MCP工具的返回结果
"""

from typing import Any, Dict

from copilot.utils.logger import logger


class ToolResultProcessor:
    """工具结果处理器 - 负责格式化工具结果以供不同场景使用"""
    
    @staticmethod
    def process_for_frontend(raw_result: Any) -> Dict[str, Any]:
        """
        处理工具结果，转换为适合前端显示的格式
        
        Args:
            raw_result: 工具的原始返回结果
            
        Returns:
            Dict[str, Any]: 处理后的结果
        """
        try:
            # 如果是字符串，尝试解析为JSON
            if isinstance(raw_result, str):
                try:
                    import json
                    parsed = json.loads(raw_result)
                    if isinstance(parsed, dict):
                        raw_result = parsed
                except:
                    pass
            
            # 处理不同类型的结果
            if isinstance(raw_result, dict):
                # 检查是否有标准的工具返回格式
                if "content" in raw_result:
                    content = raw_result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # 提取文本内容
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                            else:
                                text_parts.append(str(item))
                        
                        return {
                            "type": "text",
                            "content": "\n".join(text_parts),
                            "raw_data": raw_result,
                            "success": True
                        }
                
                # 直接返回字典格式
                return {
                    "type": "structured",
                    "content": raw_result,
                    "raw_data": raw_result,
                    "success": True
                }
            
            else:
                # 其他类型转换为字符串
                content_str = str(raw_result)
                return {
                    "type": "text",
                    "content": content_str,
                    "raw_data": raw_result,
                    "success": True
                }
                
        except Exception as e:
            logger.warning(f"Error processing tool result for frontend: {e}")
            return {
                "type": "error",
                "content": f"无法处理工具结果: {str(e)}",
                "raw_data": None,
                "success": False
            }

    @staticmethod
    def format_for_user(tool_name: str, raw_result: Any) -> str:
        """
        将工具的原始执行结果转换为用户友好的消息
        
        Args:
            tool_name: 工具名称
            raw_result: 工具的原始返回结果
            
        Returns:
            str: 用户友好的结果描述
        """
        try:
            # 根据工具类型提供不同的用户友好消息
            tool_friendly_names = {
                "file_read": "文件读取",
                "file_write": "文件写入", 
                "file_list": "文件列表",
                "directory_list": "目录列表",
                "command_execute": "命令执行",
                "search": "搜索",
                "browser": "网页浏览",
                "api_call": "API调用",
            }
            
            # 获取工具的友好名称
            friendly_name = tool_friendly_names.get(
                tool_name.split("::")[-1] if "::" in tool_name else tool_name, 
                "工具"
            )
            
            # 检查是否有明显的错误
            if isinstance(raw_result, str) and any(
                error_word in raw_result.lower() 
                for error_word in ["error", "failed", "exception", "错误", "失败"]
            ):
                return f"❌ {friendly_name}执行遇到问题，请稍后重试"
            
            # 返回简洁的成功消息
            return f"✅ {friendly_name}已成功执行"
            
        except Exception as e:
            logger.warning(f"Error formatting tool result for {tool_name}: {e}")
            return f"✅ 工具 {tool_name} 已执行完成"

    @staticmethod
    def should_filter_content(content: str) -> bool:
        """
        判断是否应该过滤掉工具相关的内容
        
        Args:
            content: 要检查的内容
            
        Returns:
            bool: True表示应该过滤掉，False表示保留
        """
        # 过滤掉工具调用和返回结果相关的内容
        filter_patterns = [
            # MCP工具调用相关
            "Tool execution result:",
            "Calling tool:",
            "Tool result:",
            # JSON格式的工具返回
            '"success": true',
            '"success": false', 
            '"result":',
            '"error":',
            # 工具执行状态消息
            "执行工具:",
            "工具执行",
            "调用工具",
            # 原始数据标识
            "raw_output",
            "processed_text",
            # 常见的MCP工具返回格式
            '{"content":',
            '{"type":',
            # 过滤文件系统操作结果
            "File contents:",
            "Directory listing:",
            "Command output:",
        ]
        
        # 检查是否包含过滤模式
        content_lower = content.lower()
        for pattern in filter_patterns:
            if pattern.lower() in content_lower:
                return True
                
        # 检查是否是纯JSON格式（可能是工具返回）
        content_stripped = content.strip()
        if content_stripped.startswith('{') and content_stripped.endswith('}'):
            try:
                import json
                json.loads(content_stripped)
                # 如果是有效JSON且包含常见工具返回字段，则过滤
                if any(key in content_stripped for key in ['"success"', '"result"', '"error"', '"data"']):
                    return True
            except:
                pass
                
        return False 