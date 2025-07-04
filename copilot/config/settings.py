import os
from pathlib import Path

import yaml

from dotenv import load_dotenv

load_dotenv()

# 设置当前文件父目录的路径
path = Path(__file__).parent.parent
# 设置当前工作目录为脚本所在目录
os.chdir(path)


# 加载YAML文件
def load_yaml_config() -> dict:
    # 从环境变量获取环境名称，默认为"dev"
    env = os.environ.get("ENV", "dev")
    print(f"环境变量: {env}")
    config_file = f"config.{env}.yaml"
    config_path = os.path.join(path, "config", config_file)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        conf = yaml.load(f, yaml.FullLoader)
    return conf


conf = load_yaml_config()

class ChatConfig:
    """聊天配置"""
    ENABLE_STREAM_NOTIFIER = True  # 是否启用流式通知器
    STREAM_NOTIFIER_TIMEOUT = 5  # 流式通知器超时时间（秒）
    STREAM_NOTIFIER_INTERVAL = 0.1  # 流式通知器轮询间隔（秒）
    
    # AI思考和回答分类配置
    ENABLE_AI_THINKING_CLASSIFICATION = True  # 是否启用AI思考和回答分类
    THINKING_EMOJI = "🤔"  # 思考阶段的表情符号
    RESPONSE_EMOJI = "💬"  # 回答阶段的表情符号
    THINKING_PREFIX = "**AI思考中**：" # 思考阶段的前缀
    RESPONSE_PREFIX = "**AI回答**：" # 回答阶段的前缀
    
    # 添加更多思考模式的关键词
    THINKING_KEYWORDS_ZH = [
        "我需要", "让我", "首先", "我应该", "为了回答", "为了获取", "我来",
        "现在让我", "接下来我", "我想", "我会", "我将", "我要", "我先",
        "让我们", "我们需要", "我们来", "我们先", "我们应该"
    ]
    
    THINKING_KEYWORDS_EN = [
        "I need to", "Let me", "I should", "To answer", "In order to",
        "I'll", "I will", "I want to", "I'm going to", "Let's",
        "We need to", "We should", "First, I'll", "Now I'll"
    ]
    
    # 回答模式的关键词
    RESPONSE_KEYWORDS_ZH = [
        "根据查询结果", "基于搜索结果", "查询结果显示", "根据工具返回",
        "基于获取的信息", "从结果中可以看到", "搜索结果表明", "通过查询发现",
        "根据分析结果", "查询到的信息", "搜索得到", "获取的数据显示"
    ]
    
    RESPONSE_KEYWORDS_EN = [
        "Based on the results", "According to the search", "The results show",
        "From the search results", "The query returned", "Based on the data",
        "According to the analysis", "The search revealed", "Results indicate"
    ]
