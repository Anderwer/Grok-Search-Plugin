from typing import Optional, Tuple

from src.common.logger import get_logger
from src.plugin_system import BaseCommand

from ..services import SearchService
from ..services.image_resolver import ImageResolverService
from ..services.vision_service import VisionService
from ..utils import format_search_result

logger = get_logger("search_command")


class SearchCommand(BaseCommand):
    command_name = "grok_search"
    command_description = "手动触发联网搜索或图片相关搜索"
    command_pattern = r"^(?:@\S+\s+)?/search\s+(?P<question>.+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        question = (self.matched_groups or {}).get("question", "")
        question = str(question).strip()

        if not question:
            await self.send_text("请输入要搜索的内容，例如：/search 今日新闻")
            return True, None, True

        try:
            image_context = ""

            if self.get_config("vision.enabled", True):
                resolver = ImageResolverService(self)
                visual = await resolver.resolve_visual_context_for_query()

                if visual.source_type == "none":
                    logger.info("未找到可用视觉资源，命令模式自动降级到普通搜索")
                else:
                    logger.info(
                        f"命令模式命中视觉资源 source_type={visual.source_type}, "
                        f"file_path={visual.file_path}"
                    )

                    # 优先使用原图走视觉分析
                    if visual.image_base64:
                        vision = VisionService(self)
                        image_context = await vision.analyze_image_base64(
                            visual.image_base64,
                            question,
                        )

                    # 如果没分析出内容，退回 text_hint
                    if not image_context and visual.text_hint:
                        image_context = visual.text_hint

            search_service = SearchService(self)
            raw_result = await search_service.search(
                question=question,
                image_context=image_context,
            )

            output_mode = self.get_config("search.output_mode", "brief")
            result = format_search_result(question, raw_result, output_mode)

            max_output_length = self.get_config("search.max_output_length", 1200)
            if len(result) > max_output_length:
                result = result[:max_output_length] + "\n\n（内容过长，已截断）"

            await self.send_text(result)
            return True, None, True

        except Exception as e:
            logger.exception(f"命令执行异常: {e}")
            await self.send_text(f"搜索失败：{str(e)}")
            return True, None, True
