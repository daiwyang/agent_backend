import logging
import os
from logging import LogRecord
from logging.handlers import TimedRotatingFileHandler

import colorlog

from copilot.utils.config import conf


class DefaultClientIPFilter(logging.Filter):
    def filter(self, record: LogRecord):
        # 如果clientip未在日志记录中设置，提供一个默认值
        if not hasattr(record, "clientip"):
            record.clientip = "-"
        return True


def set_logger(name):
    global logger
    logger = logging.getLogger(name)

    # 清除已有的处理器，防止重复添加
    if logger.handlers:
        logger.handlers = []

    # 禁止日志传播到根logger，避免重复输出
    logger.propagate = False

    logger.setLevel(logging.DEBUG)

    # 文件日志使用普通格式
    file_format = logging.Formatter("%(asctime)s - %(clientip)s - %(filename)s LineNo:%(lineno)d - %(levelname)s - %(message)s")

    # 控制台日志使用彩色格式
    console_format = colorlog.ColoredFormatter(
        "%(blue)s%(asctime)s%(reset)s - %(log_color)s%(levelname)s%(reset)s - %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
        secondary_log_colors={"asctime": {"": "blue"}},
        reset=True,
    )

    # 在当前目录下创建日志目录避免报错
    logger_config = conf.get("logger") or {}
    dir = logger_config.get("dir", "logs")
    if os.path.exists(dir) is False:
        os.makedirs(dir, exist_ok=True)
    filename = dir + "/{}.log".format(logger.name)

    time_rotating_handler = TimedRotatingFileHandler(filename, when="midnight", interval=1, backupCount=5, encoding="utf-8")
    time_rotating_handler.setLevel(logging.DEBUG)
    time_rotating_handler.setFormatter(file_format)
    logger.addHandler(time_rotating_handler)

    # 创建并设置过滤器，为没有clientip的日志记录提供默认值
    time_rotating_handler.addFilter(DefaultClientIPFilter())

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(console_format)
    logger.addHandler(stream_handler)

    stream_handler.addFilter(DefaultClientIPFilter())
    return logger


# 设置默认日志记录器
logger = set_logger("copilot")
