"""Japanese email greeting pattern detection.

Patterns match against neologdn-normalized text, so:
- Full-width ASCII is normalized to half-width
- Half-width katakana is normalized to full-width
- No need to handle width variants
"""

import re

# Greeting patterns - common Japanese email opening formulas
# These are compiled at module load time for efficiency
_GREETING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Most common business greetings
    re.compile(r"^.*お世話になっております.*$"),
    re.compile(r"^.*お世話になります.*$"),
    re.compile(r"^.*いつもお世話になっております.*$"),
    re.compile(r"^.*いつも大変お世話になっております.*$"),
    # Formal letter openings
    re.compile(r"^拝啓[、,]?.*$"),
    re.compile(r"^前略[、,]?.*$"),
    re.compile(r"^謹啓[、,]?.*$"),
    # Internal/casual greetings
    re.compile(r"^お疲れ様です[。.]?.*$"),
    re.compile(r"^お疲れさまです[。.]?.*$"),
    re.compile(r"^おつかれさまです[。.]?.*$"),
    re.compile(r"^お疲れ様でございます.*$"),
    # First contact / apology for sudden contact
    re.compile(r"^.*初めてご連絡.*$"),
    re.compile(r"^.*初めてメール.*$"),
    re.compile(r"^.*突然のご連絡.*$"),
    re.compile(r"^.*突然メール.*$"),
    re.compile(r"^.*突然のメール.*$"),
    # Long time no see
    re.compile(r"^.*ご無沙汰.*$"),
    # Thank you for X (often used as greeting)
    re.compile(r"^.*ご連絡(を)?ありがとう.*$"),
    re.compile(r"^.*ご返信(を)?ありがとう.*$"),
    re.compile(r"^.*ご対応(を)?ありがとう.*$"),
    re.compile(r"^.*メール(を)?ありがとう.*$"),
    # Addressing patterns (often precede or are greetings)
    re.compile(r"^.+様[,、]?$"),  # Tanaka-sama,
    re.compile(r"^.+さん[,、]?$"),  # Tanaka-san,
    re.compile(r"^.+殿[,、]?$"),  # Tanaka-dono,
    re.compile(r"^.+御中[,、]?$"),  # Company-onchuu,
    # Simple greetings
    re.compile(r"^こんにちは[。.]?$"),
    re.compile(r"^おはようございます[。.]?$"),
)


def is_greeting_line(line: str) -> bool:
    """Check if a line matches a greeting pattern.

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line matches a greeting pattern.
    """
    stripped = line.strip()
    if not stripped:
        return False

    return any(pattern.match(stripped) for pattern in _GREETING_PATTERNS)
