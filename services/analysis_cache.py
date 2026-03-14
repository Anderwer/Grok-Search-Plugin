import base64
import hashlib
import time
from typing import Optional

from src.common.logger import get_logger

from .plugin_cache_db import PluginCacheDB

logger = get_logger("analysis_cache")


class AnalysisCacheService:
    def __init__(self, ctx):
        self.ctx = ctx
        db_path = self.ctx.get_config(
            "vision.cache_db_path",
            "data/plugins/grok_search_plugin/cache.db"
        )
        self.db = PluginCacheDB(db_path=db_path)

    @staticmethod
    def calc_hash_from_base64(image_base64: str) -> str:
        image_bytes = base64.b64decode(image_base64)
        return hashlib.sha256(image_bytes).hexdigest()

    def get_cached_analysis(self, image_hash: str) -> Optional[str]:
        ttl = self.ctx.get_config("vision.cache_ttl_seconds", 86400 * 30)

        try:
            with self.db.get_conn() as conn:
                row = conn.execute("""
                    SELECT vision_result, updated_at, hit_count
                    FROM image_analysis_cache
                    WHERE image_hash = ?
                """, (image_hash,)).fetchone()

                if not row:
                    return None

                vision_result, updated_at, hit_count = row

                if ttl > 0 and (time.time() - updated_at) > ttl:
                    return None

                conn.execute("""
                    UPDATE image_analysis_cache
                    SET hit_count = ?, updated_at = updated_at
                    WHERE image_hash = ?
                """, (int(hit_count or 0) + 1, image_hash))

                logger.info(f"命中图片分析缓存 hash={image_hash[:12]}")
                return vision_result

        except Exception as e:
            logger.warning(f"读取图片分析缓存失败: {e}")
            return None

    def set_cached_analysis(
        self,
        image_hash: str,
        vision_result: str,
        source_type: str = "",
        source_id: str = "",
        file_path: str = "",
    ) -> None:
        if not vision_result:
            return

        now = time.time()

        try:
            with self.db.get_conn() as conn:
                row = conn.execute("""
                    SELECT id
                    FROM image_analysis_cache
                    WHERE image_hash = ?
                """, (image_hash,)).fetchone()

                if row:
                    conn.execute("""
                        UPDATE image_analysis_cache
                        SET vision_result = ?,
                            source_type = ?,
                            source_id = ?,
                            file_path = ?,
                            updated_at = ?
                        WHERE image_hash = ?
                    """, (
                        vision_result,
                        source_type,
                        source_id,
                        file_path,
                        now,
                        image_hash,
                    ))
                else:
                    conn.execute("""
                        INSERT INTO image_analysis_cache (
                            image_hash,
                            vision_result,
                            source_type,
                            source_id,
                            file_path,
                            created_at,
                            updated_at,
                            hit_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        image_hash,
                        vision_result,
                        source_type,
                        source_id,
                        file_path,
                        now,
                        now,
                    ))

            logger.info(f"写入图片分析缓存 hash={image_hash[:12]}")
        except Exception as e:
            logger.warning(f"写入图片分析缓存失败: {e}")
