"""Visual separator line detection for Japanese email text.

Detects lines that serve as visual separators (---, ===, ■■■, etc.)
using Unicode character properties rather than hardcoded character lists.
"""

import unicodedata
from collections import Counter


def is_printable_char(char: str) -> bool:
    """Check if a character prints something visible.

    Excludes whitespace, control characters, and format characters
    (like zero-width space, soft hyphen, etc.).

    Args:
        char: A single character.

    Returns:
        True if the character is visible when printed.
    """
    if char.isspace():
        return False
    cat = unicodedata.category(char)
    # Cc=control, Cf=format (zero-width etc), Zl=line sep, Zp=para sep
    if cat in ("Cc", "Cf", "Zl", "Zp"):
        return False
    return True


def is_non_pronounceable(char: str) -> bool:
    """Check if a character is non-pronounceable (separator-like).

    Pronounceable characters are letters (hiragana, katakana, kanji, Latin)
    and digits. Non-pronounceable characters include punctuation, symbols,
    box drawing characters, and letter modifiers like ー.

    Note: Lm (Letter, modifier) like ー is treated as non-pronounceable
    because when repeated (e.g., ーーー) it's used as a visual separator.

    Args:
        char: A single character.

    Returns:
        True if the character is non-pronounceable.
    """
    if char.isspace():
        return False
    cat = unicodedata.category(char)
    # Lo=letter other (hiragana, katakana, kanji)
    # Ll=lowercase, Lu=uppercase, Lt=titlecase (Latin etc.)
    # Lm=modifier (like ー) - treat as separator-like when repeated
    if cat in ("Lo", "Ll", "Lu", "Lt"):
        return False
    # Nd=decimal digit, Nl=letter number, No=other number
    if cat.startswith("N"):
        return False
    return True


def is_separator_line(line: str) -> bool:
    """Check if a line is a visual separator.

    A line is a separator if either:
    1. It contains ONLY non-pronounceable visible characters (2+ chars), OR
    2. It contains 3+ of the same non-pronounceable character making up
       at least 50% of the visible characters (for mixed lines like ◆===◆)

    Examples of separators:
        --
        ---
        ==================
        ■■■■■■■■■■■■■■■■
        ーーー
        ◆================================◆

    Examples of non-separators:
        お世話になっております。
        詳細は---をご確認  (--- is <50% of line)
        ■  (single char, could be bullet)

    Args:
        line: A single line of text.

    Returns:
        True if the line is a visual separator.
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Get only visible (printable) characters
    visible = [c for c in stripped if is_printable_char(c)]
    if not visible:
        return False

    # Case 1: Pure non-pronounceable line with 2+ visible chars
    # (Single char could be a bullet point)
    if len(visible) >= 2 and all(is_non_pronounceable(c) for c in visible):
        return True

    # Case 2: Mixed line - need 3+ of same non-pronounceable char at 50%+ ratio
    char_counts = Counter(visible)
    for char, count in char_counts.items():
        if count < 3:
            continue
        if not is_non_pronounceable(char):
            continue
        if count / len(visible) >= 0.5:
            return True

    return False
