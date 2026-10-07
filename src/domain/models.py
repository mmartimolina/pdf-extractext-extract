from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedText:
    content: str
    page_count: int
