"""Tests for the A/B testing engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.ab_testing import ABTestEngine, WELCOME_VARIATIONS, FOLLOWUP_VARIATIONS


def _make_leads(n: int) -> list[dict]:
    """Create n fake lead records."""
    return [
        {
            "id": f"rec{i:04d}",
            "fields": {
                "Name": f"Lead {i}",
                "Email": f"lead{i}@example.com",
                "Status": "Intro-email",
            },
        }
        for i in range(1, n + 1)
    ]


def test_groups_of_10():
    engine = ABTestEngine(group_size=10)
    leads = _make_leads(30)
    groups = engine.create_groups(leads)

    assert len(groups) == 3
    assert all(len(g.leads) == 10 for g in groups)


def test_partial_last_group():
    engine = ABTestEngine(group_size=10)
    leads = _make_leads(25)
    groups = engine.create_groups(leads)

    assert len(groups) == 3
    assert len(groups[0].leads) == 10
    assert len(groups[1].leads) == 10
    assert len(groups[2].leads) == 5  # partial group


def test_variation_assignment_round_robin():
    engine = ABTestEngine(group_size=10)
    leads = _make_leads(40)
    groups = engine.create_groups(leads)

    # Group 1 → variation index 0, Group 2 → 1, Group 3 → 2, Group 4 → wraps to 0
    assert groups[0].welcome_variation["id"] == WELCOME_VARIATIONS[0]["id"]
    assert groups[1].welcome_variation["id"] == WELCOME_VARIATIONS[1]["id"]
    assert groups[2].welcome_variation["id"] == WELCOME_VARIATIONS[2]["id"]
    assert groups[3].welcome_variation["id"] == WELCOME_VARIATIONS[0]["id"]  # wrap

    assert groups[0].followup_variation["id"] == FOLLOWUP_VARIATIONS[0]["id"]
    assert groups[1].followup_variation["id"] == FOLLOWUP_VARIATIONS[1]["id"]


def test_group_numbering_starts_at_1():
    engine = ABTestEngine(group_size=10)
    groups = engine.create_groups(_make_leads(20))
    assert groups[0].group_number == 1
    assert groups[1].group_number == 2


def test_response_rate_calculation():
    engine = ABTestEngine(group_size=10)
    groups = engine.create_groups(_make_leads(10))
    g = groups[0]
    assert g.response_rate == 0.0

    g.emails_sent = 10
    g.responses_received = 3
    assert g.response_rate == 30.0


def test_empty_leads():
    engine = ABTestEngine(group_size=10)
    groups = engine.create_groups([])
    assert groups == []


def test_single_lead():
    engine = ABTestEngine(group_size=10)
    groups = engine.create_groups(_make_leads(1))
    assert len(groups) == 1
    assert len(groups[0].leads) == 1


if __name__ == "__main__":
    test_groups_of_10()
    test_partial_last_group()
    test_variation_assignment_round_robin()
    test_group_numbering_starts_at_1()
    test_response_rate_calculation()
    test_empty_leads()
    test_single_lead()
    print("All tests passed! ✅")
