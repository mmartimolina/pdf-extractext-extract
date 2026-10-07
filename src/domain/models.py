from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedText:
    text: str
    page_count: int
