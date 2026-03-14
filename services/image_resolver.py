import base64
import os
import re
import time
from typing import Any, Dict, List, Optional

from maim_message import Seg
from src.common.database.database_model import Images
from src.common.logger import get_logger

logger = get_logger("image_resolver")


class ImageResolverService:
    def __init__(self, ctx):
        self.ctx = ctx

    async def resolve_image_for_query(self) -> Optional[str]:
        """
        返回本次查询应使用的图片 base64
        优先级：
        1. 当前消息中的图
        2. 当前用户最近的图
        3. 可选：当前会话最近图
        """
        current_message = self._get_current_message()
        candidates = self.extract_candidates_from_message(current_message)
        if candidates:
            logger.info("命中当前消息图片")
            return await self.resolve_candidate_to_base64(candidates[0])

        if self.ctx.get_config("vision.fallback_to_recent_image", True):
            recent = await self._find_recent_image_candidate(
                prefer_same_user=self.ctx.get_config(
                    "vision.prefer_same_user_recent_image", True
                )
            )
            if recent:
                logger.info("命中最近图片")
                return await self.resolve_candidate_to_base64(recent)

        return None

    def _get_current_message(self):
        for attr in ("message", "raw_message_obj", "maim_message", "event"):
            obj = getattr(self.ctx, attr, None)
            if obj is not None:
                return obj
        return None

    def extract_candidates_from_message(self, message: Any) -> List[str]:
        if message is None:
            return []

        items: List[str] = []

        self._collect_images_from_any(getattr(message, "message_segment", None), items)

        raw_message = getattr(message, "raw_message", None)
        if isinstance(raw_message, str):
            self._collect_images_from_any(raw_message, items)

        for attr in ("message", "segments", "data", "content"):
            self._collect_images_from_any(getattr(message, attr, None), items)

        return self._unique_candidates(items)

    def _collect_images_from_any(self, obj: Any, out: List[str]) -> None:
        if obj is None:
            return
        if isinstance(obj, Seg):
            self._handle_seg(obj, out)
            return
        if isinstance(obj, list):
            for item in obj:
                self._collect_images_from_any(item, out)
            return
        if isinstance(obj, dict):
            self._handle_dict(obj, out)
            return
        if isinstance(obj, str):
            self._handle_str(obj, out)

    def _handle_seg(self, seg: Seg, out: List[str]) -> None:
        seg_type = getattr(seg, "type", "")
        data = getattr(seg, "data", None)

        if seg_type in {"image", "emoji"}:
            self._append_candidate(data, out)
            return

        if seg_type == "seglist" and isinstance(data, list):
            for sub in data:
                self._collect_images_from_any(sub, out)
            return

        if isinstance(data, (list, dict, str)):
            self._collect_images_from_any(data, out)

    def _handle_dict(self, obj: Dict[str, Any], out: List[str]) -> None:
        if "type" in obj and "data" in obj:
            try:
                seg = Seg.from_dict(obj)
                self._collect_images_from_any(seg, out)
            except Exception:
                pass

        for key in ("base64", "url", "file"):
            self._append_candidate(obj.get(key), out)

        for key in ("message_segment", "message", "data", "content", "segments"):
            if key in obj:
                self._collect_images_from_any(obj[key], out)

    def _handle_str(self, s: str, out: List[str]) -> None:
        self._append_candidate(s, out)

    def _append_candidate(self, value: Any, out: List[str]) -> None:
        if not value:
            return

        if isinstance(value, dict):
            for k in ("base64", "url", "file"):
                v = value.get(k)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
            return

        if not isinstance(value, str):
            return

        value = value.strip()
        if not value:
            return

        if value.startswith("base64://") or value.startswith("data:image/"):
            out.append(value)

        if value.startswith("http://") or value.startswith("https://"):
            out.append(value)

        if value.startswith("[CQ:image"):
            out.append(value)

        picids = re.findall(r"\[picid:[^\]]+\]", value)
        out.extend(picids)

        urls = re.findall(r"(https?://\S+)", value)
        out.extend(urls)

    def _unique_candidates(self, items: List[str]) -> List[str]:
        seen = set()
        ordered = []
        for item in items:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    async def resolve_candidate_to_base64(self, candidate: str) -> Optional[str]:
        source = candidate.strip()
        if not source:
            return None

        direct = await self._resolve_url_or_base64(source)
        if direct is not None:
            return direct

        if source.startswith("[CQ:image"):
            cq_resolved = await self._resolve_cq_image(source)
            if cq_resolved is not None:
                return cq_resolved

        m = re.search(r"\[picid:([^\]]+)\]", source)
        if m:
            return await self._picid_to_base64(m.group(1))

        if source.startswith("http://") or source.startswith("https://"):
            return await self._url_to_base64(source)

        if self._looks_like_base64(source):
            return self._normalize_base64(source)

        return None

    async def _resolve_url_or_base64(self, source: str) -> Optional[str]:
        if source.startswith("base64://"):
            return self._normalize_base64(source[len("base64://"):])

        if source.startswith("data:"):
            return self._normalize_base64(source.split(",", 1)[-1])

        return None

    async def _resolve_cq_image(self, source: str) -> Optional[str]:
        base64_match = re.search(r"base64=([^,\]]+)", source)
        if base64_match:
            return self._normalize_base64(base64_match.group(1))

        url_match = re.search(r"url=([^,\]]+)", source)
        if url_match:
            return await self._url_to_base64(url_match.group(1))

        file_match = re.search(r"file=([^,\]]+)", source)
        if file_match:
            file_value = file_match.group(1)
            if file_value.startswith("base64://"):
                return self._normalize_base64(file_value[len("base64://"):])
            if file_value.startswith("http://") or file_value.startswith("https://"):
                return await self._url_to_base64(file_value)
            if os.path.exists(file_value):
                return self._file_to_base64(file_value)

        return None

    async def _picid_to_base64(self, image_id: str) -> Optional[str]:
        try:
            image = Images.get_or_none(Images.image_id == image_id)
            if not image:
                return None
            path = getattr(image, "path", "") or ""
            if not path or not os.path.exists(path):
                return None
            return self._file_to_base64(path)
        except Exception as e:
            logger.warning(f"picid 转 base64 失败: {e}")
            return None

    async def _url_to_base64(self, url: str) -> Optional[str]:
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=20) as resp:
                    data = await resp.read()
            return base64.b64encode(data).decode("utf-8")
        except Exception as e:
            logger.warning(f"url 转 base64 失败: {e}")
            return None

    def _file_to_base64(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _normalize_base64(self, b64: str) -> str:
        return b64.strip()

    def _looks_like_base64(self, value: str) -> bool:
        if len(value) < 80:
            return False
        try:
            base64.b64decode(value, validate=True)
            return True
        except Exception:
            return False

    async def _find_recent_image_candidate(self, prefer_same_user: bool = True) -> Optional[str]:
        try:
            from src.plugin_system.apis import message_api
        except Exception:
            return None

        chat_stream = getattr(self.ctx, "chat_stream", None)
        if not chat_stream:
            return None

        stream_id = getattr(chat_stream, "stream_id", None)
        if not stream_id:
            return None

        lookup_seconds = float(
            self.ctx.get_config("vision.recent_image_time_gap", 120) or 120
        )
        history_limit = int(
            self.ctx.get_config("vision.recent_image_scan_limit", 15) or 15
        )
        now = time.time()

        try:
            history = message_api.get_messages_by_time_in_chat_inclusive(
                stream_id,
                max(0.0, now - lookup_seconds),
                now,
                limit=history_limit,
                limit_mode="latest",
                filter_mai=False,
                filter_command=False,
            )
        except Exception as e:
            logger.warning(f"读取最近消息失败: {e}")
            return None

        current_user_id = getattr(self.ctx, "user_id", None)

        if prefer_same_user:
            for msg in reversed(history):
                msg_user_id = self._get_db_message_user_id(msg)
                if current_user_id and msg_user_id != current_user_id:
                    continue
                candidates = self._extract_images_from_db_message(msg)
                if candidates:
                    return candidates[0]

        for msg in reversed(history):
            candidates = self._extract_images_from_db_message(msg)
            if candidates:
                return candidates[0]

        return None

    def _get_db_message_user_id(self, db_msg) -> Optional[str]:
        try:
            return db_msg.user_info.user_id
        except Exception:
            return None

    def _extract_images_from_db_message(self, db_msg) -> List[str]:
        images: List[str] = []

        config_str = getattr(db_msg, "additional_config", None)
        if config_str:
            try:
                import json
                payload = json.loads(config_str)
                if isinstance(payload, dict):
                    seg_dict = payload.get("message_segment")
                    if isinstance(seg_dict, dict):
                        seg = Seg.from_dict(seg_dict)
                        self._collect_images_from_any(seg, images)
            except Exception:
                pass

        for field in ("display_message", "processed_plain_text"):
            text = getattr(db_msg, field, None)
            if not text:
                continue
            images.extend(re.findall(r"\[CQ:image[^\]]+\]", text))
            images.extend(re.findall(r"(https?://\S+)", text))
            images.extend(re.findall(r"\[picid:[^\]]+\]", text))

        return self._unique_candidates(images)
