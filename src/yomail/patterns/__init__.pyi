"""Type stubs for yomail.patterns - Pattern databases for Japanese email text classification."""

def is_greeting_line(line: str) -> bool:
    """Check if a line matches Japanese greeting patterns.

    Detects common Japanese email greetings like:
    - お疲れ様です (otsukaresama desu)
    - お世話になっております (osewa ni natte orimasu)
    - いつもお世話になっております
    - ご連絡ありがとうございます

    Args:
        line: A single line of text.

    Returns:
        True if the line matches a greeting pattern.
    """
    ...

def is_closing_line(line: str) -> bool:
    """Check if a line matches Japanese closing patterns.

    Detects common Japanese email closings like:
    - よろしくお願いします (yoroshiku onegaishimasu)
    - 以上、よろしくお願いいたします
    - ご確認ください
    - ご検討ください

    Args:
        line: A single line of text.

    Returns:
        True if the line matches a closing pattern.
    """
    ...

def is_separator_line(line: str) -> bool:
    """Check if a line is a visual separator.

    Detects lines that visually separate sections, such as:
    - Lines of dashes: ----------
    - Lines of equals: ==========
    - Lines of asterisks: **********
    - Decorative patterns: ★★★★★

    Args:
        line: A single line of text.

    Returns:
        True if the line is a visual separator.
    """
    ...

def is_contact_info_line(line: str) -> bool:
    """Check if a line contains contact information.

    Detects lines with:
    - Phone numbers (TEL, 電話)
    - Fax numbers (FAX)
    - Email addresses
    - URLs

    Args:
        line: A single line of text.

    Returns:
        True if the line contains contact information.
    """
    ...

def is_company_line(line: str) -> bool:
    """Check if a line contains company name patterns.

    Detects lines with Japanese company suffixes:
    - 株式会社 (kabushiki kaisha)
    - 有限会社 (yuugen kaisha)
    - 合同会社 (goudou kaisha)
    - Co., Ltd. / Inc. / Corp.

    Args:
        line: A single line of text.

    Returns:
        True if the line contains company patterns.
    """
    ...

__all__: list[str]
