import os
from typing import List, Optional

from langchain.tools import BaseTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAI


class DeepSeekChatModel(BaseChatModel):
    """DeepSeek聊天模型包装器"""

    client: OpenAI
    model_name: str = "deepseek-chat"
    temperature: float = 0.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key"), base_url="https://api.deepseek.com/v1")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """生成响应"""
        formatted_messages = []
        for msg in messages:
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "human":
                    formatted_messages.append({"role": "user", "content": msg.content})
                elif msg.type == "ai":
                    formatted_messages.append({"role": "assistant", "content": msg.content})
                elif msg.type == "system":
                    formatted_messages.append({"role": "system", "content": msg.content})

        response = self.client.chat.completions.create(model=self.model_name, messages=formatted_messages, temperature=self.temperature, **kwargs)

        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        message = AIMessage(content=response.choices[0].message.content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "deepseek-chat"


class ArticleAgent:
    """基于LangChain和DeepSeek的智能代理"""

    def __init__(self, tools: List[BaseTool], system_prompt: str = "你是一个有用的AI助手。"):
        self.tools = tools
        self.system_prompt = system_prompt
        self.llm = DeepSeekChatModel()
        self.agent_executor = self._create_agent_executor()

    def _create_agent_executor(self):
        """创建代理执行器"""

        # 简化版本：直接创建一个处理器
        class SimpleExecutor:
            def __init__(self, llm, tools, system_prompt):
                self.llm = llm
                self.tools = tools
                self.system_prompt = system_prompt

            async def ainvoke(self, inputs):
                user_input = inputs.get("input", "")
                chat_history = inputs.get("chat_history", [])

                # 构建消息
                messages = []

                # 系统消息
                from langchain_core.messages import SystemMessage

                messages.append(SystemMessage(content=self.system_prompt))

                # 添加历史消息
                for msg in chat_history:
                    if isinstance(msg, HumanMessage):
                        messages.append(msg)
                    elif isinstance(msg, AIMessage):
                        messages.append(msg)

                # 添加工具信息到系统提示
                if self.tools:
                    tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
                    tool_msg = SystemMessage(content=f"可用工具：\n{tool_descriptions}")
                    messages.append(tool_msg)

                # 添加用户输入
                from langchain_core.messages import HumanMessage as LCHumanMessage

                messages.append(LCHumanMessage(content=user_input))

                # 调用模型
                result = self.llm._generate(messages)
                return {"output": result.generations[0].message.content}

        return SimpleExecutor(self.llm, self.tools, self.system_prompt)

    async def run(self, input_text: str, chat_history: Optional[List] = None) -> str:
        """运行代理处理用户输入"""
        try:
            result = await self.agent_executor.ainvoke({"input": input_text, "chat_history": chat_history or []})
            return result["output"]
        except Exception as e:
            return f"处理请求时出现错误: {str(e)}"

    def add_tool(self, tool: BaseTool):
        """添加工具"""
        self.tools.append(tool)
        # 重新创建执行器
        self.agent_executor = self._create_agent_executor()

    def get_tools(self) -> List[str]:
        """获取工具列表"""
        return [tool.name for tool in self.tools]
