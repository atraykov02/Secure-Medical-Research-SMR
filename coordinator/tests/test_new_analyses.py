import pytest

from coordinator.app.models import AnalysisType
from coordinator.app.schemas import StudyCreate
from coordinator.app.verification.reference_analysis import compare_results


@pytest.mark.parametrize("analysis,values,bgw,key", [
    ("ALLELE_FREQUENCY", [{"cohort_size": 100, "alternative_allele_count": 20}],
     {"cohort_size": 100, "alternative_allele_count": 20, "allele_frequency_percent": 10.0}, "allele_frequency_percent"),
    ("COHORT_MEAN_AGE", [{"cohort_size": 2, "age_sum": 100}],
     {"cohort_size": 2, "mean_age": 50.0}, "mean_age"),
    ("THERAPY_RESPONSE_RATE", [{"cohort_size": 10, "responder_count": 7}],
     {"cohort_size": 10, "treated_count": 10, "responder_count": 7, "response_rate_percent": 70.0}, "response_rate_percent"),
    ("VARIANT_DISEASE_ASSOCIATION", [{"cohort_size": 10, "a": 4, "b": 2, "c": 2, "d": 2}],
     {"cohort_size": 10, "odds_ratio": 2.0}, "odds_ratio"),
])
def test_new_plaintext_reference_matches_bgw(analysis, values, bgw, key):
    reference, differences, verified = compare_results(analysis, values, bgw)
    assert reference[key] == bgw[key]
    assert differences[key] == 0
    assert verified


def _payload(analysis, **criteria):
    return {"name": "New analysis", "analysis_type": analysis, "organization_ids": ["1", "2", "3"], "criteria": criteria}


@pytest.mark.parametrize("analysis,criteria", [
    (AnalysisType.ALLELE_FREQUENCY, {}),
    (AnalysisType.THERAPY_RESPONSE_RATE, {}),
    (AnalysisType.VARIANT_DISEASE_ASSOCIATION, {"variant_code": "V1"}),
])
def test_new_analysis_required_criteria(analysis, criteria):
    with pytest.raises(ValueError):
        StudyCreate.model_validate(_payload(analysis, **criteria))


def test_mean_age_accepts_optional_variant_and_therapy():
    study = StudyCreate.model_validate(_payload(AnalysisType.COHORT_MEAN_AGE, disease_code="DX"))
    assert study.criteria.variant_code is None
