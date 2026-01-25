"""Tests for the FeatureExtractor component."""

from yomail import FeatureExtractor, Normalizer, StructuralAnalyzer
from yomail.pipeline.content_filter import ContentFilter


def _extract_features(text: str):
    """Helper to run the full pipeline and extract features."""
    normalizer = Normalizer()
    content_filter = ContentFilter()
    analyzer = StructuralAnalyzer()
    extractor = FeatureExtractor()

    normalized = normalizer.normalize(text)
    filtered = content_filter.filter(normalized)
    analysis = analyzer.analyze(filtered)
    return extractor.extract(analysis, filtered)


class TestPositionalFeatures:
    """Positional feature extraction tests."""

    def test_position_normalized_single_line(self) -> None:
        """Single line has position 0."""
        result = _extract_features("Hello")

        assert result.line_features[0].position_normalized == 0.0

    def test_position_normalized_multiple_lines(self) -> None:
        """Position is normalized from 0 to 1."""
        result = _extract_features("Line1\nLine2\nLine3")

        assert result.line_features[0].position_normalized == 0.0
        assert result.line_features[1].position_normalized == 0.5
        assert result.line_features[2].position_normalized == 1.0

    def test_position_reverse(self) -> None:
        """Reverse position is 1 - normalized position."""
        result = _extract_features("Line1\nLine2\nLine3")

        assert result.line_features[0].position_reverse == 1.0
        assert result.line_features[1].position_reverse == 0.5
        assert result.line_features[2].position_reverse == 0.0

    def test_lines_from_start_end(self) -> None:
        """Absolute line distances from start and end."""
        result = _extract_features("A\nB\nC\nD")

        assert result.line_features[0].lines_from_start == 0
        assert result.line_features[0].lines_from_end == 3
        assert result.line_features[3].lines_from_start == 3
        assert result.line_features[3].lines_from_end == 0

    def test_position_relative_to_quotes(self) -> None:
        """Position relative to quote blocks."""
        text = "Before\n> Quoted\nAfter"
        result = _extract_features(text)

        # First quote is at index 1
        assert result.line_features[0].position_rel_first_quote < 0  # Before quote
        assert result.line_features[2].position_rel_first_quote > 0  # After quote

    def test_no_quotes_zero_relative_position(self) -> None:
        """No quotes means zero relative position."""
        result = _extract_features("No quotes here\nJust text")

        assert result.line_features[0].position_rel_first_quote == 0.0
        assert result.line_features[0].position_rel_last_quote == 0.0


class TestContentFeatures:
    """Content feature extraction tests."""

    def test_line_length(self) -> None:
        """Line length is character count."""
        result = _extract_features("Hello")

        assert result.line_features[0].line_length == 5

    def test_blank_lines_tracked_as_context(self) -> None:
        """Blank lines are tracked via blank_lines_before/after."""
        result = _extract_features("Text\n\nMore text")

        # After filtering, we have 2 content lines
        assert len(result.line_features) == 2
        # First line ("Text") has 1 blank after it
        assert result.line_features[0].blank_lines_after == 1
        # Second line ("More text") has 1 blank before it
        assert result.line_features[1].blank_lines_before == 1

    def test_whitespace_only_filtered_out(self) -> None:
        """Whitespace-only lines are filtered out, tracked via context."""
        result = _extract_features("Text\n   \nMore")

        # Only 2 content lines after filtering
        assert len(result.line_features) == 2
        assert result.line_features[0].blank_lines_after == 1
        assert result.line_features[1].blank_lines_before == 1

    def test_leading_trailing_whitespace(self) -> None:
        """Whitespace counts are non-negative."""
        result = _extract_features("    Code block")

        features = result.line_features[0]
        assert features.leading_whitespace >= 0
        assert features.trailing_whitespace >= 0

    def test_kanji_ratio(self) -> None:
        """Kanji ratio is computed correctly."""
        result = _extract_features("日本語")  # 3 kanji

        assert result.line_features[0].kanji_ratio == 1.0

    def test_hiragana_ratio(self) -> None:
        """Hiragana ratio is computed correctly."""
        result = _extract_features("あいう")  # 3 hiragana

        assert result.line_features[0].hiragana_ratio == 1.0

    def test_katakana_ratio(self) -> None:
        """Katakana ratio is computed correctly."""
        result = _extract_features("アイウ")  # 3 katakana

        assert result.line_features[0].katakana_ratio == 1.0

    def test_ascii_ratio(self) -> None:
        """ASCII ratio is computed correctly."""
        result = _extract_features("Hello")

        assert result.line_features[0].ascii_ratio == 1.0

    def test_digit_ratio(self) -> None:
        """Digit ratio is computed correctly."""
        result = _extract_features("12345")

        assert result.line_features[0].digit_ratio == 1.0

    def test_mixed_character_ratios(self) -> None:
        """Mixed text has appropriate ratios."""
        result = _extract_features("日本Hello")  # 2 kanji + 5 ASCII = 7 chars

        features = result.line_features[0]
        assert 0.2 < features.kanji_ratio < 0.4  # ~28%
        assert 0.6 < features.ascii_ratio < 0.8  # ~71%

    def test_content_lines_only_no_empty(self) -> None:
        """Empty lines are filtered out, only content lines remain."""
        result = _extract_features("Text\n\nMore")

        # After filtering, only 2 content lines remain
        assert len(result.line_features) == 2
        # First line is "Text", second is "More"
        assert result.line_features[0].line_length == 4
        assert result.line_features[1].line_length == 4


class TestStructuralFeatures:
    """Structural feature passthrough tests."""

    def test_quote_depth_passed_through(self) -> None:
        """Quote depth from structural analysis is preserved."""
        result = _extract_features("> Quoted")

        assert result.line_features[0].quote_depth == 1

    def test_delimiter_flags_passed_through(self) -> None:
        """Delimiter flags from structural analysis are preserved."""
        result = _extract_features("Text\n---\nMore")

        assert result.line_features[1].is_delimiter is True
        assert result.line_features[2].preceded_by_delimiter is True


class TestPatternFlags:
    """Pattern flag detection tests."""

    def test_greeting_detection(self) -> None:
        """Greeting patterns are detected."""
        result = _extract_features("お世話になっております。")

        assert result.line_features[0].is_greeting is True

    def test_closing_detection(self) -> None:
        """Closing patterns are detected."""
        result = _extract_features("よろしくお願いいたします。")

        assert result.line_features[0].is_closing is True

    def test_contact_info_detection_phone(self) -> None:
        """Phone patterns are detected."""
        result = _extract_features("TEL: 03-1234-5678")

        assert result.line_features[0].has_contact_info is True

    def test_contact_info_detection_email(self) -> None:
        """Email patterns are detected."""
        result = _extract_features("test@example.com")

        assert result.line_features[0].has_contact_info is True

    def test_contact_info_detection_url(self) -> None:
        """URL patterns are detected."""
        result = _extract_features("https://example.com")

        assert result.line_features[0].has_contact_info is True

    def test_company_pattern_detection(self) -> None:
        """Company suffix patterns are detected."""
        result = _extract_features("株式会社テスト")

        assert result.line_features[0].has_company_pattern is True

    def test_company_pattern_abbreviation(self) -> None:
        """Abbreviated company patterns are detected."""
        result = _extract_features("(株)テスト")

        assert result.line_features[0].has_company_pattern is True

    def test_position_pattern_detection(self) -> None:
        """Position/title patterns are detected."""
        result = _extract_features("営業部長")

        assert result.line_features[0].has_position_pattern is True

    def test_visual_separator_detection(self) -> None:
        """Visual separators are detected."""
        result = _extract_features("----------")

        assert result.line_features[0].is_visual_separator is True

    def test_meta_discussion_detection(self) -> None:
        """Meta-discussion markers are detected."""
        result = _extract_features("例えば以下のように")

        assert result.line_features[0].has_meta_discussion is True

    def test_quotation_marks_detection(self) -> None:
        """Lines with quotation marks are detected."""
        result = _extract_features("「これはサンプルです」")

        assert result.line_features[0].is_inside_quotation_marks is True

    def test_normal_text_no_flags(self) -> None:
        """Normal body text has no pattern flags."""
        result = _extract_features("明日の会議について確認させてください。")

        features = result.line_features[0]
        assert features.is_greeting is False
        assert features.is_closing is False
        assert features.has_contact_info is False
        assert features.has_company_pattern is False


class TestContextualFeatures:
    """Contextual feature aggregation tests."""

    def test_context_greeting_count(self) -> None:
        """Greeting count in context window."""
        text = "お世話になっております。\n本文です。\nいつもお世話になっております。"
        result = _extract_features(text)

        # Middle line should see 2 greetings in its context
        assert result.line_features[1].context_greeting_count == 2

    def test_blank_line_context_features(self) -> None:
        """Blank lines tracked via blank_lines_before/after."""
        # Note: leading/trailing blanks are removed by normalizer
        # Internal blanks between content lines are preserved
        text = "First\n\n\nSecond\n\nThird"
        result = _extract_features(text)

        # Three content lines after filtering
        assert len(result.line_features) == 3
        # First line has no blanks before, 2 blanks after
        assert result.line_features[0].blank_lines_before == 0
        assert result.line_features[0].blank_lines_after == 2
        # Second line has 2 blanks before, 1 blank after
        assert result.line_features[1].blank_lines_before == 2
        assert result.line_features[1].blank_lines_after == 1
        # Third line has 1 blank before, no blanks after
        assert result.line_features[2].blank_lines_before == 1
        assert result.line_features[2].blank_lines_after == 0

    def test_context_quote_count(self) -> None:
        """Quote count in context window."""
        text = "Normal\n> Quote1\n> Quote2\n> Quote3\nNormal"
        result = _extract_features(text)

        # Line at index 2 should see quotes around it
        assert result.line_features[2].context_quote_count >= 2

    def test_context_excludes_self(self) -> None:
        """Context features exclude the line itself."""
        text = "お世話になっております。"  # Just a greeting
        result = _extract_features(text)

        # The greeting line itself should have 0 context greetings
        assert result.line_features[0].context_greeting_count == 0


class TestIntegration:
    """Integration tests with realistic email patterns."""

    def test_full_email_features(self) -> None:
        """Feature extraction on a realistic email."""
        text = """田中様

お世話になっております。
ABC株式会社の山田です。

明日の会議について確認させてください。

よろしくお願いいたします。

---
山田太郎
ABC株式会社
TEL: 03-1234-5678"""

        result = _extract_features(text)

        # Verify total lines
        assert result.total_lines > 0

        # Find greeting line
        greeting_lines = [
            f for f in result.line_features if f.is_greeting
        ]
        assert len(greeting_lines) >= 1

        # Find closing line
        closing_lines = [
            f for f in result.line_features if f.is_closing
        ]
        assert len(closing_lines) >= 1

        # Find signature area (contact info, company)
        contact_lines = [
            f for f in result.line_features if f.has_contact_info
        ]
        assert len(contact_lines) >= 1

        company_lines = [
            f for f in result.line_features if f.has_company_pattern
        ]
        assert len(company_lines) >= 1

    def test_reply_email_features(self) -> None:
        """Feature extraction on a reply email."""
        text = """ご連絡ありがとうございます。

承知しました。

On 2024/01/15, Tanaka wrote:
> 明日の件、確認お願いします。

よろしくお願いします。"""

        result = _extract_features(text)

        # Should detect quote context
        quote_features = [
            f for f in result.line_features if f.quote_depth > 0
        ]
        assert len(quote_features) >= 1

        # Lines near quotes should have context_quote_count > 0
        non_quote_with_context = [
            f for f in result.line_features
            if f.quote_depth == 0 and f.context_quote_count > 0
        ]
        assert len(non_quote_with_context) >= 1

    def test_minimal_input_features(self) -> None:
        """Minimal input produces expected features."""
        normalizer = Normalizer()
        content_filter = ContentFilter()
        analyzer = StructuralAnalyzer()
        extractor = FeatureExtractor()

        # Normalize a minimal valid input
        normalized = normalizer.normalize("x")
        filtered = content_filter.filter(normalized)
        analysis = analyzer.analyze(filtered)
        result = extractor.extract(analysis, filtered)

        assert result.total_lines == 1


class TestGreetingPatterns:
    """Tests for greeting pattern detection."""

    def test_osewa_ni_natte_orimasu(self) -> None:
        """お世話になっております is detected."""
        result = _extract_features("お世話になっております。")
        assert result.line_features[0].is_greeting is True

    def test_osewa_ni_narimasu(self) -> None:
        """お世話になります is detected."""
        result = _extract_features("お世話になります。")
        assert result.line_features[0].is_greeting is True

    def test_otsukare_sama(self) -> None:
        """お疲れ様です is detected."""
        result = _extract_features("お疲れ様です。")
        assert result.line_features[0].is_greeting is True

    def test_haikei(self) -> None:
        """拝啓 is detected."""
        result = _extract_features("拝啓、貴社ますます")
        assert result.line_features[0].is_greeting is True

    def test_addressee_pattern(self) -> None:
        """Addressee patterns like 様 are detected."""
        result = _extract_features("田中様")
        assert result.line_features[0].is_greeting is True


class TestClosingPatterns:
    """Tests for closing pattern detection."""

    def test_yoroshiku_onegai_itashimasu(self) -> None:
        """よろしくお願いいたします is detected."""
        result = _extract_features("よろしくお願いいたします。")
        assert result.line_features[0].is_closing is True

    def test_keigu(self) -> None:
        """敬具 is detected."""
        result = _extract_features("敬具")
        assert result.line_features[0].is_closing is True

    def test_ijou(self) -> None:
        """以上 is detected."""
        result = _extract_features("以上です。")
        assert result.line_features[0].is_closing is True


class TestSignaturePatterns:
    """Tests for signature-related pattern detection."""

    def test_kabushiki_gaisha(self) -> None:
        """株式会社 is detected."""
        result = _extract_features("株式会社ABC")
        assert result.line_features[0].has_company_pattern is True

    def test_phone_number(self) -> None:
        """Phone number patterns are detected."""
        result = _extract_features("03-1234-5678")
        assert result.line_features[0].has_contact_info is True

    def test_postal_code(self) -> None:
        """Postal code patterns are detected."""
        result = _extract_features("〒100-0001")
        assert result.line_features[0].has_contact_info is True


