"""
LLM 工厂模式 - 支持多个 LLM 提供商
"""

import os
from typing import Any, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatZhipuAI
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from langchain_community.chat_models.moonshot import MoonshotChat
except ImportError:
    MoonshotChat = None

try:
    from langchain_community.chat_models.tongyi import ChatTongyi
except ImportError:
    ChatTongyi = None

from copilot.utils.logger import logger
from copilot.config.settings import conf


class LLMFactory:
    """LLM工厂类 - 根据配置创建不同的LLM实例"""

    @classmethod
    def create_llm(cls, provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> BaseChatModel:
        """
        创建LLM实例

        Args:
            provider: LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model: 模型名称，如果不指定则使用配置文件中的默认值
            **kwargs: 额外的参数

        Returns:
            BaseChatModel: LLM实例
        """
        # 获取提供商配置
        if provider is None:
            provider = conf.get("llm", {}).get("default_provider", "deepseek")

        providers_config = conf.get("llm", {}).get("providers", {})
        provider_config = providers_config.get(provider, {})

        if not provider_config:
            logger.warning(f"Provider {provider} not found in config, falling back to deepseek")
            provider = "deepseek"
            provider_config = providers_config.get("deepseek", {})

        # 获取模型名称
        if model is None:
            model = provider_config.get("model", "gpt-3.5-turbo")

        # 获取API密钥
        api_key_env = provider_config.get("api_key_env")
        api_key = os.getenv(api_key_env) if api_key_env else None

        # 基础参数
        base_params = {
            "model": model,
            "temperature": kwargs.get("temperature", provider_config.get("temperature", 0.7)),
            "streaming": kwargs.get("streaming", provider_config.get("streaming", True)),
        }

        # 添加API密钥
        if api_key:
            base_params["api_key"] = api_key

        # 添加base_url（如果有）
        base_url = provider_config.get("base_url")
        if base_url:
            base_params["base_url"] = base_url

        # 根据提供商创建实例
        try:
            if provider == "deepseek":
                return cls._create_deepseek(**base_params)
            elif provider == "openai":
                return cls._create_openai(**base_params)
            elif provider == "claude":
                return cls._create_claude(**base_params)
            elif provider == "moonshot":
                return cls._create_moonshot(**base_params)
            elif provider == "zhipu":
                return cls._create_zhipu(**base_params)
            elif provider == "qwen":
                return cls._create_qwen(**base_params)
            elif provider == "gemini":
                return cls._create_gemini(**base_params)
            else:
                logger.error(f"Unsupported provider: {provider}")
                # 回退到deepseek
                return cls._create_deepseek(**base_params)

        except Exception as e:
            logger.error(f"Failed to create LLM for provider {provider}: {str(e)}")
            # 尝试回退到deepseek
            try:
                deepseek_config = providers_config.get("deepseek", {})
                deepseek_api_key = os.getenv(deepseek_config.get("api_key_env", "DEEPSEEK_API_KEY"))
                if deepseek_api_key:
                    return ChatDeepSeek(
                        model=deepseek_config.get("model", "deepseek-chat"),
                        temperature=deepseek_config.get("temperature", 0.7),
                        streaming=deepseek_config.get("streaming", True),
                        api_key=deepseek_api_key,
                    )
            except Exception as fallback_error:
                logger.error(f"Fallback to deepseek also failed: {str(fallback_error)}")

            raise e

    @staticmethod
    def _create_deepseek(**params) -> ChatDeepSeek:
        """创建DeepSeek实例"""
        if not params.get("api_key"):
            raise ValueError("DEEPSEEK_API_KEY is required")
        return ChatDeepSeek(**params)

    @staticmethod
    def _create_openai(**params) -> ChatOpenAI:
        """创建OpenAI实例"""
        if not params.get("api_key"):
            raise ValueError("OPENAI_API_KEY is required")
        return ChatOpenAI(**params)

    @staticmethod
    def _create_claude(**params) -> ChatAnthropic:
        """创建Claude实例"""
        if not params.get("api_key"):
            raise ValueError("ANTHROPIC_API_KEY is required")
        return ChatAnthropic(**params)

    @staticmethod
    def _create_moonshot(**params) -> Any:
        """创建Moonshot实例"""
        if MoonshotChat is None:
            raise ImportError("Moonshot chat model not available")
        if not params.get("api_key"):
            raise ValueError("MOONSHOT_API_KEY is required")

        # Moonshot 可能需要特殊的参数处理
        moonshot_params = params.copy()
        if "base_url" in moonshot_params:
            moonshot_params["moonshot_api_base"] = moonshot_params.pop("base_url")

        return MoonshotChat(**moonshot_params)

    @staticmethod
    def _create_zhipu(**params) -> ChatZhipuAI:
        """创建智谱AI实例"""
        if not params.get("api_key"):
            raise ValueError("ZHIPU_API_KEY is required")
        return ChatZhipuAI(**params)

    @staticmethod
    def _create_qwen(**params) -> Any:
        """创建通义千问实例"""
        if ChatTongyi is None:
            raise ImportError("Tongyi (Qwen) chat model not available")
        if not params.get("api_key"):
            raise ValueError("DASHSCOPE_API_KEY is required")

        # 通义千问使用dashscope_api_key参数
        qwen_params = params.copy()
        qwen_params["dashscope_api_key"] = qwen_params.pop("api_key")

        return ChatTongyi(**qwen_params)

    @staticmethod
    def _create_gemini(**params) -> ChatGoogleGenerativeAI:
        """创建Gemini实例"""
        if not params.get("api_key"):
            raise ValueError("GOOGLE_API_KEY is required")

        # Gemini 使用google_api_key参数
        gemini_params = params.copy()
        gemini_params["google_api_key"] = gemini_params.pop("api_key")

        return ChatGoogleGenerativeAI(**gemini_params)

    @classmethod
    def get_available_providers(cls) -> Dict[str, bool]:
        """
        获取可用的提供商列表

        Returns:
            Dict[str, bool]: 提供商名称和是否可用的映射
        """
        providers = {}
        providers_config = conf.get("llm", {}).get("providers", {})

        for provider_name, provider_config in providers_config.items():
            api_key_env = provider_config.get("api_key_env")
            api_key = os.getenv(api_key_env) if api_key_env else None
            providers[provider_name] = bool(api_key)

        return providers

    @classmethod
    def validate_provider(cls, provider: str) -> bool:
        """
        验证提供商是否可用

        Args:
            provider: 提供商名称

        Returns:
            bool: 是否可用
        """
        available_providers = cls.get_available_providers()
        return available_providers.get(provider, False)
