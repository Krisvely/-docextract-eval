from eval.invariants.selector import invariants_for
from eval.invariants.precision import NumericFieldMatchesGolden, StringFieldMatchesGolden
from eval.invariants.semantic import RequiredTopLevelFieldsPresent


def _names(invariants):
    return {getattr(inv, "name", type(inv).__name__) for inv in invariants}


def test_loss_run_selector_includes_core_checks():
    invariants = invariants_for("loss_run")
    names = _names(invariants)
    assert "required_top_level_fields_present" in names
    assert "valuation_date_not_before_policy_effective_date" in names
    assert "document_check_paid_sum_check" in names
    assert any(n.startswith("numeric_field_matches_golden::total_paid") for n in names)


def test_binder_selector_is_distinct_from_loss_run():
    loss_run_names = _names(invariants_for("binder"))
    binder_names = _names(invariants_for("binder"))
    # Binder selector should not pull in loss-run-specific checks.
    assert "document_check_paid_sum_check" not in binder_names
    assert "valuation_date_not_before_policy_effective_date" not in binder_names
    # But it must still define some precision checks...
    assert any(n.startswith("string_field_matches_golden::binder_number") for n in binder_names)
    # ...and its own cross-field check for date order.
    assert "document_check_binder_dates_in_order" in binder_names
    assert binder_names == loss_run_names  # idempotent selector


def test_sov_selector_covers_total_tiv_style_numeric():
    names = _names(invariants_for("sov"))
    assert any(n.startswith("numeric_field_matches_golden::total_tiv") for n in names)
    # SOV selector owns its own cross-field sum check, separate from loss_run's.
    assert "document_check_tiv_sum_check" in names
    assert "document_check_paid_sum_check" not in names


def test_coi_selector_covers_certificate_holder_and_coverage_count():
    names = _names(invariants_for("coi"))
    assert any(n.startswith("string_field_matches_golden::certificate_holder") for n in names)
    assert any(n.startswith("string_field_matches_golden::insured_name") for n in names)
    assert any(n.startswith("numeric_field_matches_golden::coverage_count") for n in names)
    # Must not pull in loss-run-specific checks.
    assert "document_check_paid_sum_check" not in names
    assert "valuation_date_not_before_policy_effective_date" not in names


def test_endorsement_selector_covers_change_type_and_premium_delta():
    names = _names(invariants_for("endorsement"))
    assert any(n.startswith("string_field_matches_golden::endorsement_number") for n in names)
    assert any(n.startswith("string_field_matches_golden::change_type") for n in names)
    assert any(n.startswith("numeric_field_matches_golden::premium_delta") for n in names)
    # Must not pull in loss-run-specific checks.
    assert "document_check_paid_sum_check" not in names


def test_unknown_doc_type_falls_back_to_loss_run():
    fallback = invariants_for("does_not_exist")
    default = invariants_for("loss_run")
    assert _names(fallback) == _names(default)


def test_none_doc_type_falls_back_to_loss_run():
    assert _names(invariants_for(None)) == _names(invariants_for("loss_run"))


def test_selector_returns_instances_of_expected_classes():
    invariants = invariants_for("loss_run")
    types = {type(inv) for inv in invariants}
    assert RequiredTopLevelFieldsPresent in types
    assert NumericFieldMatchesGolden in types
    assert StringFieldMatchesGolden in types
