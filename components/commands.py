from typing import Optional, Tuple

from src.common.logger import get_logger
from src.plugin_system import BaseCommand

from ..services import SearchService
from ..utils import format_search_result

logger = get_logger("grok_search_plugin")


class SearchCommand(BaseCommand):
    """手动联网搜索命令"""

    command_name = "internet_search"
    command_description = "手动触发联网搜索"
    command_pattern = r"^/search\s+(?P<question>.+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        question = (self.matched_groups or {}).get("question", "")
        question = str(question).strip()

        if not question:
            return True, "请输入要搜索的内容，例如：/search 今天有什么新的新闻", True

        try:
            service = SearchService(self)
            raw_result = await service.search(question)
            output_mode = self.get_config("search.output_mode", "brief")
            result = format_search_result(question, raw_result, output_mode)
            return True, result, True
        except Exception as e:
            logger.exception(f"[grok_search_plugin] Command execute 异常: {e}")
            return True, f"搜索失败：{str(e)}", True
