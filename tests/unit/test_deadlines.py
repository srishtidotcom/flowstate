from datetime import datetime, timezone

import pytest

from backend.enrichment.deadlines import normalize_deadline


REFERENCE_UTC = datetime(2026, 9, 17, 16, 24, 26, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("today", "2026-09-17T23:59:00+05:30"),
        ("tomorrow", "2026-09-18T23:59:00+05:30"),
        ("EOD", "2026-09-17T18:00:00+05:30"),
        ("by EOD today", "2026-09-17T18:00:00+05:30"),
        ("by EOD tomorrow", "2026-09-18T18:00:00+05:30"),
        ("EOW", "2026-09-18T18:00:00+05:30"),
        ("Friday", "2026-09-18T23:59:00+05:30"),
        ("this Friday", "2026-09-18T23:59:00+05:30"),
        ("next Friday", "2026-09-25T23:59:00+05:30"),
        ("by EOD Friday", "2026-09-18T18:00:00+05:30"),
        ("Monday", "2026-09-21T23:59:00+05:30"),
    ],
)
def test_relative_deadlines_use_fixed_event_timestamp(value, expected):
    assert normalize_deadline(value, REFERENCE_UTC) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-01", "2026-10-01T23:59:00+05:30"),
        ("2026-10-01T10:00:00Z", "2026-10-01T15:30:00+05:30"),
        ("2026-10-01T10:00:00", "2026-10-01T10:00:00+05:30"),
    ],
)
def test_absolute_iso_values_are_normalized_to_ist(value, expected):
    assert normalize_deadline(value, REFERENCE_UTC) == expected


@pytest.mark.parametrize("value", [None, "", "sometime soon", "2026-99-99"])
def test_invalid_or_unrecognized_values_return_none(value):
    assert normalize_deadline(value, REFERENCE_UTC) is None


def test_naive_reference_is_safely_interpreted_as_ist():
    reference = datetime(2026, 9, 17, 23, 30)

    assert (
        normalize_deadline("tomorrow", reference_date=reference)
        == "2026-09-18T23:59:00+05:30"
    )
