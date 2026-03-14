import os
import sqlite3
from contextlib import contextmanager

from src.common.logger import get_logger

logger = get_logger("plugin_cache_db")


class PluginCacheDB:
    def __init__(self, db_path: str = "data/plugins/grok_search_plugin/cache.db"):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS image_analysis_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_hash TEXT NOT NULL UNIQUE,
                    vision_result TEXT NOT NULL,
                    source_type TEXT,
                    source_id TEXT,
                    file_path TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                )
            """)
        logger.info(f"插件缓存数据库初始化完成: {self.db_path}")
