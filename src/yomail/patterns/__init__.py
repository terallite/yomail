"""Pattern databases for Japanese email text classification."""

from yomail.patterns.closings import is_closing_line
from yomail.patterns.greetings import is_greeting_line
from yomail.patterns.separators import is_separator_line
from yomail.patterns.signatures import (
    is_company_line,
    is_contact_info_line,
)

__all__ = [
    "is_closing_line",
    "is_company_line",
    "is_contact_info_line",
    "is_greeting_line",
    "is_separator_line",
]
