TOLERANCE = 1e-9


def calculate_variant_frequency_plaintext(values: list[dict]) -> dict:
    cohort = sum(int(v["cohort_size"]) for v in values)
    variants = sum(int(v["variant_count"]) for v in values)
    return {
        "cohort_size": cohort,
        "variant_count": variants,
        "frequency_percent": round(variants / cohort * 100, 4) if cohort else None,
    }


def calculate_therapy_response_plaintext(values: list[dict]) -> dict:
    a, b, c, d = (sum(int(v[key]) for v in values) for key in ("a", "b", "c", "d"))
    ad, bc = a * d, b * c
    return {
        "cohort_size": a + b + c + d, "a": a, "b": b, "c": c, "d": d,
        "ad": ad, "bc": bc, "odds_ratio": round(ad / bc, 6) if bc else None,
    }


def calculate_sum_plaintext(analysis_type: str, values: list[dict]) -> dict:
    cohort = sum(int(v["cohort_size"]) for v in values)
    if analysis_type == "ALLELE_FREQUENCY":
        total = sum(int(v["alternative_allele_count"]) for v in values)
        return {"cohort_size": cohort, "alternative_allele_count": total,
                "allele_frequency_percent": round(total / (2 * cohort) * 100, 4) if cohort else None}
    if analysis_type == "COHORT_MEAN_AGE":
        total = sum(int(v["age_sum"]) for v in values)
        return {"cohort_size": cohort, "mean_age": round(total / cohort, 4) if cohort else None}
    responders = sum(int(v["responder_count"]) for v in values)
    return {"cohort_size": cohort, "treated_count": cohort, "responder_count": responders,
            "response_rate_percent": round(responders / cohort * 100, 4) if cohort else None}


def compare_results(analysis_type: str, values: list[dict], bgw: dict) -> tuple[dict, dict, bool]:
    if analysis_type == "VARIANT_FREQUENCY":
        reference = calculate_variant_frequency_plaintext(values)
        keys = ("cohort_size", "variant_count", "frequency_percent")
    elif analysis_type in ("THERAPY_RESPONSE", "VARIANT_DISEASE_ASSOCIATION"):
        reference = calculate_therapy_response_plaintext(values)
        keys = ("cohort_size", "odds_ratio")
    else:
        reference = calculate_sum_plaintext(analysis_type, values)
        keys = {
            "ALLELE_FREQUENCY": ("cohort_size", "alternative_allele_count", "allele_frequency_percent"),
            "COHORT_MEAN_AGE": ("cohort_size", "mean_age"),
            "THERAPY_RESPONSE_RATE": ("cohort_size", "responder_count", "response_rate_percent"),
        }[analysis_type]
    differences = {}
    verified = True
    for key in keys:
        left, right = reference.get(key), bgw.get(key)
        difference = 0.0 if left is None and right is None else (
            None if left is None or right is None else abs(float(left) - float(right))
        )
        differences[key] = difference
        verified = verified and difference is not None and difference <= TOLERANCE
    return reference, differences, verified
