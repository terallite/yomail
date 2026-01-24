"""Tests for the Normalizer component."""

import pytest

from yomail import InvalidInputError, Normalizer


class TestNormalizerBasic:
    """Basic normalization tests."""

    def test_simple_text(self) -> None:
        """Plain text passes through with line splitting."""
        normalizer = Normalizer()
        result = normalizer.normalize("Hello\nWorld")

        assert result.lines == ("Hello", "World")
        assert result.text == "Hello\nWorld"

    def test_crlf_normalization(self) -> None:
        """CRLF line endings are converted to LF."""
        normalizer = Normalizer()
        result = normalizer.normalize("Line1\r\nLine2\r\n")

        assert result.lines == ("Line1", "Line2", "")
        assert "\r" not in result.text

    def test_cr_normalization(self) -> None:
        """Bare CR line endings are converted to LF."""
        normalizer = Normalizer()
        result = normalizer.normalize("Line1\rLine2")

        assert result.lines == ("Line1", "Line2")

    def test_empty_input_raises(self) -> None:
        """Empty string raises InvalidInputError."""
        normalizer = Normalizer()

        with pytest.raises(InvalidInputError):
            normalizer.normalize("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only input raises InvalidInputError."""
        normalizer = Normalizer()

        with pytest.raises(InvalidInputError):
            normalizer.normalize("   \n\n   \t  ")

    def test_preserves_blank_lines(self) -> None:
        """Blank lines are preserved in output."""
        normalizer = Normalizer()
        result = normalizer.normalize("Para1\n\nPara2")

        assert result.lines == ("Para1", "", "Para2")


class TestJapaneseNormalization:
    """Japanese-specific normalization tests."""

    def test_fullwidth_ascii_to_halfwidth(self) -> None:
        """Full-width ASCII characters become half-width."""
        normalizer = Normalizer()
        result = normalizer.normalize("ＡＢＣ１２３")

        assert result.text == "ABC123"

    def test_halfwidth_katakana_to_fullwidth(self) -> None:
        """Half-width katakana becomes full-width."""
        normalizer = Normalizer()
        result = normalizer.normalize("ｶﾀｶﾅ")

        assert result.text == "カタカナ"

    def test_prolonged_sound_marks(self) -> None:
        """Repeated prolonged sound marks are reduced."""
        normalizer = Normalizer()
        result = normalizer.normalize("すごーーーい")

        # neologdn reduces repeated ー
        assert "ーーー" not in result.text
        assert "ー" in result.text

    def test_tilde_normalization(self) -> None:
        """Wave dash variants are normalized.

        Note: neologdn removes tildes between numbers (10~20 → 1020).
        This test verifies consistent behavior with wave dash character.
        """
        normalizer = Normalizer()
        # Wave dash (U+301C) and ASCII tilde should normalize the same way
        result1 = normalizer.normalize("10~20")
        result2 = normalizer.normalize("10〜20")

        # Both should produce the same output
        assert result1.text == result2.text

    def test_mixed_japanese_text(self) -> None:
        """Mixed Japanese text is properly normalized."""
        normalizer = Normalizer()
        text = "お世話になっております。ＡＢＣ株式会社の田中です。"
        result = normalizer.normalize(text)

        # Full-width ABC should become half-width
        assert "ABC" in result.text
        assert "ＡＢＣ" not in result.text

    def test_email_greeting_preserved(self) -> None:
        """Common email greetings are preserved."""
        normalizer = Normalizer()
        result = normalizer.normalize("お世話になっております。")

        assert "お世話になっております" in result.text


class TestChoonpuLineNormalization:
    """Tests for CHOONPU (prolonged sound mark) line handling."""

    def test_choonpu_line_preserves_length(self) -> None:
        """Lines of only CHOONPU chars preserve length, become ASCII hyphens."""
        normalizer = Normalizer()
        result = normalizer.normalize("ーーーーーーーーーーーーーーーーーーーー")

        assert result.lines[0] == "-" * 20

    def test_box_drawing_heavy_preserves_length(self) -> None:
        """Box drawing heavy horizontal (━) preserves length."""
        normalizer = Normalizer()
        result = normalizer.normalize("━━━━━━━━━━━━━━━━━━━━")

        assert result.lines[0] == "-" * 20

    def test_box_drawing_light_preserves_length(self) -> None:
        """Box drawing light horizontal (─) preserves length."""
        normalizer = Normalizer()
        result = normalizer.normalize("──────────────────────")

        assert result.lines[0] == "-" * 22

    def test_horizontal_bar_preserves_length(self) -> None:
        """Horizontal bar (―) preserves length."""
        normalizer = Normalizer()
        result = normalizer.normalize("――――――――――――――――――――")

        assert result.lines[0] == "-" * 20

    def test_fullwidth_hyphen_preserves_length(self) -> None:
        """Fullwidth hyphen-minus (－) preserves length."""
        normalizer = Normalizer()
        result = normalizer.normalize("－－－－－－－－－－")

        assert result.lines[0] == "-" * 10

    def test_mixed_choonpu_preserves_length(self) -> None:
        """Mixed CHOONPU characters preserve total length."""
        normalizer = Normalizer()
        result = normalizer.normalize("ーー━━──――")

        assert result.lines[0] == "-" * 8

    def test_choonpu_line_strips_whitespace(self) -> None:
        """CHOONPU lines strip leading/trailing whitespace."""
        normalizer = Normalizer()
        result = normalizer.normalize("  ーーーーー  ")

        assert result.lines[0] == "-----"

    def test_mixed_dash_hyphen_line_unifies(self) -> None:
        """Lines with mix of ASCII hyphen and CHOONPU unify to majority."""
        normalizer = Normalizer()
        # This goes through neologdn (has ASCII -), then unify_delimiter_lines
        result = normalizer.normalize("-----ー-----ー-----")

        # Should unify to all hyphens (majority)
        assert result.lines[0] == "-" * 17

    def test_non_choonpu_delimiter_not_affected(self) -> None:
        """Lines with = or * go through neologdn normally."""
        normalizer = Normalizer()
        result = normalizer.normalize("====================")

        assert result.lines[0] == "===================="

    def test_choonpu_in_text_still_collapses(self) -> None:
        """CHOONPU in regular text still collapses (expected behavior)."""
        normalizer = Normalizer()
        result = normalizer.normalize("すごーーーい")

        # neologdn collapses repeated ー in text
        assert "ーーー" not in result.text
        assert "ー" in result.text

    def test_multiline_with_choonpu_line(self) -> None:
        """CHOONPU line in multiline text handled correctly."""
        normalizer = Normalizer()
        text = "お世話になっております\n━━━━━━━━━━\n田中です"
        result = normalizer.normalize(text)

        assert result.lines[0] == "お世話になっております"
        assert result.lines[1] == "-" * 10
        assert result.lines[2] == "田中です"

    def test_decorative_delimiter_preserves_shape(self) -> None:
        """Delimiter lines with decorative chars preserve shape."""
        normalizer = Normalizer()
        # Stars with box drawing dashes
        result = normalizer.normalize("★━━━━━━━━━━★")

        # Stars preserved, dashes become hyphens
        assert result.lines[0] == "★----------★"

    def test_bracket_delimiter_preserved(self) -> None:
        """Delimiter lines with brackets preserved."""
        normalizer = Normalizer()
        result = normalizer.normalize("【========================】")

        assert result.lines[0] == "【========================】"


class TestZeroWidthCharacters:
    """Tests for zero-width character stripping."""

    def test_embedded_bom_stripped(self) -> None:
        """Embedded BOM (U+FEFF) is stripped."""
        normalizer = Normalizer()
        result = normalizer.normalize("abc\ufeffdef")

        assert result.text == "abcdef"
        assert "\ufeff" not in result.text

    def test_zero_width_space_stripped(self) -> None:
        """Zero-width space (U+200B) is stripped."""
        normalizer = Normalizer()
        result = normalizer.normalize("abc\u200bdef")

        assert result.text == "abcdef"
        assert "\u200b" not in result.text

    def test_zero_width_joiner_stripped(self) -> None:
        """Zero-width joiner (U+200D) is stripped."""
        normalizer = Normalizer()
        result = normalizer.normalize("abc\u200ddef")

        assert result.text == "abcdef"

    def test_multiple_zero_width_chars_stripped(self) -> None:
        """Multiple different zero-width chars are all stripped."""
        normalizer = Normalizer()
        result = normalizer.normalize("a\ufeffb\u200bc\u200cd\u200de\u2060f")

        assert result.text == "abcdef"

    def test_zero_width_in_delimiter_line_stripped(self) -> None:
        """Zero-width chars in delimiter lines are stripped."""
        normalizer = Normalizer()
        result = normalizer.normalize("----\ufeff----\u200b----")

        assert result.lines[0] == "------------"

    def test_zero_width_in_choonpu_line_stripped(self) -> None:
        """Zero-width chars in CHOONPU lines don't prevent detection."""
        normalizer = Normalizer()
        # Box drawing with embedded ZWSP - should still detect as CHOONPU line
        result = normalizer.normalize("─────────\u200b───────────")

        # Should be 20 hyphens (not collapsed ーー)
        assert result.lines[0] == "-" * 20


class TestNormalizedEmailDataclass:
    """Tests for the NormalizedEmail dataclass."""

    def test_immutable(self) -> None:
        """NormalizedEmail is immutable."""
        normalizer = Normalizer()
        result = normalizer.normalize("Test")

        with pytest.raises(AttributeError):
            result.text = "Modified"  # type: ignore[misc]

    def test_lines_is_tuple(self) -> None:
        """Lines are returned as immutable tuple."""
        normalizer = Normalizer()
        result = normalizer.normalize("Line1\nLine2")

        assert isinstance(result.lines, tuple)
