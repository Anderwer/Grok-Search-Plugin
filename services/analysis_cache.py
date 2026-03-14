import json
import os
import time
import hashlib
import base64
from typing import Optional, Dict, Any

from src.common.logger import get_logger

logger = get_logger("analysis_cache")


class AnalysisCacheService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cache_file = self.get_cache_file()

    def get_cache_file(self) -> str:
        configured = self.ctx.get_config(
            "vision.cache_file",
            "data/plugins/grok_search_plugin/image_analysis_cache.json"
        )
        os.makedirs(os.path.dirname(configured), exist_ok=True)
        return configured

    def _load_cache(self) -> Dict[str, Any]:
        if not os.path.exists(self.cache_file):
            return {}
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return {}

    def _save_cache(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")

    @staticmethod
    def calc_hash_from_base64(image_base64: str) -> str:
        image_bytes = base64.b64decode(image_base64)
        return hashlib.sha256(image_bytes).hexdigest()

    def get_cached_analysis(self, image_hash: str) -> Optional[str]:
        cache = self._load_cache()
        item = cache.get(image_hash)
        if not item:
            return None

        ttl = self.ctx.get_config("vision.cache_ttl_seconds", 86400 * 30)
        updated_at = item.get("updated_at", 0)
        if ttl > 0 and (time.time() - updated_at) > ttl:
            return None

        return item.get("vision_result")

    def set_cached_analysis(self, image_hash: str, vision_result: str) -> None:
        cache = self._load_cache()
        cache[image_hash] = {
            "vision_result": vision_result,
            "updated_at": time.time(),
        }
        self._save_cache(cache)
