import base64
import hashlib
import json
import os
import re
import time
from typing import Any, List, Optional

from maim_message import Seg
from src.common.database.database_model import Images
from src.common.logger import get_logger

from ..models import VisualContext

logger = get_logger("image_resolver")


class ImageResolverService:
    """
    统一视觉资源解析器：
    1. 普通图片：优先从 picid -> data/images/<picid>.png 或 Images 表中取原图
    2. 表情包：从 [表情包：xxx] 提取标签，去 emoji 表中模糊匹配 full_path
    3. 回溯最近消息时优先当前用户
    """

    def __init__(self, ctx):
        self.ctx = ctx

    async def resolve_visual_context_for_query(self) -> VisualContext:
        """
        返回本次查询应使用的视觉上下文：
        - source_type=image: 有原图，可走视觉模型
        - source_type=emoji: 有表情包原图，可走视觉模型
        - source_type=none: 没找到
        """
        # 1. 当前消息优先
        current_message = self._get_current_message()
        current_ctx = await self._resolve_from_message_object(current_message)
        if current_ctx.source_type != "none":
            logger.info(f"命中当前消息视觉资源 source_type={current_ctx.source_type}")
            return current_ctx

        # 2. 回溯最近消息
        if self.ctx.get_config("vision.fallback_to_recent_image", True):
            recent_ctx = await self._find_recent_visual_context(
                prefer_same_user=self.ctx.get_config(
                    "vision.prefer_same_user_recent_image", True
                )
            )
            if recent_ctx.source_type != "none":
                logger.info(f"命中最近视觉资源 source_type={recent_ctx.source_type}")
                return recent_ctx

        logger.info("未找到可用视觉资源")
        return VisualContext()

    def _get_current_message(self):
        for attr in ("message", "raw_message_obj", "maim_message", "event"):
            obj = getattr(self.ctx, attr, None)
            if obj is not None:
                return obj
        return None

    async def _resolve_from_message_object(self, message: Any) -> VisualContext:
        if message is None:
            return VisualContext()

        text_pool = self._extract_texts_from_message(message)

        # 1. 优先按 picid 取普通图片
        picids = self._extract_picids_from_texts(text_pool)
        for picid in picids:
            ctx = self._build_visual_context_from_picid(picid)
            if ctx.source_type != "none":
                return ctx

        # 2. 再尝试直接从消息对象中找 image/emoji 段里的 file/url/base64
        direct_ctx = await self._resolve_direct_binary_from_message(message)
        if direct_ctx.source_type != "none":
            return direct_ctx

        # 3. 最后处理 [表情包：xxx]
        emoji_labels = self._extract_emoji_labels_from_texts(text_pool)
        if emoji_labels:
            ctx = self._build_visual_context_from_emoji_labels(emoji_labels)
            if ctx.source_type != "none":
                return ctx

        return VisualContext()

    def _extract_texts_from_message(self, message: Any) -> List[str]:
        texts: List[str] = []

        for attr in ("raw_message", "processed_plain_text", "display_message"):
            val = getattr(message, attr, None)
            if isinstance(val, str) and val.strip():
                texts.append(val)

        for attr in ("message_segment", "message", "segments", "data", "content"):
            self._collect_texts_from_any(getattr(message, attr, None), texts)

        return self._unique_list(texts)

    def _collect_texts_from_any(self, obj: Any, out: List[str]) -> None:
        if obj is None:
            return

        if isinstance(obj, str):
            if obj.strip():
                out.append(obj)
            return

        if isinstance(obj, Seg):
            seg_type = getattr(obj, "type", "")
            data = getattr(obj, "data", None)

            if isinstance(data, str) and data.strip():
                out.append(data)

            if isinstance(data, dict):
                for v in data.values():
                    self._collect_texts_from_any(v, out)

            if isinstance(data, list):
                for item in data:
                    self._collect_texts_from_any(item, out)

            # 某些文本段本身可能在 Seg 里
            if seg_type == "text":
                try:
                    txt = str(data)
                    if txt.strip():
                        out.append(txt)
                except Exception:
                    pass
            return

        if isinstance(obj, dict):
            for v in obj.values():
                self._collect_texts_from_any(v, out)
            return

        if isinstance(obj, list):
            for item in obj:
                self._collect_texts_from_any(item, out)

    def _extract_picids_from_texts(self, texts: List[str]) -> List[str]:
        picids: List[str] = []
        for text in texts:
            picids.extend(re.findall(r"\[picid:([^\]]+)\]", text))
        return self._unique_list(picids)

    def _extract_emoji_labels_from_texts(self, texts: List[str]) -> List[str]:
        labels: List[str] = []
        for text in texts:
            matches = re.findall(r"\[表情包：([^\]]+)\]", text)
            for raw in matches:
                parts = [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]
                labels.extend(parts)
        return self._unique_list(labels)

    async def _resolve_direct_binary_from_message(self, message: Any) -> VisualContext:
        """
        兼容直接从消息段中拿 file/url/base64 的情况。
        """
        candidates = []
        for attr in ("message_segment", "message", "segments", "data", "content"):
            self._collect_binary_candidates(getattr(message, attr, None), candidates)

        for item in self._unique_list(candidates):
            ctx = await self._candidate_to_visual_context(item)
            if ctx.source_type != "none":
                return ctx

        return VisualContext()

    def _collect_binary_candidates(self, obj: Any, out: List[str]) -> None:
        if obj is None:
            return

        if isinstance(obj, Seg):
            seg_type = getattr(obj, "type", "")
            data = getattr(obj, "data", None)

            if seg_type in {"image", "emoji", "sticker"}:
                self._append_binary_candidate(data, out)

            if isinstance(data, dict):
                for v in data.values():
                    self._collect_binary_candidates(v, out)
            elif isinstance(data, list):
                for item in data:
                    self._collect_binary_candidates(item, out)
            return

        if isinstance(obj, dict):
            # 支持 {"type": "...", "data": {...}}
            if "type" in obj and "data" in obj:
                try:
                    seg = Seg.from_dict(obj)
                    self._collect_binary_candidates(seg, out)
                except Exception:
                    pass

            for key in ("file", "url", "base64"):
                val = obj.get(key)
                if isinstance(val, str) and val.strip():
                    out.append(val.strip())

            for v in obj.values():
                self._collect_binary_candidates(v, out)
            return

        if isinstance(obj, list):
            for item in obj:
                self._collect_binary_candidates(item, out)

    def _append_binary_candidate(self, data: Any, out: List[str]) -> None:
        if not data:
            return

        if isinstance(data, dict):
            for key in ("file", "url", "base64"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    out.append(val.strip())
            return

        if isinstance(data, str) and data.strip():
            out.append(data.strip())

    async def _candidate_to_visual_context(self, candidate: str) -> VisualContext:
        source = candidate.strip()
        if not source:
            return VisualContext()

        # base64://...
        if source.startswith("base64://"):
            b64 = source[len("base64://"):].strip()
            return self._build_visual_context_from_base64(
                b64,
                source_type="image",
                source_id="base64_inline",
            )

        # data:image/...
        if source.startswith("data:image/"):
            b64 = source.split(",", 1)[-1].strip()
            return self._build_visual_context_from_base64(
                b64,
                source_type="image",
                source_id="data_uri",
            )

        # 本地文件
        if os.path.exists(source):
            return self._build_visual_context_from_file(
                source,
                source_type="image",
                source_id=source,
            )

        # url
        if source.startswith("http://") or source.startswith("https://"):
            b64 = await self._url_to_base64(source)
            if b64:
                return self._build_visual_context_from_base64(
                    b64,
                    source_type="image",
                    source_id=source,
                )

        return VisualContext()

    def _build_visual_context_from_picid(self, picid: str) -> VisualContext:
        # 1. 直接按 data/images/<picid>.png 尝试
        direct_path = os.path.join("data", "images", f"{picid}.png")
        if os.path.exists(direct_path):
            return self._build_visual_context_from_file(
                direct_path,
                source_type="image",
                source_id=picid,
            )

        # 2. 再查 Images 表
        try:
            image = Images.get_or_none(Images.image_id == picid)
            if image:
                path = getattr(image, "path", "") or ""
                if path and os.path.exists(path):
                    return self._build_visual_context_from_file(
                        path,
                        source_type="image",
                        source_id=picid,
                    )
        except Exception as e:
            logger.warning(f"通过 Images 表解析 picid 失败: {e}")

        return VisualContext()

    def _build_visual_context_from_emoji_labels(self, labels: List[str]) -> VisualContext:
        """
        从 emoji 表中根据标签模糊匹配 full_path。
        注意：下面的 Emoji 模型类名可能需要按你的项目真实名字改。
        """
        if not labels:
            return VisualContext()

        emoji_model = self._get_emoji_model()
        if emoji_model is None:
            logger.warning("未找到 emoji 数据模型，请检查 database_model 中的表模型类名")
            return VisualContext(text_hint="表情包标签：" + "、".join(labels))

        try:
            candidates = emoji_model.select().where(
                emoji_model.is_registered == 1,
                emoji_model.is_banned == 0,
            )
        except Exception as e:
            logger.warning(f"查询 emoji 表失败: {e}")
            return VisualContext(text_hint="表情包标签：" + "、".join(labels))

        best = None
        best_score = 0

        for item in candidates:
            haystack = f"{getattr(item, 'description', '')} {getattr(item, 'emotion', '')}"
            score = 0
            for label in labels:
                if label and label in haystack:
                    score += 1
            if score > best_score:
                best_score = score
                best = item

        if not best:
            logger.info(f"未在 emoji 表中找到匹配标签: {labels}")
            return VisualContext(text_hint="表情包标签：" + "、".join(labels))

        full_path = getattr(best, "full_path", "") or ""
        description = getattr(best, "description", "") or ""
        emotion = getattr(best, "emotion", "") or ""

        if full_path and os.path.exists(full_path):
            ctx = self._build_visual_context_from_file(
                full_path,
                source_type="emoji",
                source_id=str(getattr(best, "id", "")),
            )
            ctx.text_hint = description or emotion or ("表情包标签：" + "、".join(labels))
            return ctx

        # 即使没原图，也返回文本提示，后续可降级给搜索用
        return VisualContext(
            source_type="emoji",
            text_hint=description or emotion or ("表情包标签：" + "、".join(labels)),
            file_path=full_path,
            source_id=str(getattr(best, "id", "")),
        )

    async def _find_recent_visual_context(self, prefer_same_user: bool = True) -> VisualContext:
        try:
            from src.plugin_system.apis import message_api
        except Exception:
            return VisualContext()

        chat_stream = getattr(self.ctx, "chat_stream", None)
        if not chat_stream:
            return VisualContext()

        stream_id = getattr(chat_stream, "stream_id", None)
        if not stream_id:
            return VisualContext()

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
            return VisualContext()

        current_user_id = getattr(self.ctx, "user_id", None)

        # 1. 优先当前用户
        if prefer_same_user:
            for msg in reversed(history):
                msg_user_id = self._get_db_message_user_id(msg)
                if current_user_id and msg_user_id != current_user_id:
                    continue
                ctx = self._resolve_from_db_message(msg)
                if ctx.source_type != "none":
                    return ctx

        # 2. 再查全会话
        for msg in reversed(history):
            ctx = self._resolve_from_db_message(msg)
            if ctx.source_type != "none":
                return ctx

        return VisualContext()

    def _get_db_message_user_id(self, db_msg) -> Optional[str]:
        try:
            return db_msg.user_info.user_id
        except Exception:
            pass

        for attr in ("user_id", "chat_info_user_id"):
            val = getattr(db_msg, attr, None)
            if val:
                return str(val)
        return None

    def _resolve_from_db_message(self, db_msg) -> VisualContext:
        text_pool: List[str] = []

        for field in ("processed_plain_text", "display_message"):
            val = getattr(db_msg, field, None)
            if isinstance(val, str) and val.strip():
                text_pool.append(val)

        # additional_config 中可能带 message_segment
        config_str = getattr(db_msg, "additional_config", None)
        if config_str:
            try:
                payload = json.loads(config_str)
                if isinstance(payload, dict):
                    seg_dict = payload.get("message_segment")
                    if isinstance(seg_dict, dict):
                        seg = Seg.from_dict(seg_dict)
                        self._collect_texts_from_any(seg, text_pool)

                        direct_candidates = []
                        self._collect_binary_candidates(seg, direct_candidates)
                        for item in self._unique_list(direct_candidates):
                            if os.path.exists(item):
                                return self._build_visual_context_from_file(
                                    item,
                                    source_type="image",
                                    source_id=item,
                                )
            except Exception:
                pass

        # 1. 普通图片优先
        picids = self._extract_picids_from_texts(text_pool)
        for picid in picids:
            ctx = self._build_visual_context_from_picid(picid)
            if ctx.source_type != "none":
                return ctx

        # 2. 表情包：不要再依赖 is_emoji，直接根据文本特征判断
        labels = self._extract_emoji_labels_from_texts(text_pool)
        if labels:
            logger.info(f"检测到表情包标签 labels={labels}")
            ctx = self._build_visual_context_from_emoji_labels(labels)
            if ctx.source_type != "none" or ctx.text_hint:
                return ctx

        return VisualContext()

    def _build_visual_context_from_file(
        self,
        path: str,
        source_type: str,
        source_id: str = "",
    ) -> VisualContext:
        try:
            with open(path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("utf-8")
            image_hash = hashlib.sha256(data).hexdigest()
            return VisualContext(
                source_type=source_type,
                image_base64=b64,
                image_hash=image_hash,
                file_path=path,
                source_id=source_id,
            )
        except Exception as e:
            logger.warning(f"读取文件失败 path={path}, error={e}")
            return VisualContext()

    def _build_visual_context_from_base64(
        self,
        image_base64: str,
        source_type: str,
        source_id: str = "",
    ) -> VisualContext:
        try:
            data = base64.b64decode(image_base64)
            image_hash = hashlib.sha256(data).hexdigest()
            return VisualContext(
                source_type=source_type,
                image_base64=image_base64,
                image_hash=image_hash,
                source_id=source_id,
            )
        except Exception as e:
            logger.warning(f"base64 解析失败: {e}")
            return VisualContext()

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

    def _unique_list(self, items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _get_emoji_model(self):
        """
        这里尝试自动适配 emoji 表模型名。
        你如果知道真实类名，建议直接改成显式导入，最稳。
        """
        try:
            import src.common.database.database_model as dbm
        except Exception:
            return None

        for name in ("Emoji", "EmojiRegisted", "EmojiRegistered", "Emojis"):
            model = getattr(dbm, name, None)
            if model is not None:
                return model

        return None
