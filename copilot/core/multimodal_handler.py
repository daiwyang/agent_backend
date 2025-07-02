"""
多模态处理器 - 处理图片和其他多媒体内容
"""

from typing import List, Optional

from copilot.utils.logger import logger


class MultimodalHandler:
    """多模态处理器 - 负责处理图片等多媒体内容"""
    
    def __init__(self, provider: str):
        """
        初始化多模态处理器
        
        Args:
            provider: LLM提供商名称
        """
        self.provider = provider
    
    def supports_multimodal(self) -> bool:
        """检查当前提供商是否支持多模态"""
        return self.provider in ["openai", "claude", "gemini"]
    
    async def preprocess_image(self, image_data: dict) -> dict:
        """
        图片预处理
        - 格式转换
        - 尺寸调整
        - 质量压缩
        
        Args:
            image_data: 图片数据字典
            
        Returns:
            dict: 处理后的图片数据
        """
        try:
            # 根据不同提供商处理图片格式
            if self.provider == "openai":
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data.get("url") or 
                               f"data:{image_data.get('mime_type', 'image/jpeg')};base64,{image_data.get('base64')}"
                    },
                }
            elif self.provider == "claude":
                return {
                    "type": "image",
                    "source": {
                        "type": "base64", 
                        "media_type": image_data.get("mime_type", "image/jpeg"), 
                        "data": image_data.get("base64")
                    },
                }
            else:
                # 默认格式
                return {
                    "type": "image",
                    "source": {
                        "type": "base64", 
                        "media_type": image_data.get("mime_type", "image/jpeg"), 
                        "data": image_data.get("base64")
                    },
                }
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            # 返回错误格式的图片数据
            return {
                "type": "error",
                "error": f"图片处理失败: {str(e)}"
            }
    
    async def build_multimodal_content(self, message: str, images: Optional[List[dict]]) -> any:
        """
        构建多模态内容
        
        Args:
            message: 文本消息
            images: 图片列表
            
        Returns:
            构建后的内容（可能是字符串或复合对象）
        """
        try:
            # 如果没有图片或不支持多模态，返回纯文本
            if not images or not self.supports_multimodal():
                return message
            
            # 构建多模态内容
            content = [{"type": "text", "text": message}]
            
            for img in images:
                processed_img = await self.preprocess_image(img)
                if processed_img.get("type") != "error":
                    content.append(processed_img)
                else:
                    logger.warning(f"Skipping invalid image: {processed_img.get('error')}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error building multimodal content: {e}")
            # 回退到纯文本
            return message
    
    def extract_images_from_attachments(self, attachments: Optional[List[dict]]) -> List[dict]:
        """
        从附件中提取图片
        
        Args:
            attachments: 附件列表
            
        Returns:
            List[dict]: 图片列表
        """
        if not attachments:
            return []
        
        try:
            images = []
            for attachment in attachments:
                if attachment.get("type") == "image":
                    # 验证图片数据
                    if self._validate_image_data(attachment):
                        images.append(attachment)
                    else:
                        logger.warning(f"Invalid image attachment: {attachment}")
            
            return images
            
        except Exception as e:
            logger.error(f"Error extracting images from attachments: {e}")
            return []
    
    def _validate_image_data(self, image_data: dict) -> bool:
        """
        验证图片数据是否有效
        
        Args:
            image_data: 图片数据
            
        Returns:
            bool: 是否有效
        """
        try:
            # 检查必需字段
            if not image_data.get("base64") and not image_data.get("url"):
                return False
            
            # 检查MIME类型
            mime_type = image_data.get("mime_type", "")
            if mime_type and not mime_type.startswith("image/"):
                return False
            
            # 检查base64数据长度（如果存在）
            base64_data = image_data.get("base64", "")
            if base64_data and len(base64_data) < 100:  # 太短的base64不太可能是有效图片
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating image data: {e}")
            return False 