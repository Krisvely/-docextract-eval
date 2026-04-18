from eval.invariants.semantic import RequiredTopLevelFieldsPresent


def test_required_fields_present_passes():
    run = {
        "summary": {
            "top_level_fields": {
                "insured_name": "A",
                "carrier": "B",
                "policy_number": "C",
                "policy_effective_date": "2021-01-01",
                "valuation_date": "2026-02-28",
                "total_paid": 1.0,
                "total_incurred": 2.0,
                "claim_count": 3,
            }
        }
    }

    result = RequiredTopLevelFieldsPresent().evaluate(run)
    assert result.passed is True


def test_required_fields_present_fails_when_missing():
    run = {
        "summary": {
            "top_level_fields": {
                "insured_name": "A",
                "carrier": "B"
            }
        }
    }

    result = RequiredTopLevelFieldsPresent().evaluate(run)
    assert result.passed is False
    assert "policy_number" in result.details["missing_fields"]