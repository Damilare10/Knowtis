"""
Unit tests for TemporalParser.resolve() method.

Tests the new resolver against the fixture corpus in temporal_cases.py.
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.services.temporal_parser import TemporalParser, DatePrecision
from tests.fixtures.temporal_cases import CASES


def parse_anchor(anchor_iso: str) -> datetime:
    """Parse ISO anchor string to timezone-aware datetime."""
    return datetime.fromisoformat(anchor_iso)


def parse_expected(expected_iso: str | None) -> datetime | None:
    """Parse expected UTC ISO string to naive UTC datetime."""
    if expected_iso is None:
        return None
    # Expected format: "YYYY-MM-DDTHH:MM:SSZ" (naive UTC)
    dt = datetime.fromisoformat(expected_iso.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def precision_from_str(s: str) -> DatePrecision:
    """Convert precision string to enum."""
    return {
        "exact": DatePrecision.EXACT,
        "day_only": DatePrecision.DAY_ONLY,
        "unknown": DatePrecision.UNKNOWN,
    }[s]


class TestTemporalParserResolve:
    """Test the resolve() method against all fixture cases."""
    
    @pytest.mark.parametrize("expression,anchor_iso,expected_iso,precision_str", CASES)
    def test_resolve(self, expression: str, anchor_iso: str, expected_iso: str | None, precision_str: str):
        anchor = parse_anchor(anchor_iso)
        expected_dt = parse_expected(expected_iso)
        expected_precision = precision_from_str(precision_str)
        
        result_dt, result_precision = TemporalParser.resolve(expression, anchor)
        
        assert result_precision == expected_precision, \
            f"Expression: {expression!r}\nExpected precision: {expected_precision}, got: {result_precision}"
        
        if expected_dt is None:
            assert result_dt is None, \
                f"Expression: {expression!r}\nExpected None, got: {result_dt}"
        else:
            assert result_dt is not None, \
                f"Expression: {expression!r}\nExpected datetime, got None"
            # Compare naive UTC datetimes (ignore microseconds)
            assert result_dt.replace(microsecond=0) == expected_dt.replace(microsecond=0), \
                f"Expression: {expression!r}\nExpected: {expected_dt.isoformat()}Z, got: {result_dt.isoformat()}Z"


class TestTemporalParserEdgeCases:
    """Additional edge case tests."""
    
    def test_explicit_false_resolves_relative_spans(self):
        """explicit=False should resolve relative spans."""
        anchor = parse_anchor("2024-06-12T10:00:00+01:00")
        result, precision = TemporalParser.resolve("in 2 days", anchor, explicit=False)
        assert precision == DatePrecision.DAY_ONLY
        # in 2 days from Wed Jun 12 = Fri Jun 14
        assert result == parse_expected("2024-06-13T23:00:00Z")
    
    def test_explicit_true_ignores_relative_spans(self):
        """explicit=True should NOT resolve vague relative spans without explicit dates."""
        anchor = parse_anchor("2024-06-12T10:00:00+01:00")
        result, precision = TemporalParser.resolve("in 2 days", anchor, explicit=True)
        # "in 2 days" is not an explicit date reference, should return UNKNOWN
        assert precision == DatePrecision.UNKNOWN
        assert result is None
    
    def test_explicit_true_resolves_explicit_dates(self):
        """explicit=True should still resolve explicit dates like 'Friday'."""
        anchor = parse_anchor("2024-06-12T10:00:00+01:00")
        result, precision = TemporalParser.resolve("Friday", anchor, explicit=True)
        assert precision == DatePrecision.DAY_ONLY
        assert result == parse_expected("2024-06-13T23:00:00Z")
    
    def test_none_expression(self):
        """None expression should return UNKNOWN."""
        result, precision = TemporalParser.resolve(None)
        assert precision == DatePrecision.UNKNOWN
        assert result is None
    
    def test_empty_string(self):
        """Empty string should return UNKNOWN."""
        result, precision = TemporalParser.resolve("")
        assert precision == DatePrecision.UNKNOWN
        assert result is None
    
    def test_whitespace_only(self):
        """Whitespace-only string should return UNKNOWN."""
        result, precision = TemporalParser.resolve("   ")
        assert precision == DatePrecision.UNKNOWN
        assert result is None
    
    def test_timezone_conversion(self):
        """Result should be naive UTC regardless of anchor timezone."""
        # Anchor in UTC (9am UTC = 10am Lagos)
        anchor_utc = datetime(2024, 6, 12, 9, 0, tzinfo=timezone.utc)
        result, _ = TemporalParser.resolve("tomorrow", anchor_utc)
        assert result.tzinfo is None
        # Tomorrow in Lagos: Jun 12 10am -> Jun 13 00:00 Lagos = Jun 12 23:00 UTC
        assert result == datetime(2024, 6, 12, 23, 0)
        
        # Anchor in Africa/Lagos (UTC+1)
        anchor_lagos = datetime(2024, 6, 12, 10, 0, tzinfo=timezone(timedelta(hours=1)))
        result, _ = TemporalParser.resolve("tomorrow", anchor_lagos)
        assert result.tzinfo is None
        # Same result: Jun 13 00:00 Lagos = Jun 12 23:00 UTC
        assert result == datetime(2024, 6, 12, 23, 0)
    
    def test_legacy_parse_date_time_still_works(self):
        """The old parse_date_time method should still work for backward compatibility."""
        anchor = parse_anchor("2024-06-12T10:00:00+01:00")
        result = TemporalParser.parse_date_time("Friday 2pm", anchor)
        assert result is not None
        assert result == parse_expected("2024-06-14T13:00:00Z")  # 2pm Lagos = 13:00 UTC
    
    def test_has_date_reference(self):
        """has_date_reference should detect various date references."""
        assert TemporalParser.has_date_reference("meeting tomorrow")
        assert TemporalParser.has_date_reference("on Friday")
        assert TemporalParser.has_date_reference("June 15")
        assert TemporalParser.has_date_reference("15/06/2024")
        assert TemporalParser.has_date_reference("30th")
        assert TemporalParser.has_date_reference("in 2 days")
        assert not TemporalParser.has_date_reference("soon")
        assert not TemporalParser.has_date_reference("later")
        assert not TemporalParser.has_date_reference("")
        assert not TemporalParser.has_date_reference("?")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])