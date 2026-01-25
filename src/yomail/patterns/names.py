"""Japanese name pattern detection for signature identification.

Uses the gimei dataset (https://github.com/willnet/gimei) to detect
Japanese personal names in email signatures.
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml


def _load_names_data() -> dict:
    """Load names data from YAML file."""
    # Try multiple locations for the data file
    candidates = [
        Path(__file__).parent.parent.parent.parent / "data" / "names.yaml",
        Path("data/names.yaml"),
    ]

    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f)

    # Return empty structure if file not found
    return {"first_name": {"male": [], "female": []}, "last_name": []}


@lru_cache(maxsize=1)
def _get_name_sets() -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    """Get sets of names for efficient lookup.

    Returns:
        Tuple of (last_names_kanji, first_names_kanji, all_names_katakana, all_names_romaji)
    """
    data = _load_names_data()

    last_names_kanji: set[str] = set()
    first_names_kanji: set[str] = set()
    all_katakana: set[str] = set()
    all_romaji: set[str] = set()

    # Process last names
    for entry in data.get("last_name", []):
        if len(entry) >= 4:
            kanji, _hiragana, katakana, romaji = entry[:4]
            last_names_kanji.add(kanji)
            all_katakana.add(katakana)
            all_romaji.add(romaji)

    # Process first names (male and female)
    first_name_data = data.get("first_name", {})
    for gender in ["male", "female"]:
        for entry in first_name_data.get(gender, []):
            if len(entry) >= 4:
                kanji, _hiragana, katakana, romaji = entry[:4]
                first_names_kanji.add(kanji)
                all_katakana.add(katakana)
                all_romaji.add(romaji)

    return (
        frozenset(last_names_kanji),
        frozenset(first_names_kanji),
        frozenset(all_katakana),
        frozenset(all_romaji),
    )


# Pattern for name with reading: 田中太郎 (タナカタロウ) or 田中太郎(タナカタロウ)
_NAME_WITH_READING_PATTERN = re.compile(
    r"^([^\s(（]+)\s*[（(]([ァ-ヶー\s]+)[）)]$"
)

# Pattern for name with romaji: 田中太郎 / Taro Tanaka or 田中 Tanaka
_NAME_WITH_ROMAJI_PATTERN = re.compile(
    r"^([^\s/]+)\s*[/／]\s*([A-Za-z\s]+)$"
)

# Pattern for romaji name only: Taro Tanaka
_ROMAJI_NAME_PATTERN = re.compile(
    r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$"
)


def is_name_line(line: str) -> bool:
    """Check if a line appears to be a personal name (signature-style).

    Detects:
    - Short lines consisting primarily of known names
    - Name with katakana reading: 田中太郎 (タナカタロウ)
    - Name with romaji: 田中 / Tanaka
    - Romaji name: Taro Tanaka

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line appears to be a personal name.
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Check for name with reading pattern
    if _NAME_WITH_READING_PATTERN.match(stripped):
        return True

    # Check for name with romaji pattern
    if _NAME_WITH_ROMAJI_PATTERN.match(stripped):
        return True

    # Check for romaji-only name
    if _ROMAJI_NAME_PATTERN.match(stripped):
        return True

    # For short lines, check if they contain known names
    # Only check lines that look like they could be just a name (short, no punctuation)
    if len(stripped) <= 15 and not any(c in stripped for c in "。、！？!?,.:;"):
        last_names, first_names, katakana_names, romaji_names = _get_name_sets()

        # Check for full name (last + first)
        for last in last_names:
            if stripped.startswith(last):
                remainder = stripped[len(last):]
                # Remainder should be a first name or empty (last name only)
                if not remainder or remainder in first_names:
                    return True

        # Check for katakana name
        if stripped in katakana_names:
            return True

        # Check for known last name only (common in signatures)
        if stripped in last_names and len(stripped) <= 4:
            return True

    return False


def contains_known_name(line: str) -> bool:
    """Check if a line contains a known Japanese name.

    This is a broader check than is_name_line - it returns True if
    the line contains any known name, even if it's not the entire line.
    Useful for detecting signature blocks that contain names among other info.

    Args:
        line: A single normalized line of text.

    Returns:
        True if the line contains a known name.
    """
    stripped = line.strip()
    if not stripped:
        return False

    last_names, first_names, katakana_names, romaji_names = _get_name_sets()

    # Check for any known last name
    for name in last_names:
        if name in stripped:
            return True

    # Check for katakana names
    for name in katakana_names:
        if name in stripped:
            return True

    # Check for romaji names (case insensitive for contains check)
    stripped_lower = stripped.lower()
    for name in romaji_names:
        if name.lower() in stripped_lower:
            return True

    return False
