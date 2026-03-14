from typing import Any, Dict

from src.common.logger import get_logger
from src.plugin_system import BaseTool, ToolParamType

from ..services import SearchService
from ..services.image_resolver import ImageResolverService
from ..services.vision_service import VisionService
from ..utils import format_search_result

logger = get_logger("search_tool")


class GroundedSearchTool(BaseTool):
    name = "grounded_search"
    description = "当问题需要联网搜索时使用。适合热点、新闻、版本更新、事实核查等。"
    parameters = [
        ("question", ToolParamType.STRING, "要搜索的问题、关键词或主题", True, None),
    ]
    available_for_llm = True

    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, str]:
        question = str((function_args or {}).get("question", "")).strip()
        if not question:
            return {"name": self.name, "content": "搜索失败：缺少必要参数 question。"}

        try:
            service = SearchService(self)
            raw_result = await service.search(question)
            output_mode = self.get_config("search.output_mode", "brief")
            result = format_search_result(question, raw_result, output_mode)
            return {"name": self.name, "content": result}
        except Exception as e:
            logger.exception(f"Tool execute 异常: {e}")
            return {"name": self.name, "content": f"搜索失败：{str(e)}"}


class RecentImageSearchTool(BaseTool):
    name = "recent_image_search"
    description = (
        "当用户的问题与图片有关时使用，例如“这是谁”“这是什么梗”“这图出自哪里”。"
        "该工具会自动读取当前消息图片或当前用户最近发送的图片，进行视觉分析；"
        "如果未找到图片，则自动降级为普通联网搜索。"
    )
    parameters = [
        ("question", ToolParamType.STRING, "用户提出的问题", True, None),
    ]
    available_for_llm = True

    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, str]:
        question = str((function_args or {}).get("question", "")).strip()
        if not question:
            return {
                "name": self.name,
                "content": "搜索失败：缺少必要参数 question。"
            }

        try:
            resolver = ImageResolverService(self)
            image_base64 = await resolver.resolve_image_for_query()

            search = SearchService(self)

            # 没找到图：自动降级到普通搜索
            if not image_base64:
                logger.info("未找到可用图片，自动降级到普通搜索")
                raw_result = await search.search(question=question)
                output_mode = self.get_config("search.output_mode", "brief")
                result = format_search_result(question, raw_result, output_mode)
                return {
                    "name": self.name,
                    "content": result
                }

            # 找到图：先视觉分析，再搜索
            vision = VisionService(self)
            image_context = await vision.analyze_image_base64(image_base64, question)

            raw_result = await search.search(
                question=question,
                image_context=image_context,
            )

            output_mode = self.get_config("search.output_mode", "brief")
            result = format_search_result(question, raw_result, output_mode)
            return {
                "name": self.name,
                "content": result
            }

        except Exception as e:
            logger.exception(f"RecentImageSearchTool 异常: {e}")
            return {
                "name": self.name,
                "content": f"搜索失败：{str(e)}"
            }
