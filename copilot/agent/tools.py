from typing import Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import json


class CalculatorInput(BaseModel):
    """计算器工具的输入模式"""

    expression: str = Field(description="数学表达式，例如：2 + 2 * 3")


class CalculatorTool(BaseTool):
    """简单的计算器工具"""

    def __init__(self):
        super().__init__(
            name="calculator",
            description="执行基本的数学计算。输入数学表达式，返回计算结果。",
        )

    def _run(self, expression: str) -> str:
        """执行计算"""
        try:
            # 安全地评估数学表达式
            allowed_names = {k: v for k, v in __builtins__.items() if k in ["abs", "round", "min", "max", "sum"]}
            allowed_names.update(
                {
                    "pow": pow,
                    "sqrt": lambda x: x**0.5,
                }
            )

            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return f"计算结果：{expression} = {result}"
        except Exception as e:
            return f"计算错误：{str(e)}"

    async def _arun(self, expression: str) -> str:
        """异步执行计算"""
        return self._run(expression)


class WeatherInput(BaseModel):
    """天气查询工具的输入模式"""

    city: str = Field(description="城市名称，例如：北京")


class WeatherTool(BaseTool):
    """天气查询工具（示例）"""

    def __init__(self):
        super().__init__(
            name="weather",
            description="查询指定城市的天气信息。",
        )

    def _run(self, city: str) -> str:
        """查询天气"""
        try:
            # 这里是示例实现，实际使用时需要接入真实的天气API
            # 例如：OpenWeatherMap, 和风天气等
            weather_data = {
                "北京": "晴天，温度25°C，湿度60%",
                "上海": "多云，温度28°C，湿度70%",
                "深圳": "小雨，温度30°C，湿度85%",
                "广州": "阴天，温度29°C，湿度75%",
            }

            result = weather_data.get(city, f"抱歉，暂时无法获取{city}的天气信息")
            return f"{city}的天气：{result}"
        except Exception as e:
            return f"天气查询错误：{str(e)}"

    async def _arun(self, city: str) -> str:
        """异步查询天气"""
        return self._run(city)


class SearchInput(BaseModel):
    """搜索工具的输入模式"""

    query: str = Field(description="搜索关键词")


class SearchTool(BaseTool):
    """网络搜索工具（示例）"""

    def __init__(self):
        super().__init__(
            name="search",
            description="搜索互联网上的信息。",
        )

    def _run(self, query: str) -> str:
        """执行搜索"""
        try:
            # 这里是示例实现，实际使用时可以接入真实的搜索API
            # 例如：Google Search API, Bing Search API等
            return f"搜索结果：关于'{query}'的信息（这是一个示例结果）"
        except Exception as e:
            return f"搜索错误：{str(e)}"

    async def _arun(self, query: str) -> str:
        """异步搜索"""
        return self._run(query)


def get_default_tools():
    """获取默认工具集合"""
    return [CalculatorTool(), WeatherTool(), SearchTool()]


def create_custom_tool(tool_name: str, tool_description: str, func):
    """创建自定义工具"""

    class CustomTool(BaseTool):
        def __init__(self, name: str, description: str, func):
            super().__init__(name=name, description=description)
            self.func = func

        def _run(self, input: str) -> str:
            try:
                return self.func(input)
            except Exception as e:
                return f"工具执行错误：{str(e)}"

        async def _arun(self, input: str) -> str:
            return self._run(input)

    return CustomTool(tool_name, tool_description, func)
