"""Tests for Japanese name pattern detection."""

from yomail.patterns.names import is_name_line, contains_known_name


class TestIsNameLine:
    """Tests for is_name_line function."""

    # === Positive cases: Should detect as names ===

    def test_full_name_kanji(self) -> None:
        """Full name in kanji is detected."""
        assert is_name_line("田中太郎")
        assert is_name_line("山田一郎")
        assert is_name_line("佐藤明")  # last + first from dataset

    def test_last_name_only(self) -> None:
        """Last name only is detected (common in signatures)."""
        assert is_name_line("田中")
        assert is_name_line("鈴木")
        assert is_name_line("佐藤")

    def test_name_with_katakana_reading(self) -> None:
        """Name with katakana reading in parentheses."""
        assert is_name_line("田中太郎 (タナカタロウ)")
        assert is_name_line("田中太郎(タナカタロウ)")
        assert is_name_line("田中太郎（タナカタロウ）")  # fullwidth parens

    def test_name_with_romaji(self) -> None:
        """Name with romaji after slash."""
        assert is_name_line("田中 / Tanaka")
        assert is_name_line("田中太郎 / Taro Tanaka")

    def test_romaji_name_only(self) -> None:
        """Romaji name only."""
        assert is_name_line("Taro Tanaka")
        assert is_name_line("Hanako Suzuki")

    def test_name_from_training_data(self) -> None:
        """Names that appear in our training data failures."""
        assert is_name_line("新井辰夫")
        assert is_name_line("秋山竜太")

    # === Negative cases: Should NOT detect as names ===

    def test_casual_closing_not_name(self) -> None:
        """Casual closings should not be detected as names."""
        assert not is_name_line("ファイト!")
        assert not is_name_line("以上!")
        assert not is_name_line("よろしく!")

    def test_greeting_not_name(self) -> None:
        """Greetings should not be detected as names."""
        assert not is_name_line("お世話になっております")
        assert not is_name_line("お疲れ様です")

    def test_closing_phrase_not_name(self) -> None:
        """Closing phrases should not be detected as names."""
        assert not is_name_line("よろしくお願いいたします")
        assert not is_name_line("ご確認ください")

    def test_body_content_not_name(self) -> None:
        """Regular body content should not be detected."""
        assert not is_name_line("会議は明日の10時からです")
        assert not is_name_line("資料を添付しました")

    def test_empty_and_blank(self) -> None:
        """Empty and blank lines are not names."""
        assert not is_name_line("")
        assert not is_name_line("   ")
        assert not is_name_line("\t")

    # === Adversarial cases ===

    def test_name_with_extra_spaces(self) -> None:
        """Names with extra spaces should still work."""
        assert is_name_line("  田中太郎  ")  # leading/trailing spaces
        assert is_name_line("田中太郎 ")

    def test_name_with_honorific_not_detected(self) -> None:
        """Name with honorific is body text, not signature."""
        # These are too long/complex to be signature lines
        assert not is_name_line("田中太郎様")
        assert not is_name_line("田中さん")
        assert not is_name_line("鈴木部長")

    def test_company_name_not_person_name(self) -> None:
        """Company names should not trigger name detection."""
        assert not is_name_line("株式会社田中")
        assert not is_name_line("田中商事株式会社")

    def test_long_line_with_name_not_detected(self) -> None:
        """Long lines containing names are body, not signature."""
        assert not is_name_line("田中さんに連絡してください")
        assert not is_name_line("鈴木様からのメールを転送します")

    def test_partial_romaji_not_name(self) -> None:
        """Partial or malformed romaji should not match."""
        assert not is_name_line("taro")  # lowercase only
        assert not is_name_line("TARO TANAKA")  # all caps
        assert not is_name_line("Taro")  # single name

    def test_katakana_word_not_name(self) -> None:
        """Random katakana words should not match."""
        assert not is_name_line("ファイル")
        assert not is_name_line("メール")
        assert not is_name_line("プロジェクト")

    def test_punctuation_prevents_match(self) -> None:
        """Lines with punctuation are not signature names."""
        assert not is_name_line("田中。")
        assert not is_name_line("田中、")
        assert not is_name_line("田中!")


class TestContainsKnownName:
    """Tests for contains_known_name function."""

    def test_line_with_embedded_name(self) -> None:
        """Lines containing names among other text."""
        assert contains_known_name("担当: 田中")
        assert contains_known_name("連絡先: 鈴木")

    def test_email_with_name(self) -> None:
        """Email addresses with names."""
        assert contains_known_name("tanaka@example.com")

    def test_line_without_name(self) -> None:
        """Lines without any names."""
        assert not contains_known_name("会議室A")
        assert not contains_known_name("10:00-12:00")
        assert not contains_known_name("")
