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

    def __init__(self, provider: str = "deepseek", model_name: str = "deepseek-chat", mcp_tools: List = None, **llm_kwargs):
        """
        初始化思考Agent

        Args:
            provider: LLM提供商（建议使用推理能力强的模型）
            model_name: 模型名称
            mcp_tools: MCP工具列表（用于分析可用工具）
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.provider = provider
        self.model_name = model_name
        self.mcp_tools = mcp_tools or []
        self.llm_kwargs = llm_kwargs

        # 初始化LLM（使用更高的temperature以获得更多创造性思考）
        llm_config = {"temperature": 0.7, "max_tokens": 4000, **llm_kwargs}  # 稍微提高创造性  # 确保有足够空间进行详细思考

        self.llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_config)

        # 思考prompt模板
        self.thinking_prompt = self._build_thinking_prompt()

        logger.info(f"ThinkingAgent initialized with {provider}/{model_name}, {len(self.mcp_tools)} MCP tools available")

    @classmethod
    async def create_with_mcp_tools(
        cls,
        provider: str = "deepseek",
        model_name: str = "deepseek-chat",
        **llm_kwargs,
    ):
        """
        异步创建思考Agent实例，自动加载MCP工具

        Args:
            provider: LLM提供商
            model_name: 模型名称
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            ThinkingAgent: 配置好的思考Agent实例
        """
        # 获取可用的MCP工具
        from copilot.core.mcp_tool_wrapper import MCPToolWrapper

        mcp_tools = await MCPToolWrapper.get_mcp_tools()

        logger.info(f"Creating ThinkingAgent with provider: {provider}, model: {model_name}, mcp_tools: {len(mcp_tools)}")

        # 创建思考Agent实例
        return cls(
            provider=provider,
            model_name=model_name,
            mcp_tools=mcp_tools,
            **llm_kwargs,
        )

    def _build_thinking_prompt(self) -> str:
        """构建思考Agent的prompt模板 - 包含可用工具信息"""
        prompt = """你是一个专业的AI思考助手，负责分析用户输入并制定处理计划。

请以自然、流畅的方式分析用户的需求，并制定执行计划。你可以这样思考：

1. 首先理解用户想要什么
2. 分析这个问题的复杂程度
3. 制定具体的执行步骤
4. 考虑需要什么工具和资源

请用自然语言表达你的思考过程，就像在和朋友讨论如何解决问题一样。

现在开始分析用户输入："""

        # 如果有可用的MCP工具，添加到prompt中
        if self.mcp_tools:
            prompt += "\n\n📋 **可用的工具列表**:\n"
            for i, tool in enumerate(self.mcp_tools, 1):
                tool_name = getattr(tool, "name", str(tool))
                tool_desc = getattr(tool, "description", "无描述")
                prompt += f"{i}. **{tool_name}**: {tool_desc}\n"

            prompt += "\n💡 **提示**: 在制定执行计划时，请考虑使用上述工具来完成特定任务。"

        return prompt

    async def think(self, user_input: str, context: Dict[str, Any] = None, conversation_history: List[Dict] = None) -> ThinkingResult:
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

    async def think_stream(self, user_input: str, context: Dict[str, Any] = None, conversation_history: List[Dict] = None):
        """
        流式思考方法 - 简化版本，直接输出AI的思考过程

        Args:
            user_input: 用户输入
            context: 上下文信息（会话信息、用户偏好等）
            conversation_history: 对话历史

        Yields:
            Dict[str, Any]: 流式思考数据
        """
        try:
            # 构建完整的思考输入
            thinking_input = self._build_thinking_input(user_input, context, conversation_history)

            logger.info(f"ThinkingAgent开始流式分析用户输入: {user_input[:100]}...")

            # 使用流式调用，直接输出AI的思考过程
            full_response = ""
            thinking_buffer = ""

            async for chunk in self.llm.astream(thinking_input):
                if hasattr(chunk, "content") and chunk.content:
                    content = str(chunk.content)
                    full_response += content
                    thinking_buffer += content

                    # 简单的分块输出：当有完整句子或足够长度时输出
                    if len(thinking_buffer) > 30 and any(char in thinking_buffer for char in "。！？\n"):
                        yield {
                            "type": "thinking_chunk",
                            "content": thinking_buffer.strip(),
                            "phase": "thinking",
                            "timestamp": datetime.now().isoformat(),
                        }
                        thinking_buffer = ""

                    # 简单的分块输出：当有完整句子或足够长度时输出
                    if len(thinking_buffer) > 30 and any(char in thinking_buffer for char in "。！？\n"):
                        # 清理内容，移除markdown标记
                        clean_content = self._clean_thinking_chunk(thinking_buffer.strip())
                        if clean_content:
                            yield {
                                "type": "thinking_chunk",
                                "content": clean_content,
                                "phase": "thinking",
                                "timestamp": datetime.now().isoformat(),
                            }
                        thinking_buffer = ""

            # 输出剩余的思考内容
            if thinking_buffer.strip():
                clean_content = self._clean_thinking_chunk(thinking_buffer.strip())
                if clean_content:
                    yield {"type": "thinking_chunk", "content": clean_content, "phase": "thinking", "timestamp": datetime.now().isoformat()}

            # 思考完成，创建JSON格式的结构化数据
            if full_response:
                # 创建结构化的思考结果
                thinking_result = self._create_structured_result(full_response, user_input)

                # 解析JSON字符串为字典，用于后续处理
                try:
                    thinking_data = json.loads(thinking_result)
                except json.JSONDecodeError:
                    # 如果JSON解析失败，创建基础数据结构
                    thinking_data = {
                        "status": "completed",
                        "user_input": user_input,
                        "user_intent": user_input[:200] + "..." if len(user_input) > 200 else user_input,
                        "problem_analysis": "思考分析完成",
                        "execution_plan": [
                            {
                                "step_id": "step_1",
                                "description": "基于思考结果执行用户请求",
                                "reasoning": "根据AI的思考分析执行任务",
                                "expected_tools": [],
                                "parameters": {},
                                "priority": 1,
                                "dependencies": [],
                            }
                        ],
                        "complexity": "medium",
                        "complexity_level": "medium",
                    }

                yield {
                    "type": "thinking_complete",
                    "content": thinking_result,  # 保持原有的content字段
                    "thinking_data": thinking_data,  # 添加thinking_data字段供coordinator使用
                    "phase": "thinking",
                    "timestamp": datetime.now().isoformat(),
                }

            logger.info("ThinkingAgent完成流式分析")

        except Exception as e:
            logger.error(f"ThinkingAgent流式思考过程出错: {str(e)}")

            yield {
                "type": "thinking_error",
                "content": f"🚫 思考过程遇到错误: {str(e)}",
                "phase": "thinking",
                "timestamp": datetime.now().isoformat(),
            }

            # 创建简单的备用结果 - JSON格式
            fallback_result = {
                "status": "error",
                "user_input": user_input,
                "user_intent": user_input[:200] + "..." if len(user_input) > 200 else user_input,
                "problem_analysis": "思考过程遇到问题，将直接处理用户请求",
                "key_points": ["系统将直接处理用户请求"],
                "execution_plan": [
                    {
                        "step_id": "step_1",
                        "description": f"处理用户请求: {user_input[:100]}{'...' if len(user_input) > 100 else ''}",
                        "reasoning": "思考Agent出错，直接处理用户输入",
                        "expected_tools": ["web_search"],  # 默认建议使用网络搜索
                        "parameters": {},
                        "priority": 1,
                        "dependencies": [],
                    }
                ],
                "estimated_complexity": "medium",
                "complexity_level": "medium",
                "suggested_model": None,
                "context_requirements": {},
                "thinking_duration": "error",
                "timestamp": datetime.now().isoformat(),
                "metadata": {"response_length": 0, "key_points_count": 1, "analysis_quality": "error"},
            }

            yield {
                "type": "thinking_complete",
                "content": json.dumps(fallback_result, ensure_ascii=False, indent=2),
                "thinking_data": fallback_result,  # 添加thinking_data字段供coordinator使用
                "phase": "thinking",
                "timestamp": datetime.now().isoformat(),
            }

    def _create_simple_summary(self, full_response: str, user_input: str) -> str:
        """创建简单的思考总结 - 优化版本"""

        # 清理和格式化思考内容
        cleaned_response = self._clean_summary_content(full_response)

        # 提取关键信息
        summary_parts = []

        # 1. 用户意图（从用户输入提取）
        user_intent = user_input[:100] + "..." if len(user_input) > 100 else user_input
        summary_parts.append(f"🎯 **用户需求**: {user_intent}")

        # 2. 思考要点（从AI响应中提取）
        key_points = self._extract_key_points(cleaned_response)
        if key_points:
            summary_parts.append("💭 **思考要点**")
            for i, point in enumerate(key_points, 1):
                summary_parts.append(f"{i}. {point}")

        # 3. 执行计划
        summary_parts.append("📋 **执行计划**")
        summary_parts.append("1. 基于分析结果处理用户请求")

        # 4. 复杂度评估
        complexity = self._assess_complexity(cleaned_response)
        summary_parts.append(f"\n{complexity}")

        return "\n\n".join(summary_parts)

    def _clean_summary_content(self, content: str) -> str:
        """清理总结内容，移除markdown标记等"""
        if not content:
            return ""

        # 移除markdown标记
        content = content.replace("###", "").replace("##", "").replace("#", "")
        content = content.replace("**", "").replace("*", "")
        content = content.replace("```", "").replace("`", "")

        # 移除多余的空白字符
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        content = "\n".join(lines)

        return content

    def _extract_key_points(self, content: str) -> List[str]:
        """从内容中提取关键要点"""
        points = []

        # 按句子分割
        sentences = content.split("。")

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 15 and len(sentence) < 120:  # 合适的长度
                # 移除常见的开头词
                clean_sentence = sentence
                for prefix in ["首先", "其次", "然后", "接着", "最后", "另外", "此外", "同时"]:
                    if clean_sentence.startswith(prefix):
                        clean_sentence = clean_sentence[len(prefix) :].strip()

                if clean_sentence and len(clean_sentence) > 10:
                    points.append(clean_sentence)

                # 最多提取3个要点
                if len(points) >= 3:
                    break

        return points

    def _assess_complexity(self, content: str) -> str:
        """评估复杂度"""
        content_lower = content.lower()

        # 简单判断逻辑
        if any(word in content_lower for word in ["简单", "基础", "容易", "直接"]):
            return "🟢 **复杂度**: low"
        elif any(word in content_lower for word in ["复杂", "困难", "高级", "专业"]):
            return "🔴 **复杂度**: high"
        else:
            return "🟡 **复杂度**: medium"

    def _extract_suggested_tools(self, content: str) -> List[str]:
        """从思考内容中提取建议的工具，基于实际可用的MCP工具"""
        suggested_tools = []
        content_lower = content.lower()

        if not self.mcp_tools:
            return suggested_tools

        # 遍历可用的MCP工具，检查是否在思考内容中被提及
        for tool in self.mcp_tools:
            tool_name = getattr(tool, "name", str(tool)).lower()
            tool_desc = getattr(tool, "description", "").lower()

            # 检查工具名称是否在内容中被提及
            if tool_name in content_lower:
                suggested_tools.append(tool_name)
                continue

            # 检查工具描述中的关键词是否在内容中被提及
            # 提取描述中的关键词（通常是功能描述）
            desc_keywords = self._extract_tool_keywords(tool_desc)
            for keyword in desc_keywords:
                if keyword in content_lower:
                    suggested_tools.append(tool_name)
                    break

        # 去重并返回
        return list(set(suggested_tools))

    def _extract_tool_keywords(self, tool_desc: str) -> List[str]:
        """从工具描述中提取关键词"""
        keywords = []

        # 常见的功能关键词
        common_keywords = [
            "搜索",
            "查询",
            "查找",
            "获取",
            "读取",
            "写入",
            "保存",
            "分析",
            "计算",
            "翻译",
            "搜索",
            "查询",
            "查找",
            "获取",
            "读取",
            "写入",
            "保存",
            "分析",
            "计算",
            "翻译",
            "search",
            "query",
            "find",
            "get",
            "read",
            "write",
            "save",
            "analyze",
            "calculate",
            "translate",
            "学术",
            "文献",
            "论文",
            "专利",
            "网络",
            "文件",
            "代码",
            "图像",
            "图片",
            "academic",
            "literature",
            "paper",
            "patent",
            "web",
            "file",
            "code",
            "image",
            "picture",
        ]

        desc_lower = tool_desc.lower()
        for keyword in common_keywords:
            if keyword in desc_lower:
                keywords.append(keyword)

        return keywords

    def _build_thinking_input(self, user_input: str, context: Dict[str, Any] = None, conversation_history: List[Dict] = None) -> str:
        """构建完整的思考输入"""

        input_parts = [self.thinking_prompt]

        # 添加上下文信息
        if context:
            input_parts.append(f"\n当前上下文：\n{json.dumps(context, ensure_ascii=False, indent=2)}")

        # 添加对话历史（最近5轮）
        if conversation_history:
            recent_history = conversation_history[-5:]  # 只取最近5轮
            history_text = "\n".join(
                [
                    f"{msg['role']}: {msg['content'][:200]}..." if len(msg["content"]) > 200 else f"{msg['role']}: {msg['content']}"
                    for msg in recent_history
                ]
            )
            input_parts.append(f"\n对话历史：\n{history_text}")

        # 添加用户输入
        input_parts.append(f"\n用户输入：\n{user_input}")

        input_parts.append("\n请开始你的深度思考分析：")

        return "\n".join(input_parts)

    def _parse_thinking_response(self, response: str) -> ThinkingResult:
        """解析LLM的思考响应"""
        try:
            # 新的解析方法：从自然语言格式中提取结构化信息
            result = self._parse_natural_thinking_response(response)
            return result

        except Exception as e:
            logger.warning(f"解析思考结果失败: {str(e)}，使用原始响应")
            return self._parse_fallback_response(response)

    def _parse_natural_thinking_response(self, response: str) -> ThinkingResult:
        """解析自然语言格式的思考响应"""

        # 提取用户意图
        user_intent = self._extract_section_content(response, "用户意图分析")

        # 提取问题分析
        problem_analysis = self._extract_section_content(response, "问题背景理解")

        # 提取执行计划
        execution_plan_text = self._extract_section_content(response, "执行计划制定")
        execution_plan = self._parse_execution_plan(execution_plan_text)

        # 提取复杂度评估
        complexity_text = self._extract_section_content(response, "复杂度评估")
        estimated_complexity = self._extract_complexity(complexity_text)

        # 提取建议模型
        suggested_model = self._extract_section_content(response, "建议模型")

        # 构建ThinkingResult对象
        result = ThinkingResult(
            user_intent=user_intent or "需要进一步分析",
            problem_analysis=problem_analysis or "问题分析中",
            execution_plan=execution_plan,
            estimated_complexity=estimated_complexity,
            suggested_model=suggested_model,
            context_requirements={},
            timestamp=datetime.now(),
        )

        return result

    def _extract_section_content(self, text: str, section_name: str) -> str:
        """提取指定章节的内容"""
        try:
            # 查找章节开始
            start_marker = f"**{section_name}**"
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return ""

            # 查找下一个章节或文档结束
            content_start = start_idx + len(start_marker)
            next_section_start = text.find("**", content_start)

            if next_section_start == -1:
                # 没有下一个章节，取到文档结束
                content = text[content_start:].strip()
            else:
                # 取到下一个章节开始
                content = text[content_start:next_section_start].strip()

            # 只做基本的清理，保留AI的自然语言输出
            content = content.strip()

            # 移除可能的占位符标记，但保留实际内容
            if content.startswith("[") and content.endswith("]"):
                # 如果整个内容被方括号包围，可能是占位符
                inner_content = content[1:-1].strip()
                if len(inner_content) > 10:  # 如果内容足够长，认为是实际内容
                    content = inner_content
            elif content.startswith("[") and not content.endswith("]"):
                # 如果只有开始方括号，移除它
                content = content[1:].strip()

            return content.strip()

        except Exception as e:
            logger.debug(f"提取章节 {section_name} 失败: {str(e)}")
            return ""

    def _parse_execution_plan(self, plan_text: str) -> List[ThinkingStep]:
        """解析执行计划文本 - 增强版本"""
        steps = []
        if not plan_text:
            logger.debug("执行计划文本为空")
            return steps

        try:
            logger.debug(f"开始解析执行计划: {plan_text[:200]}...")

            # 按行分割
            lines = plan_text.split("\n")
            current_step = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                logger.debug(f"处理行: {line}")

                # 多种步骤识别模式
                step_created = False

                # 模式1: 数字. 描述
                if line[0].isdigit() and "." in line:
                    step_created = self._create_step_from_line(line, steps, current_step)
                    if step_created:
                        current_step = step_created

                # 模式2: 数字、描述
                elif line[0].isdigit() and "、" in line:
                    step_created = self._create_step_from_line(line.replace("、", "."), steps, current_step)
                    if step_created:
                        current_step = step_created

                # 模式3: - 描述
                elif line.startswith("- "):
                    step_created = self._create_step_from_line(f"{len(steps)+1}. {line[2:]}", steps, current_step)
                    if step_created:
                        current_step = step_created

                # 模式4: • 描述
                elif line.startswith("• "):
                    step_created = self._create_step_from_line(f"{len(steps)+1}. {line[2:]}", steps, current_step)
                    if step_created:
                        current_step = step_created

                # 如果不是新步骤，添加到当前步骤的描述中
                elif current_step and line and not step_created:
                    current_step.description += f" {line}"

            # 添加最后一个步骤
            if current_step:
                steps.append(current_step)

        except Exception as e:
            logger.debug(f"解析执行计划失败: {str(e)}")

        # 如果没有解析到步骤，尝试从整个文本中提取
        if not steps:
            steps = self._extract_steps_from_text(plan_text)

        # 如果还是没有步骤，创建默认步骤
        if not steps:
            logger.debug("无法解析执行计划，创建默认步骤")
            steps = [
                ThinkingStep(
                    step_id="step_1",
                    description="根据用户输入直接处理",
                    reasoning="无法解析详细计划，直接执行用户请求",
                    expected_tools=[],
                    parameters={},
                )
            ]

        logger.debug(f"解析完成，共找到 {len(steps)} 个步骤")
        return steps

    def _create_step_from_line(self, line: str, steps: List[ThinkingStep], current_step: ThinkingStep = None) -> ThinkingStep:
        """从行创建步骤"""
        if current_step:
            steps.append(current_step)

        # 提取步骤描述
        if "：" in line:
            step_desc = line.split("：", 1)[-1]
        elif "." in line:
            step_desc = line.split(".", 1)[-1]
        else:
            step_desc = line

        step_desc = step_desc.strip()

        # 如果描述为空，使用整行作为描述
        if not step_desc:
            step_desc = line.strip()

        new_step = ThinkingStep(
            step_id=f"step_{len(steps)+1}",
            description=step_desc,
            reasoning="基于用户需求制定的执行步骤",
            expected_tools=[],
            parameters={},
            priority=len(steps) + 1,
            dependencies=[],
        )

        logger.debug(f"创建步骤: {step_desc}")
        return new_step

    def _extract_steps_from_text(self, text: str) -> List[ThinkingStep]:
        """从文本中提取步骤（备用方法）"""
        steps = []

        # 尝试按句子分割
        sentences = text.split("。")
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) > 10:  # 只处理有意义的句子
                steps.append(
                    ThinkingStep(
                        step_id=f"step_{i+1}",
                        description=sentence,
                        reasoning="从文本中提取的执行步骤",
                        expected_tools=[],
                        parameters={},
                        priority=i + 1,
                        dependencies=[],
                    )
                )

        return steps[:3]  # 最多返回3个步骤

    def _extract_complexity(self, complexity_text: str) -> str:
        """提取复杂度评估"""
        if not complexity_text:
            return "medium"

        complexity_text = complexity_text.lower()

        if any(word in complexity_text for word in ["简单", "low", "easy"]):
            return "low"
        elif any(word in complexity_text for word in ["复杂", "high", "difficult"]):
            return "high"
        else:
            return "medium"

    def _parse_fallback_response(self, response: str) -> ThinkingResult:
        """备用解析方法，当JSON解析失败时使用"""
        # 基于响应内容创建简单的执行计划
        steps = [
            ThinkingStep(
                step_id="step_1", description="根据用户输入直接处理", reasoning="无法解析详细计划，直接执行用户请求", expected_tools=[], parameters={}
            )
        ]

        return ThinkingResult(
            user_intent="需要进一步分析",
            problem_analysis=response[:500],  # 取前500字符作为分析
            execution_plan=steps,
            estimated_complexity="medium",
            timestamp=datetime.now(),
        )

    def _create_fallback_result(self, user_input: str) -> ThinkingResult:
        """创建备用的思考结果"""
        steps = [
            ThinkingStep(
                step_id="step_1",
                description=f"处理用户请求: {user_input[:100]}",
                reasoning="思考Agent出错，直接处理用户输入",
                expected_tools=[],
                parameters={},
            )
        ]

        return ThinkingResult(
            user_intent=user_input[:200],
            problem_analysis="思考Agent暂时无法分析，将直接处理用户请求",
            execution_plan=steps,
            estimated_complexity="medium",
            timestamp=datetime.now(),
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
            "capabilities": ["intent_analysis", "problem_decomposition", "execution_planning", "complexity_assessment", "plan_optimization"],
            "config": self.llm_kwargs,
        }

    def _clean_thinking_chunk(self, chunk: str) -> str:
        """清理思考分块内容，移除markdown标记等"""
        if not chunk:
            return ""

        # 移除markdown标记
        chunk = chunk.replace("###", "").replace("##", "").replace("#", "")
        chunk = chunk.replace("**", "").replace("*", "")
        chunk = chunk.replace("```", "").replace("`", "")

        # 移除多余的空白字符
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        chunk = "\n".join(lines)

        return chunk.strip()

    def _create_structured_result(self, full_response: str, user_input: str) -> str:
        """创建结构化的思考结果 - JSON格式"""

        # 清理和格式化思考内容
        cleaned_response = self._clean_summary_content(full_response)

        # 提取关键信息
        key_points = self._extract_key_points(cleaned_response)
        complexity = self._assess_complexity(cleaned_response)

        # 提取建议的工具
        suggested_tools = self._extract_suggested_tools(cleaned_response)

        # 构建结构化数据
        structured_data = {
            "status": "completed",
            "user_input": user_input,
            "user_intent": user_input[:200] + "..." if len(user_input) > 200 else user_input,
            "problem_analysis": cleaned_response[:800] + "..." if len(cleaned_response) > 800 else cleaned_response,
            "key_points": key_points,
            "execution_plan": [
                {
                    "step_id": "step_1",
                    "description": "基于思考结果执行用户请求",
                    "reasoning": "根据AI的思考分析执行任务",
                    "expected_tools": suggested_tools,  # 使用提取的工具信息
                    "parameters": {},
                    "priority": 1,
                    "dependencies": [],
                }
            ],
            "estimated_complexity": complexity.replace("🟢 **复杂度**: ", "").replace("🟡 **复杂度**: ", "").replace("🔴 **复杂度**: ", ""),
            "complexity_level": "low" if "🟢" in complexity else "high" if "🔴" in complexity else "medium",
            "suggested_model": None,
            "context_requirements": {},
            "suggested_tools": suggested_tools,  # 添加建议工具字段
            "thinking_duration": "completed",
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "response_length": len(full_response),
                "key_points_count": len(key_points),
                "analysis_quality": "good" if len(key_points) >= 2 else "basic",
                "tools_suggested": len(suggested_tools),
            },
        }

        return json.dumps(structured_data, ensure_ascii=False, indent=2)
