"""Japanese email closing pattern detection.

Patterns match against neologdn-normalized text.
"""

import re

# Closing patterns - common Japanese email closing formulas
_CLOSING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Most common business closings
    re.compile(r"^.*よろしくお願い(いた|致)します[。.]?$"),
    re.compile(r"^.*よろしくお願い申し上げます[。.]?$"),
    re.compile(r"^.*よろしくお願いします[。.]?$"),
    re.compile(r"^以上[、,]?.*よろしくお願い.*$"),
    re.compile(r"^.*何卒よろしくお願い.*$"),
    re.compile(r"^.*どうぞよろしくお願い.*$"),
    re.compile(r"^.*引き続きよろしくお願い.*$"),
    re.compile(r"^.*今後(とも)?よろしくお願い.*$"),
    # Request for confirmation/review
    re.compile(r"^.*ご確認.*よろしくお願い.*$"),
    re.compile(r"^.*ご検討.*よろしくお願い.*$"),
    re.compile(r"^.*ご対応.*よろしくお願い.*$"),
    # Apology for trouble
    re.compile(r"^.*お手数をおかけしますが.*$"),
    re.compile(r"^.*お手数ですが.*$"),
    re.compile(r"^.*ご面倒をおかけしますが.*$"),
    # Formal letter closings
    re.compile(r"^敬具[。.]?$"),
    re.compile(r"^草々[。.]?$"),
    re.compile(r"^敬白[。.]?$"),
    re.compile(r"^謹白[。.]?$"),
    re.compile(r"^早々[。.]?$"),
    # 以上 (that's all) - often ends body
    re.compile(r"^以上です[。.]?$"),
    re.compile(r"^以上となります[。.]?$"),
    re.compile(r"^以上[。.]?$"),
    # Waiting for reply
    re.compile(r"^.*ご返信.*お待ち.*$"),
    re.compile(r"^.*お返事.*お待ち.*$"),
    # Thanks in advance
    re.compile(r"^.*ありがとうございます[。.]?$"),
    re.compile(r"^.*ありがとうございました[。.]?$"),
    # Take care
    re.compile(r"^.*失礼いたします[。.]?$"),
    re.compile(r"^.*失礼します[。.]?$"),
)


def is_closing_line(line: str) -> bool:
    """Check if a line matches a closing pattern.

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line matches a closing pattern.
    """
    stripped = line.strip()
    if not stripped:
        return False

    return any(pattern.match(stripped) for pattern in _CLOSING_PATTERNS)
