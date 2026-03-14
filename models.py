from dataclasses import dataclass


@dataclass
class SearchRequest:
    question: str
    context_text: str
    current_time_text: str
    image_context: str = ""


@dataclass
class VisualContext:
    source_type: str = "none"
    image_base64: str = ""
    image_hash: str = ""
    text_hint: str = ""
    file_path: str = ""
    source_id: str = ""
