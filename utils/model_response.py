from typing import Any


def extract_completion_content(completion: Any) -> str:
    """
    统一提取模型返回内容，兼容：
    1. OpenAI SDK 对象
    2. dict 响应
    3. 直接字符串
    4. 其他可转字符串对象
    """

    # 1. OpenAI SDK / 类似对象
    if hasattr(completion, "choices"):
        try:
            content = completion.choices[0].message.content
            if content is None:
                return ""
            return str(content).strip()
        except Exception:
            pass

    # 2. dict 格式
    if isinstance(completion, dict):
        try:
            choices = completion.get("choices")
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message", {})
                content = msg.get("content", "")
                if content is not None:
                    return str(content).strip()
        except Exception:
            pass

        # 一些兼容接口直接返回 {"content": "..."}
        content = completion.get("content")
        if content is not None:
            return str(content).strip()

        # 一些接口可能返回 {"text": "..."}
        text = completion.get("text")
        if text is not None:
            return str(text).strip()

    # 3. 直接就是字符串
    if isinstance(completion, str):
        return completion.strip()

    # 4. 兜底
    if completion is None:
        return ""

    return str(completion).strip()
