import asyncio
import time
from typing import Optional

from openai import AsyncOpenAI

from src.common.logger import get_logger
from src.plugin_system import message_api

from ..models import SearchRequest
from ..prompts import SearchPromptBuilder
from ..utils.model_response import extract_completion_content

logger = get_logger("search_service")

class SearchService:
    """联网搜索服务：负责上下文、重试、限流、模型调用"""

    _semaphore: Optional[asyncio.Semaphore] = None
    _semaphore_max_concurrency: Optional[int] = None

    def __init__(self, plugin_context):
        """
        plugin_context 可以是 Tool / Command / 其他拥有 get_config 的对象
        """
        self.ctx = plugin_context

    def _get_semaphore(self) -> asyncio.Semaphore:
        max_concurrency = int(self.ctx.get_config("search.max_concurrency", 3) or 3)

        if max_concurrency <= 0:
            max_concurrency = 1

        if (
            self.__class__._semaphore is None
            or self.__class__._semaphore_max_concurrency != max_concurrency
        ):
            self.__class__._semaphore = asyncio.Semaphore(max_concurrency)
            self.__class__._semaphore_max_concurrency = max_concurrency
            logger.info(f"[grok_search_plugin] 更新搜索并发限制 max_concurrency={max_concurrency}")

        return self.__class__._semaphore

    def build_request(self, question: str, image_context: str = "") -> SearchRequest:
        context_text = self._get_recent_context()
        current_time_text = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        return SearchRequest(
            question=question,
            context_text=context_text,
            current_time_text=current_time_text,
            image_context=image_context or "",
        )

    def _get_recent_context(self) -> str:
        try:
            if not self.ctx.get_config("search.enable_context", True):
                return "（未启用聊天上下文）"

            time_gap = self.ctx.get_config("search.time_gap", 270)
            max_limit = self.ctx.get_config("search.max_limit", 10)

            current = time.time()
            earlier = current - time_gap
            messages = message_api.get_messages_by_time(earlier, current, limit=max_limit)
            context_text = message_api.build_readable_messages_to_str(messages)

            return context_text or "（无可用聊天上下文）"
        except Exception as e:
            logger.warning(f"[grok_search_plugin] 获取上下文失败: {e}")
            return "（上下文获取失败）"

    async def search(self, question: str, image_context: str = "") -> str:
        question = (question or "").strip()
        if not question:
            raise ValueError("缺少必要参数: question")

        request = self.build_request(question, image_context)
        retry_attempts = self.ctx.get_config("search.retry_attempts", 3)
        retry_wait_min = self.ctx.get_config("search.retry_wait_min", 1.5)
        retry_wait_max = self.ctx.get_config("search.retry_wait_max", 8.0)
        semaphore = self._get_semaphore()

        last_error = None

        for attempt in range(1, retry_attempts + 1):
            try:
                async with semaphore:
                    return await self._search_once(request)
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    f"[grok_search_plugin] 搜索超时 "
                    f"({attempt}/{retry_attempts}) question={question}"
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"搜索失败 "
                    f"({attempt}/{retry_attempts}) question={question}, error={e}"
                )

            if attempt < retry_attempts:
                wait_time = min(retry_wait_min * (2 ** (attempt - 1)), retry_wait_max)
                await asyncio.sleep(wait_time)

        if isinstance(last_error, asyncio.TimeoutError):
            return "搜索请求超时，请稍后再试。"

        return "搜索服务暂时不可用，请稍后再试。"

    async def _search_once(self, request: SearchRequest) -> str:
        timeout = self.ctx.get_config("search.timeout", 20.0)
        direction = self.ctx.get_config(
            "search.direction",
            "请优先关注事实准确性、时效性和来源可靠性。"
        )
        system_prompt = self.ctx.get_config(
            "prompt.system_prompt",
            "你是专业的联网检索助手，擅长根据外部信息生成可靠、简洁、及时的总结。"
        )

        if request.image_context.strip():
            prompt = SearchPromptBuilder.build_image_search_prompt(
                question=request.question,
                context_text=request.context_text,
                current_time_text=request.current_time_text,
                direction=direction,
                image_context=request.image_context,
            )
        else:
            prompt = SearchPromptBuilder.build_text_search_prompt(
                question=request.question,
                context_text=request.context_text,
                current_time_text=request.current_time_text,
                direction=direction,
            )

        client = AsyncOpenAI(
            base_url=self.ctx.get_config("model.base_url"),
            api_key=self.ctx.get_config("model.api_key"),
        )

        logger.info(
            f"开始搜索 question={request.question} "
        )

        completion = await client.chat.completions.create(
            model=self.ctx.get_config("model.model"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=self.ctx.get_config("model.temperature", 0.2),
            timeout=timeout,
        )

        logger.debug(f"[grok_search_plugin] search completion type={type(completion)}")
        content = extract_completion_content(completion)

        if not content:
            return "暂无足够可信的搜索结果。"

        return content
