"""Type stubs for yomail.patterns.signatures."""

def is_contact_info_line(line: str) -> bool:
    """Check if a line contains contact information.

    Args:
        line: A single line of text.

    Returns:
        True if the line contains contact information.
    """
    ...

def is_company_line(line: str) -> bool:
    """Check if a line contains company name patterns.

    Args:
        line: A single line of text.

    Returns:
        True if the line contains company patterns.
    """
    ...

def is_position_line(line: str) -> bool:
    """Check if a line contains job position/title patterns.

    Args:
        line: A single line of text.

    Returns:
        True if the line contains position patterns.
    """
    ...
