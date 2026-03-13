def format_search_result(question: str, result: str, output_mode: str = "brief") -> str:
    if not result or not result.strip():
        return f"未找到关于“{question}”的可靠信息。"

    result = result.strip()

    if output_mode == "raw":
        return result

    if output_mode == "structured":
        return f"📚 搜索主题：{question}\n\n{result}"

    return f"关于“{question}”的搜索结果：\n{result}"
