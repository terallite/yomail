"""Type stubs for yomail.patterns.names."""

def is_name_line(line: str) -> bool:
    """Check if a line appears to be a personal name.

    Args:
        line: A single line of text.

    Returns:
        True if the line matches name patterns.
    """
    ...

def contains_known_name(line: str) -> bool:
    """Check if a line contains a known Japanese name.

    Args:
        line: A single line of text.

    Returns:
        True if the line contains a known name.
    """
    ...
