"""Japanese email signature pattern detection.

Patterns for detecting:
- Contact information (phone, fax, email, URL, postal code)
- Company names and suffixes
- Position/title patterns

Note: Visual separator detection is in separators.py
"""

import re

# Contact information patterns
_CONTACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Phone patterns (after normalization, TEL/Tel are ASCII)
    re.compile(r"TEL\s*[::]", re.IGNORECASE),
    re.compile(r"Tel\s*[::]", re.IGNORECASE),
    re.compile(r"電話\s*[::]"),
    re.compile(r"携帯\s*[::]"),
    re.compile(r"直通\s*[::]"),
    re.compile(r"内線\s*[::]"),
    # Fax patterns
    re.compile(r"FAX\s*[::]", re.IGNORECASE),
    re.compile(r"Fax\s*[::]", re.IGNORECASE),
    re.compile(r"ファックス\s*[::]"),
    re.compile(r"ファクス\s*[::]"),
    # Phone number patterns (Japanese format)
    re.compile(r"\d{2,4}-\d{2,4}-\d{4}"),  # 03-1234-5678
    re.compile(r"\(\d{2,4}\)\s*\d{2,4}-\d{4}"),  # (03) 1234-5678
    re.compile(r"0\d{1,3}-\d{1,4}-\d{4}"),  # Japanese phone format
    # Email patterns
    re.compile(r"E-?mail\s*[::]", re.IGNORECASE),
    re.compile(r"Mail\s*[::]", re.IGNORECASE),
    re.compile(r"メール\s*[::]"),
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),  # Email address
    # URL patterns
    re.compile(r"https?://"),
    re.compile(r"www\."),
    re.compile(r"URL\s*[::]", re.IGNORECASE),
    re.compile(r"HP\s*[::]"),
    re.compile(r"ホームページ\s*[::]"),
    # Postal code patterns
    re.compile(r"〒\s*\d{3}-?\d{4}"),  # Postal code with symbol
    re.compile(r"郵便番号\s*[::]?\s*\d{3}-?\d{4}"),
    # Address indicators
    re.compile(r"住所\s*[::]"),
    re.compile(r"所在地\s*[::]"),
)

# Company name patterns
_COMPANY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Company type suffixes
    re.compile(r"株式会社"),
    re.compile(r"有限会社"),
    re.compile(r"合同会社"),
    re.compile(r"合資会社"),
    re.compile(r"合名会社"),
    re.compile(r"\(株\)"),  # Normalized from （株）
    re.compile(r"\(有\)"),  # Normalized from （有）
    re.compile(r"Inc\.?", re.IGNORECASE),
    re.compile(r"Corp\.?", re.IGNORECASE),
    re.compile(r"Co\.,?\s*Ltd\.?", re.IGNORECASE),
    re.compile(r"LLC", re.IGNORECASE),
)

# Position/title patterns (commonly found in signatures)
_POSITION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"代表取締役"),
    re.compile(r"取締役"),
    re.compile(r"部長"),
    re.compile(r"課長"),
    re.compile(r"係長"),
    re.compile(r"主任"),
    re.compile(r"マネージャー"),
    re.compile(r"リーダー"),
    re.compile(r"担当"),
    re.compile(r"スタッフ"),
    re.compile(r"チーフ"),
    re.compile(r"ディレクター"),
    re.compile(r"エンジニア"),
    re.compile(r"Manager", re.IGNORECASE),
    re.compile(r"Director", re.IGNORECASE),
    re.compile(r"Engineer", re.IGNORECASE),
)


def is_contact_info_line(line: str) -> bool:
    """Check if a line contains contact information.

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line contains phone, fax, email, URL, or postal code patterns.
    """
    if not line.strip():
        return False

    return any(pattern.search(line) for pattern in _CONTACT_PATTERNS)


def is_company_line(line: str) -> bool:
    """Check if a line contains a company name pattern.

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line contains company suffixes like 株式会社, Inc., etc.
    """
    if not line.strip():
        return False

    return any(pattern.search(line) for pattern in _COMPANY_PATTERNS)


def is_position_line(line: str) -> bool:
    """Check if a line contains a position/title pattern.

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line contains position patterns like 部長, Manager, etc.
    """
    if not line.strip():
        return False

    return any(pattern.search(line) for pattern in _POSITION_PATTERNS)
