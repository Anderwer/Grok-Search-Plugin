from typing import List, Tuple, Type

from src.plugin_system import (
    BasePlugin,
    ComponentInfo,
    ConfigField,
    register_plugin,
)

from .components import GroundedSearchTool, SearchCommand, RecentImageSearchTool

@register_plugin
class GrokSearchPlugin(BasePlugin):
    """Grok 搜索插件"""

    plugin_name = "grok_search_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = ["openai"]
    config_file_name = "config.toml"

    config_section_descriptions = {
        "plugin": "插件基础信息",
        "model": "搜索模型配置(推荐使用Grok模型)",
        "search": "搜索行为配置",
        "prompt": "提示词配置",
        "vision": "图片识别与缓存配置",
    }

    config_schema = {
        "plugin": {
            "name": ConfigField(
                type=str,
                default="grok_search_plugin",
                description="插件名称"
            ),
            "version": ConfigField(
                type=str,
                default="1.0.0",
                description="插件版本"
            ),
            "config_version": ConfigField(
                type=str,
                default="1.0.0",
                description="配置文件版本"
            ),
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用插件"
            ),
        },
        "model": {
            "base_url": ConfigField(
                type=str,
                default="https://api.openai.com/v1",
                description="兼容 OpenAI Chat Completions 的接口地址"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="模型 API 密钥"
            ),
            "model": ConfigField(
                type=str,
                default="grok-4",
                description="使用的模型名称"
            ),
            "temperature": ConfigField(
                type=float,
                default=0.2,
                description="生成温度，建议较低以减少发散"
            ),
        },
        "search": {
            "direction": ConfigField(
                type=str,
                default="请优先关注热点事件、事实准确性、发布时间、版本变更和外部资料的可靠性。",
                description="搜索归纳方向"
            ),
            "enable_context": ConfigField(
                type=bool,
                default=True,
                description="是否附带最近聊天上下文帮助理解问题"
            ),
            "time_gap": ConfigField(
                type=int,
                default=270,
                description="读取最近多少秒内的聊天记录"
            ),
            "max_limit": ConfigField(
                type=int,
                default=10,
                description="最多读取多少条聊天记录"
            ),
            "timeout": ConfigField(
                type=float,
                default=20.0,
                description="单次请求超时时间（秒）"
            ),
            "max_concurrency": ConfigField(
                type=int,
                default=3,
                description="最大并发搜索请求数"
            ),
            "retry_attempts": ConfigField(
                type=int,
                default=3,
                description="失败重试次数"
            ),
            "retry_wait_min": ConfigField(
                type=float,
                default=1.5,
                description="最小重试等待时间（秒）"
            ),
            "retry_wait_max": ConfigField(
                type=float,
                default=8.0,
                description="最大重试等待时间（秒）"
            ),
            "output_mode": ConfigField(
                type=str,
                default="brief",
                description="输出模式：brief / structured / raw"
            ),
        },
        "prompt": {
            "system_prompt": ConfigField(
                type=str,
                default="你是专业的联网检索助手，擅长根据外部信息生成可靠、简洁、及时的总结。",
                description="系统提示词"
            ),
        },
        "vision": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用图片视觉分析"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.openai.com/v1",
                description="视觉模型接口地址"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="视觉模型 API 密钥"
            ),
            "model": ConfigField(
                type=str,
                default="grok-4",
                description="视觉模型名称"
            ),
            "direct_answer_mode": ConfigField(
                type=bool,
                default=True,
                description="图片识别类问题是否只使用视觉模型直接回答，如果关闭会在视觉分析后继续交给搜索模型"
            ),
            "temperature": ConfigField(
                type=float,
                default=0.1,
                description="视觉分析温度"
            ),
            "timeout": ConfigField(
                type=float,
                default=20.0,
                description="视觉分析超时时间（秒）"
            ),
            "prompt": ConfigField(
                type=str,
                default="请准确识别图片中的人物、角色、作品线索、文字信息和可能的梗来源，不要编造。",
                description="视觉分析提示词"
            ),
            "fallback_to_recent_image": ConfigField(
                type=bool,
                default=True,
                description="当前消息无图时，是否回退查找最近图片"
            ),
            "prefer_same_user_recent_image": ConfigField(
                type=bool,
                default=True,
                description="是否优先查找当前用户最近发送的图片"
            ),
            "recent_image_time_gap": ConfigField(
                type=int,
                default=120,
                description="回溯最近图片的时间范围（秒）"
            ),
            "recent_image_scan_limit": ConfigField(
                type=int,
                default=15,
                description="最多检查最近多少条消息"
            ),
            "cache_db_path": ConfigField(
                type=str,
                default="data/plugins/grok_search_plugin/cache.db",
                description="图片分析缓存数据库路径"
            ),
            "cache_ttl_seconds": ConfigField(
                type=int,
                default=2592000,
                description="图片分析缓存有效期（秒），30天"
            ),
},
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (GroundedSearchTool.get_tool_info(), GroundedSearchTool),
            (RecentImageSearchTool.get_tool_info(), RecentImageSearchTool),
            (SearchCommand.get_command_info(), SearchCommand),
        ]
