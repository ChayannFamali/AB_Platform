from dataclasses import dataclass

from scipy.stats import chisquare


@dataclass
class SRMResult:
    srm_detected: bool
    p_value: float
    chi2: float
    observed: dict[str, int]
    expected: dict[str, float]


def check_srm(
    observed_counts: dict[str, int],   # {"control": 10240, "treatment": 9891}
    expected_splits: dict[str, float], # {"control": 50.0, "treatment": 50.0}
    threshold: float = 0.01,           # строгий порог для SRM
) -> SRMResult:
    """
    Chi-squared тест на Sample Ratio Mismatch.

    Если p < 0.01 → что-то сломано в assignment логике.
    Результатам эксперимента доверять нельзя до исправления.

    Порог 0.01 (не 0.05) — SRM это технический баг, не статистический вопрос.
    """
    total = sum(observed_counts.values())
    if total == 0:
        return SRMResult(
            srm_detected=False, p_value=1.0, chi2=0.0,
            observed=observed_counts, expected={}
        )

    variants = sorted(observed_counts.keys())
    observed = [observed_counts[v] for v in variants]
    expected_counts = {v: total * (expected_splits[v] / 100.0) for v in variants}
    expected = [expected_counts[v] for v in variants]

    chi2, p_value = chisquare(f_obs=observed, f_exp=expected)

    return SRMResult(
        srm_detected=bool(p_value < threshold),
        p_value=float(p_value),
        chi2=float(chi2),
        observed=observed_counts,
        expected=expected_counts,
    )