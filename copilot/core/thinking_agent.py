"""
思考Agent - 专门负责解读用户输入、分析问题和制定处理步骤
不执行实际工具，只进行思考和规划
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from copilot.core.llm_factory import LLMFactory
from copilot.utils.logger import logger


@dataclass
class ThinkingStep:
    """思考步骤"""
    step_id: str
    description: str
    reasoning: str
    expected_tools: List[str] = None
    parameters: Dict[str, Any] = None
    priority: int = 1
    dependencies: List[str] = None


@dataclass
class ThinkingResult:
    """思考结果"""
    user_intent: str
    problem_analysis: str
    execution_plan: List[ThinkingStep]
    estimated_complexity: str  # low, medium, high
    suggested_model: str = None
    context_requirements: Dict[str, Any] = None
    timestamp: datetime = None


class ThinkingAgent:
    """思考Agent - 专门负责分析和规划，不执行实际操作"""

    def __init__(self, provider: str = "deepseek", model_name: str = "deepseek-chat", **llm_kwargs):
        """
        初始化思考Agent

        Args:
            provider: LLM提供商（建议使用推理能力强的模型）
            model_name: 模型名称
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.provider = provider
        self.model_name = model_name
        self.llm_kwargs = llm_kwargs
        
        # 初始化LLM（使用更高的temperature以获得更多创造性思考）
        llm_config = {
            "temperature": 0.7,  # 稍微提高创造性
            "max_tokens": 4000,  # 确保有足够空间进行详细思考
            **llm_kwargs
        }
        
        self.llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_config)
        
        # 思考prompt模板
        self.thinking_prompt = self._build_thinking_prompt()
        
        logger.info(f"ThinkingAgent initialized with {provider}/{model_name}")

    def _build_thinking_prompt(self) -> str:
        """构建思考Agent的prompt模板"""
        return """你是一个专业的AI思考助手，负责分析用户输入并制定详细的处理计划。你不执行任何实际操作，只进行深度思考和规划。

你的任务：
1. 理解用户的真实意图和需求
2. 分析问题的复杂程度和处理方式
3. 制定详细的执行步骤计划
4. 建议合适的工具和参数

可用的工具类型包括：
- 文件操作工具（读取、编写、搜索文件）
- 系统工具（命令行执行、目录操作）
- 网络工具（HTTP请求、API调用）
- 数据处理工具（JSON处理、文本分析）
- 开发工具（代码分析、测试运行）
- MCP扩展工具（根据实际配置）

请按以下JSON格式回复你的思考结果：

```json
{
    "user_intent": "用户的真实意图描述",
    "problem_analysis": "问题分析和背景理解",
    "execution_plan": [
        {
            "step_id": "step_1",
            "description": "步骤描述",
            "reasoning": "为什么需要这个步骤",
            "expected_tools": ["tool_name1", "tool_name2"],
            "parameters": {"param1": "value1"},
            "priority": 1,
            "dependencies": []
        }
    ],
    "estimated_complexity": "low|medium|high",
    "suggested_model": "建议使用的执行模型",
    "context_requirements": {
        "need_history": true,
        "max_history_messages": 10,
        "special_context": "特殊上下文需求"
    }
}
```

注意事项：
- 详细分析用户意图，不要遗漏隐含需求
- 步骤要具体可执行，避免模糊描述
- 合理安排步骤顺序和依赖关系
- 根据复杂度建议合适的执行模型
- 考虑错误处理和备选方案

现在开始分析用户输入："""

    async def think(
        self, 
        user_input: str, 
        context: Dict[str, Any] = None, 
        conversation_history: List[Dict] = None
    ) -> ThinkingResult:
        """
        分析用户输入并生成思考结果

        Args:
            user_input: 用户输入
            context: 上下文信息（会话信息、用户偏好等）
            conversation_history: 对话历史

        Returns:
            ThinkingResult: 详细的思考和规划结果
        """
        try:
            # 构建完整的思考输入
            thinking_input = self._build_thinking_input(user_input, context, conversation_history)
            
            logger.info(f"ThinkingAgent开始分析用户输入: {user_input[:100]}...")
            
            # 调用LLM进行思考
            response = await self.llm.ainvoke(thinking_input)
            
            # 解析思考结果
            result = self._parse_thinking_response(response.content)
            
            logger.info(f"ThinkingAgent完成分析，生成了{len(result.execution_plan)}个执行步骤")
            
            return result
            
        except Exception as e:
            logger.error(f"ThinkingAgent思考过程出错: {str(e)}")
            # 返回基础的思考结果
            return self._create_fallback_result(user_input)

    def _build_thinking_input(
        self, 
        user_input: str, 
        context: Dict[str, Any] = None, 
        conversation_history: List[Dict] = None
    ) -> str:
        """构建完整的思考输入"""
        
        input_parts = [self.thinking_prompt]
        
        # 添加上下文信息
        if context:
            input_parts.append(f"\n当前上下文：\n{json.dumps(context, ensure_ascii=False, indent=2)}")
        
        # 添加对话历史（最近5轮）
        if conversation_history:
            recent_history = conversation_history[-5:]  # 只取最近5轮
            history_text = "\n".join([
                f"{msg['role']}: {msg['content'][:200]}..." if len(msg['content']) > 200 else f"{msg['role']}: {msg['content']}"
                for msg in recent_history
            ])
            input_parts.append(f"\n对话历史：\n{history_text}")
        
        # 添加用户输入
        input_parts.append(f"\n用户输入：\n{user_input}")
        
        input_parts.append("\n请开始你的深度思考分析：")
        
        return "\n".join(input_parts)

    def _parse_thinking_response(self, response: str) -> ThinkingResult:
        """解析LLM的思考响应"""
        try:
            # 提取JSON部分
            json_start = response.find("```json")
            json_end = response.find("```", json_start + 7)
            
            if json_start == -1 or json_end == -1:
                # 如果没有找到代码块，尝试直接解析整个响应
                json_str = response
            else:
                json_str = response[json_start + 7:json_end].strip()
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 构建ThinkingStep对象
            execution_plan = []
            for step_data in data.get("execution_plan", []):
                step = ThinkingStep(
                    step_id=step_data.get("step_id", f"step_{len(execution_plan)+1}"),
                    description=step_data.get("description", ""),
                    reasoning=step_data.get("reasoning", ""),
                    expected_tools=step_data.get("expected_tools", []),
                    parameters=step_data.get("parameters", {}),
                    priority=step_data.get("priority", 1),
                    dependencies=step_data.get("dependencies", [])
                )
                execution_plan.append(step)
            
            # 构建ThinkingResult对象
            result = ThinkingResult(
                user_intent=data.get("user_intent", ""),
                problem_analysis=data.get("problem_analysis", ""),
                execution_plan=execution_plan,
                estimated_complexity=data.get("estimated_complexity", "medium"),
                suggested_model=data.get("suggested_model"),
                context_requirements=data.get("context_requirements", {}),
                timestamp=datetime.now()
            )
            
            return result
            
        except Exception as e:
            logger.warning(f"解析思考结果失败: {str(e)}，使用原始响应")
            return self._parse_fallback_response(response)

    def _parse_fallback_response(self, response: str) -> ThinkingResult:
        """备用解析方法，当JSON解析失败时使用"""
        # 基于响应内容创建简单的执行计划
        steps = [
            ThinkingStep(
                step_id="step_1",
                description="根据用户输入直接处理",
                reasoning="无法解析详细计划，直接执行用户请求",
                expected_tools=[],
                parameters={}
            )
        ]
        
        return ThinkingResult(
            user_intent="需要进一步分析",
            problem_analysis=response[:500],  # 取前500字符作为分析
            execution_plan=steps,
            estimated_complexity="medium",
            timestamp=datetime.now()
        )

    def _create_fallback_result(self, user_input: str) -> ThinkingResult:
        """创建备用的思考结果"""
        steps = [
            ThinkingStep(
                step_id="step_1",
                description=f"处理用户请求: {user_input[:100]}",
                reasoning="思考Agent出错，直接处理用户输入",
                expected_tools=[],
                parameters={}
            )
        ]
        
        return ThinkingResult(
            user_intent=user_input[:200],
            problem_analysis="思考Agent暂时无法分析，将直接处理用户请求",
            execution_plan=steps,
            estimated_complexity="medium",
            timestamp=datetime.now()
        )

    async def refine_plan(self, current_plan: ThinkingResult, feedback: str) -> ThinkingResult:
        """
        根据反馈优化执行计划

        Args:
            current_plan: 当前执行计划
            feedback: 执行反馈或用户反馈

        Returns:
            ThinkingResult: 优化后的执行计划
        """
        try:
            refine_prompt = f"""
基于以下执行计划和反馈，请优化和调整计划：

当前计划：
{json.dumps(current_plan.__dict__, ensure_ascii=False, default=str, indent=2)}

反馈信息：
{feedback}

请提供优化后的执行计划，格式与之前相同的JSON格式。
重点关注：
1. 根据反馈调整步骤
2. 优化工具选择
3. 改进参数配置
4. 调整步骤顺序

优化后的计划：
"""
            
            response = await self.llm.ainvoke(refine_prompt)
            refined_result = self._parse_thinking_response(response.content)
            
            logger.info("ThinkingAgent已根据反馈优化执行计划")
            return refined_result
            
        except Exception as e:
            logger.error(f"计划优化失败: {str(e)}")
            return current_plan  # 返回原计划

    def get_thinking_stats(self) -> Dict[str, Any]:
        """获取思考Agent的统计信息"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "capabilities": [
                "intent_analysis",
                "problem_decomposition", 
                "execution_planning",
                "complexity_assessment",
                "plan_optimization"
            ],
            "config": self.llm_kwargs
        } 