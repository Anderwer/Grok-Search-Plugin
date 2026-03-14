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
        "该工具会自动读取当前消息图片、当前用户最近发送的图片或表情包，进行视觉分析；"
        "如果未找到可用视觉资源，则自动降级为普通联网搜索。"
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
            visual = await resolver.resolve_visual_context_for_query()

            search = SearchService(self)

            # 没找到视觉资源：自动降级到普通搜索
            if visual.source_type == "none":
                logger.info("未找到可用视觉资源，自动降级到普通搜索")
                raw_result = await search.search(question=question)
                output_mode = self.get_config("search.output_mode", "brief")
                result = format_search_result(question, raw_result, output_mode)
                return {
                    "name": self.name,
                    "content": result
                }

            logger.info(
                f"命中视觉资源 source_type={visual.source_type}, "
                f"file_path={visual.file_path}, source_id={visual.source_id}"
            )

            image_context = ""

            # 优先使用原图走视觉分析
            if visual.image_base64:
                vision = VisionService(self)
                image_context = await vision.analyze_image_base64(
                    visual.image_base64,
                    user_question=question,
                    source_type=visual.source_type,
                    source_id=visual.source_id,
                    file_path=visual.file_path,
                )

            # 如果没有原图分析结果，但有文本提示，就退回文本提示
            if not image_context and visual.text_hint:
                image_context = visual.text_hint

            # 仅由 direct_answer_mode 决定是否直接返回视觉结果
            direct_answer_mode = self.get_config("vision.direct_answer_mode", False)
            if direct_answer_mode and image_context:
                logger.info("direct_answer_mode 已开启，图片工具直接返回视觉模型结果")
                return {
                    "name": self.name,
                    "content": image_context.strip()
                }

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
