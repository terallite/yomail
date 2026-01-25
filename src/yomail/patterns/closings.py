"""Japanese email closing pattern detection.

Patterns match against neologdn-normalized text.
"""

import re

# Sentence-ending punctuation (formal and informal)
# Includes: period (。.), exclamation (!！), tilde (〜~)
_PUNCT = r"[。.!！〜~]"

# Closing patterns - common Japanese email closing formulas
_CLOSING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Most common business closings
    re.compile(rf"^.*よろしくお願い(いた|致)します{_PUNCT}?$"),
    re.compile(rf"^.*よろしくお願い申し上げます{_PUNCT}?$"),
    re.compile(rf"^.*よろしくお願いします{_PUNCT}?$"),
    # 以上 (that's all) followed by any polite request
    re.compile(r"^以上[、,､].*(お願い|ください|下さい).*$"),
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
    re.compile(rf"^敬具{_PUNCT}?$"),
    re.compile(rf"^草々{_PUNCT}?$"),
    re.compile(rf"^敬白{_PUNCT}?$"),
    re.compile(rf"^謹白{_PUNCT}?$"),
    re.compile(rf"^早々{_PUNCT}?$"),
    # 以上 (that's all) - often ends body
    re.compile(rf"^以上です{_PUNCT}?$"),
    re.compile(rf"^以上となります{_PUNCT}?$"),
    re.compile(rf"^以上{_PUNCT}?$"),
    # Waiting for reply
    re.compile(r"^.*ご返信.*お待ち.*$"),
    re.compile(r"^.*お返事.*お待ち.*$"),
    # Thanks in advance
    re.compile(rf"^.*ありがとうございます{_PUNCT}?$"),
    re.compile(rf"^.*ありがとうございました{_PUNCT}?$"),
    # Take care
    re.compile(rf"^.*失礼いたします{_PUNCT}?$"),
    re.compile(rf"^.*失礼します{_PUNCT}?$"),
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
