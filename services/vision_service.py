from openai import AsyncOpenAI
from src.common.logger import get_logger

from .analysis_cache import AnalysisCacheService
from ..utils.model_response import extract_completion_content

logger = get_logger("vision_service")


class VisionService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cache = AnalysisCacheService(ctx)

    async def analyze_image_base64(
        self,
        image_base64: str,
        user_question: str = "",
        source_type: str = "",
        source_id: str = "",
        file_path: str = "",
    ) -> str:
        if not image_base64:
            return ""

        image_hash = self.cache.calc_hash_from_base64(image_base64)
        cached = self.cache.get_cached_analysis(image_hash)
        if cached:
            return cached

        logger.info(f"开始视觉分析 hash={image_hash[:12]}")

        client = AsyncOpenAI(
            base_url=self.ctx.get_config("vision.base_url"),
            api_key=self.ctx.get_config("vision.api_key"),
        )

        prompt = self.ctx.get_config(
            "vision.prompt",
            "请准确识别图片中的人物、角色、作品线索、文字信息和可能的梗来源，不要编造。"
        )
        if user_question:
            prompt += f"\n\n用户当前问题：{user_question}"

        try:
            completion = await client.chat.completions.create(
                model=self.ctx.get_config("vision.model"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                temperature=self.ctx.get_config("vision.temperature", 0.1),
                timeout=self.ctx.get_config("vision.timeout", 20.0),
            )

            content = extract_completion_content(completion).strip()

            if content:
                self.cache.set_cached_analysis(
                    image_hash=image_hash,
                    vision_result=content,
                    source_type=source_type,
                    source_id=source_id,
                    file_path=file_path,
                )

            return content

        except Exception as e:
            logger.exception(f"视觉分析失败: {e}")
            return ""
