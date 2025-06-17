"""
LLM 提供商管理工具
"""

import os
from typing import Dict, List, Any, Optional
from copilot.core.llm_factory import LLMFactory
from copilot.utils.logger import logger
from copilot.config.settings import conf


class LLMProviderManager:
    """LLM提供商管理器"""
    
    @staticmethod
    def get_provider_status() -> Dict[str, Any]:
        """
        获取所有提供商的状态信息
        
        Returns:
            Dict[str, Any]: 提供商状态信息
        """
        providers_config = conf.get('llm', {}).get('providers', {})
        default_provider = conf.get('llm', {}).get('default_provider', 'deepseek')
        
        status = {
            'default_provider': default_provider,
            'providers': {}
        }
        
        for provider_name, provider_config in providers_config.items():
            api_key_env = provider_config.get('api_key_env')
            api_key = os.getenv(api_key_env) if api_key_env else None
            
            status['providers'][provider_name] = {
                'model': provider_config.get('model'),
                'available': bool(api_key),
                'api_key_env': api_key_env,
                'api_key_configured': bool(api_key),
                'base_url': provider_config.get('base_url'),
                'supports_streaming': provider_config.get('streaming', True),
                'supports_multimodal': provider_name in ['openai', 'claude', 'gemini']
            }
        
        return status
    
    @staticmethod
    def get_available_providers() -> List[str]:
        """
        获取可用的提供商列表
        
        Returns:
            List[str]: 可用提供商名称列表
        """
        status = LLMProviderManager.get_provider_status()
        return [name for name, info in status['providers'].items() if info['available']]
    
    @staticmethod
    def validate_provider_config(provider: str) -> Dict[str, Any]:
        """
        验证提供商配置
        
        Args:
            provider: 提供商名称
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        providers_config = conf.get('llm', {}).get('providers', {})
        
        if provider not in providers_config:
            return {
                'valid': False,
                'error': f'Provider {provider} not found in configuration'
            }
        
        provider_config = providers_config[provider]
        api_key_env = provider_config.get('api_key_env')
        api_key = os.getenv(api_key_env) if api_key_env else None
        
        result = {
            'valid': bool(api_key),
            'provider': provider,
            'model': provider_config.get('model'),
            'api_key_env': api_key_env,
            'api_key_configured': bool(api_key)
        }
        
        if not api_key:
            result['error'] = f'API key not found in environment variable: {api_key_env}'
        
        return result
    
    @staticmethod
    def test_provider(provider: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        测试提供商连接
        
        Args:
            provider: 提供商名称
            model: 模型名称（可选）
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            # 验证配置
            config_result = LLMProviderManager.validate_provider_config(provider)
            if not config_result['valid']:
                return {
                    'success': False,
                    'error': config_result.get('error')
                }
            
            # 尝试创建LLM实例
            llm = LLMFactory.create_llm(provider=provider, model=model)
            
            # 这里可以添加一个简单的测试请求
            # 注意：实际测试可能会消耗API配额
            
            return {
                'success': True,
                'provider': provider,
                'model': model or config_result.get('model'),
                'message': f'Provider {provider} is working correctly'
            }
            
        except Exception as e:
            logger.error(f"Failed to test provider {provider}: {str(e)}")
            return {
                'success': False,
                'provider': provider,
                'error': str(e)
            }
    
    @staticmethod
    def get_provider_recommendations() -> Dict[str, Any]:
        """
        获取提供商推荐
        
        Returns:
            Dict[str, Any]: 推荐信息
        """
        available_providers = LLMProviderManager.get_available_providers()
        status = LLMProviderManager.get_provider_status()
        
        recommendations = {
            'for_general_chat': [],
            'for_multimodal': [],
            'for_coding': [],
            'for_chinese': []
        }
        
        # 通用聊天推荐
        general_preference = ['openai', 'claude', 'deepseek', 'moonshot']
        for provider in general_preference:
            if provider in available_providers:
                recommendations['for_general_chat'].append(provider)
        
        # 多模态推荐
        multimodal_providers = ['openai', 'claude', 'gemini']
        for provider in multimodal_providers:
            if provider in available_providers:
                recommendations['for_multimodal'].append(provider)
        
        # 编程推荐
        coding_preference = ['openai', 'claude', 'deepseek']
        for provider in coding_preference:
            if provider in available_providers:
                recommendations['for_coding'].append(provider)
        
        # 中文推荐
        chinese_preference = ['deepseek', 'moonshot', 'zhipu', 'qwen', 'openai']
        for provider in chinese_preference:
            if provider in available_providers:
                recommendations['for_chinese'].append(provider)
        
        return {
            'available_count': len(available_providers),
            'available_providers': available_providers,
            'recommendations': recommendations,
            'default_provider': status['default_provider']
        }
    
    @staticmethod
    def get_setup_instructions() -> Dict[str, str]:
        """
        获取各个提供商的设置说明
        
        Returns:
            Dict[str, str]: 设置说明
        """
        return {
            'deepseek': 'export DEEPSEEK_API_KEY="your-deepseek-api-key"',
            'openai': 'export OPENAI_API_KEY="your-openai-api-key"',
            'claude': 'export ANTHROPIC_API_KEY="your-anthropic-api-key"',
            'moonshot': 'export MOONSHOT_API_KEY="your-moonshot-api-key"',
            'zhipu': 'export ZHIPU_API_KEY="your-zhipu-api-key"',
            'qwen': 'export DASHSCOPE_API_KEY="your-dashscope-api-key"',
            'gemini': 'export GOOGLE_API_KEY="your-google-api-key"'
        }
