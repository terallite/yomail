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
