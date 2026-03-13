from typing import Any, Dict

from src.common.logger import get_logger
from src.plugin_system import BaseTool, ToolParamType

from ..services import SearchService
from ..utils import format_search_result

logger = get_logger("search_tool")


class GroundedSearchTool(BaseTool):
    """给 LLM 自动调用的联网搜索工具"""

    name = "grounded_search"
    description = (
        "当问题具有时效性、事实性、争议性，或需要依赖外部资料确认时，"
        "使用该工具进行联网检索和可靠总结。适合热点、新闻、梗、近期事件、版本更新等问题。"
    )
    parameters = [
    ("question", ToolParamType.STRING, "要搜索的问题、关键词或主题", True, None),
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
            service = SearchService(self)
            raw_result = await service.search(question)
            output_mode = self.get_config("search.output_mode", "brief")
            result = format_search_result(question, raw_result, output_mode)
            return {
                "name": self.name,
                "content": result,
            }
        except Exception as e:
            logger.exception(f"[grok_search_plugin] Tool execute 异常: {e}")
            return {
                "name": self.name,
                "content": f"搜索失败：{str(e)}"
            }

    async def direct_execute(self, **function_args) -> str:
        question = str(function_args.get("question", "")).strip()
        if not question:
            raise ValueError("缺少必要参数: question")

        service = SearchService(self)
        raw_result = await service.search(question)
        output_mode = self.get_config("search.output_mode", "brief")
        return format_search_result(question, raw_result, output_mode)
