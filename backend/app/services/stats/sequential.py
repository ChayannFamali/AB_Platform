"""
Mixture Sequential Probability Ratio Test (mSPRT) — always-valid p-values.

Implements the closed-form mSPRT statistic for two-sample normal location
testing (Howard et al. 2021, "Uniformly Valid Confidence Sets and Hypothesis
Tests", arXiv:2101.06195). The mixture prior N(0, ρ_max·σ²) is calibrated
so that the resulting always-valid p-value is finite for any sample size
without inflating the false-positive rate.

Result: p_t = 1 / (1 + Λ_t) where Λ_t is the marginal likelihood ratio.
The boundary is implicitly defined: reject H₀ when p_t < α.

Closed-form (no numerical integration):

    n_eff = 1 / (1/n_c + 1/n_t)
    σ²    = pooled variance
    τ²    = ρ_max · σ²                          (mixture variance)
    d     = mean_t - mean_c                     (effect)

    log Λ = -½·log(n_eff·ρ_max + 1)
            + n_eff²·d² / [2·σ²·(n_eff + 1/ρ_max)]

Always-valid p-value p = 1 / (1 + exp(log Λ)).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SequentialResult:
    always_valid_pvalue: float
    boundary_crossed: bool
    likelihood_ratio: float


def always_valid_pvalue(
    control: np.ndarray | list[float],
    treatment: np.ndarray | list[float],
    alpha: float = 0.05,
    rho_max: float = 0.001,
) -> SequentialResult | None:
    """
    mSPRT always-valid p-value for two-sample location test (Howard 2021).

    Returns None when the sample is too small for CLT applicability
    (n < 30 in either group) or when the pooled variance is zero.

    Args:
        control:    control variant samples (binary 0/1 for conversion,
                    floats for revenue/duration).
        treatment:  treatment variant samples (same shape as control).
        alpha:      significance level for the boundary test
                    (always-valid p-value is compared against this).
        rho_max:    mixture prior variance scale (default 0.001 per
                    Howard et al.). Larger values make the test more
                    conservative.

    Returns:
        SequentialResult(always_valid_pvalue, boundary_crossed,
        likelihood_ratio), or None when n < 30 or σ² == 0.
    """
    control = np.asarray(control, dtype=float)
    treatment = np.asarray(treatment, dtype=float)
    n_c, n_t = int(control.size), int(treatment.size)

    # CLT floor: skip when sample is too small for normal approximation.
    # The mixture test relies on Gaussian likelihood, so n >= 30 in each
    # group is a conservative minimum.
    if n_c < 30 or n_t < 30:
        return None

    if rho_max <= 0:
        raise ValueError("rho_max must be positive")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0, 1)")

    d = float(np.mean(treatment) - np.mean(control))
    var_c = float(np.var(control, ddof=1)) if n_c > 1 else 0.0
    var_t = float(np.var(treatment, ddof=1)) if n_t > 1 else 0.0
    denom = n_c + n_t - 2
    if denom <= 0:
        return None
    sigma2 = ((n_c - 1) * var_c + (n_t - 1) * var_t) / denom
    if sigma2 <= 0:
        # Zero variance → no information → mSPRT undefined.
        return None

    n_eff = 1.0 / (1.0 / n_c + 1.0 / n_t)

    # Closed-form log Λ (see module docstring).
    log_lambda = (
        -0.5 * np.log(n_eff * rho_max + 1.0)
        + (n_eff * n_eff * d * d) / (2.0 * sigma2 * (n_eff + 1.0 / rho_max))
    )

    # Overflow protection for extreme effect sizes / sample sizes.
    if log_lambda > 500.0:
        likelihood_ratio = float("inf")
        always_valid_p = 0.0
    elif log_lambda < -500.0:
        likelihood_ratio = 0.0
        always_valid_p = 1.0
    else:
        likelihood_ratio = float(np.exp(log_lambda))
        always_valid_p = 1.0 / (1.0 + likelihood_ratio)

    return SequentialResult(
        always_valid_pvalue=always_valid_p,
        boundary_crossed=always_valid_p < alpha,
        likelihood_ratio=likelihood_ratio,
    )