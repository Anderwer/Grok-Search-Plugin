from dataclasses import dataclass


@dataclass
class SearchRequest:
    question: str
    context_text: str
    current_time_text: str
    image_context: str = ""