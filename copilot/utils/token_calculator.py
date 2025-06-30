"""
Token计算工具 - 简化token使用量估算
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, Union

from copilot.utils.logger import logger


@dataclass
class TokenUsage:
    """Token使用量数据结构"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, int]:
        """转换为字典格式"""
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens, "total_tokens": self.total_tokens}

    @classmethod
    def from_dict(cls, data: Dict[str, Union[int, float]]) -> "TokenUsage":
        """从字典创建TokenUsage实例"""
        return cls(
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
        )


class TokenCalculator:
    """简化的Token计算器"""

    # 不同模型的平均token率（字符数/token）
    TOKEN_RATES = {
        "gpt-4": 4.0,
        "gpt-3.5": 4.0,
        "claude": 4.5,
        "deepseek": 3.5,
        "qwen": 2.0,
        "zhipu": 2.5,
        "moonshot": 3.0,
        "gemini": 4.0,
        "default": 4.0,
    }

    @classmethod
    def estimate_tokens(cls, text: str, model_name: str = "default") -> int:
        """
        估算文本的token数量

        Args:
            text: 输入文本
            model_name: 模型名称

        Returns:
            int: 估算的token数量
        """
        if not text:
            return 0

        try:
            # 简单的token估算：基于字符数和经验比率
            char_count = len(text)

            # 获取模型对应的token率
            rate = cls.TOKEN_RATES.get(model_name, cls.TOKEN_RATES["default"])

            # 基本估算
            estimated_tokens = max(1, int(char_count / rate))

            # 中文文本调整（中文token消耗通常更高）
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
            if chinese_chars > 0:
                # 中文比率调整
                chinese_ratio = chinese_chars / char_count
                adjustment_factor = 1 + (chinese_ratio * 0.5)  # 中文增加50%
                estimated_tokens = int(estimated_tokens * adjustment_factor)

            return estimated_tokens

        except Exception as e:
            logger.warning(f"Token estimation failed: {str(e)}, using fallback")
            # 降级处理：每4个字符约等于1个token
            return max(1, len(text) // 4)

    @classmethod
    def calculate_usage(cls, prompt: str, completion: str, model_name: str = "default") -> TokenUsage:
        """
        计算完整的token使用量

        Args:
            prompt: 用户输入
            completion: 模型回复
            model_name: 模型名称

        Returns:
            TokenUsage: token使用量统计
        """
        try:
            prompt_tokens = cls.estimate_tokens(prompt, model_name)
            completion_tokens = cls.estimate_tokens(completion, model_name)
            total_tokens = prompt_tokens + completion_tokens

            return TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens)

        except Exception as e:
            logger.error(f"Token calculation failed: {str(e)}")
            # 返回默认值，避免系统崩溃
            return TokenUsage()

    @classmethod
    def safe_extract_tokens(cls, token_data: Optional[Dict]) -> TokenUsage:
        """
        安全地从token数据中提取信息

        Args:
            token_data: token数据字典（可能为None或格式不正确）

        Returns:
            TokenUsage: 安全的token使用量
        """
        if not token_data:
            return TokenUsage()

        try:
            if isinstance(token_data, dict):
                return TokenUsage.from_dict(token_data)
            else:
                logger.warning(f"Invalid token data type: {type(token_data)}")
                return TokenUsage()

        except Exception as e:
            logger.warning(f"Failed to extract token data: {str(e)}")
            return TokenUsage()

    @classmethod
    def get_model_key(cls, provider: str, model_name: str = None) -> str:
        """
        获取模型对应的token计算key

        Args:
            provider: LLM提供商
            model_name: 模型名称

        Returns:
            str: 模型key
        """
        provider_mapping = {
            "openai": "gpt-4",
            "claude": "claude",
            "deepseek": "deepseek",
            "qwen": "qwen",
            "zhipu": "zhipu",
            "moonshot": "moonshot",
            "gemini": "gemini",
        }

        # 先尝试根据model_name匹配
        if model_name:
            model_lower = model_name.lower()
            if "gpt-3.5" in model_lower:
                return "gpt-3.5"
            elif "gpt-4" in model_lower:
                return "gpt-4"
            elif "claude" in model_lower:
                return "claude"
            elif "deepseek" in model_lower:
                return "deepseek"
            elif "qwen" in model_lower:
                return "qwen"
            elif "zhipu" in model_lower or "glm" in model_lower:
                return "zhipu"
            elif "moonshot" in model_lower:
                return "moonshot"
            elif "gemini" in model_lower:
                return "gemini"

        # 根据provider匹配
        return provider_mapping.get(provider, "default")
