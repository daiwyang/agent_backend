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
