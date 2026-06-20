"""
Тесты с известными результатами.
Если эти тесты падают — stats engine сломан.
Никакого моккинга — чистая математика.
"""
import pytest
import numpy as np

from app.services.stats.corrections import benjamini_hochberg
from app.services.stats.hypothesis_tests import (
    check_normality,
    mann_whitney_test,
    welch_t_test,
    z_test_proportions,
)
from app.services.stats.interpreter import InsightSeverity, interpret
from app.services.stats.sample_size import (
    calculate_achieved_mde_conversion,
    calculate_achieved_mde_revenue,
    calculate_for_conversion,
)
from app.services.stats.sequential import always_valid_pvalue
from app.services.stats.srm import check_srm
from app.services.stats.srm import SRMResult
from app.services.stats.engine import MetricAnalysis, VariantAnalysis


# SRM ─

def test_srm_no_mismatch():
    result = check_srm(
        observed_counts={"control": 5000, "treatment": 5000},
        expected_splits={"control": 50.0, "treatment": 50.0},
    )
    assert result.srm_detected is False
    assert result.p_value > 0.01


def test_srm_detected():
    result = check_srm(
        observed_counts={"control": 10000, "treatment": 6000},
        expected_splits={"control": 50.0, "treatment": 50.0},
    )
    assert result.srm_detected is True
    assert result.p_value < 0.001


def test_srm_empty():
    result = check_srm(
        observed_counts={"control": 0, "treatment": 0},
        expected_splits={"control": 50.0, "treatment": 50.0},
    )
    assert result.srm_detected is False


# Z-test 

def test_z_test_significant():
    result = z_test_proportions(300, 10000, 400, 10000)
    assert result is not None
    assert result.is_significant is True
    assert result.p_value < 0.05
    assert result.effect_size == pytest.approx(0.01, abs=0.001)
    assert result.test_used == "z_test"


def test_z_test_not_significant():
    result = z_test_proportions(31, 1000, 33, 1000)
    assert result is not None
    assert result.is_significant is False


def test_z_test_insufficient_data():
    result = z_test_proportions(3, 10, 4, 10)
    assert result is None


# T-test 

def test_t_test_significant():
    rng = np.random.default_rng(42)
    control = rng.normal(loc=100, scale=20, size=500).tolist()
    treatment = rng.normal(loc=115, scale=20, size=500).tolist()

    result = welch_t_test(control, treatment)
    assert result is not None
    assert result.is_significant is True
    assert result.effect_size == pytest.approx(15, abs=3)
    assert result.test_used == "welch_t_test"


def test_t_test_no_difference():
    rng = np.random.default_rng(42)
    control = rng.normal(loc=100, scale=20, size=200).tolist()
    treatment = rng.normal(loc=101, scale=20, size=200).tolist()

    result = welch_t_test(control, treatment)
    assert result is not None
    assert result.is_significant is False


# Benjamini-Hochberg 

def test_bh_all_significant():
    result = benjamini_hochberg([0.001, 0.002, 0.003])
    assert all(result)


def test_bh_none_significant():
    result = benjamini_hochberg([0.5, 0.6, 0.7])
    assert not any(result)


def test_bh_mixed():
    p_values = [0.001, 0.008, 0.039, 0.041, 0.210, 0.630]
    result = benjamini_hochberg(p_values, alpha=0.05)
    assert result[0] is True
    assert result[1] is True
    assert result[4] is False
    assert result[5] is False


# Sample Size 

def test_sample_size_reasonable():
    result = calculate_for_conversion(baseline_rate=0.032, mde=0.005)
    assert 5_000 < result.sample_size_per_variant < 100_000


def test_sample_size_with_traffic():
    result = calculate_for_conversion(baseline_rate=0.05, mde=0.01, daily_traffic=1000)
    assert result.days_needed is not None
    assert result.days_needed > 0


# Normality check

def test_normality_normal_data():
    """Нормальные данные → is_normal=True."""
    rng = np.random.default_rng(42)
    values = rng.normal(loc=100, scale=15, size=200).tolist()
    is_normal, p_value = check_normality(values)
    assert is_normal is True
    assert p_value > 0.05


def test_normality_exponential_data():
    """Экспоненциальное распределение (как выручка) → is_normal=False."""
    rng = np.random.default_rng(42)
    # Сильно скошенное: много нулей, редкие большие значения
    values = rng.exponential(scale=1.0, size=200).tolist()
    is_normal, p_value = check_normality(values)
    assert is_normal is False
    assert p_value < 0.05


def test_normality_large_sample_always_true():
    """n > 5000 → всегда True (ЦПТ), без запуска теста."""
    rng = np.random.default_rng(42)
    # Даже экспоненциальное — True при большой выборке
    values = rng.exponential(scale=1.0, size=6000).tolist()
    is_normal, p_value = check_normality(values)
    assert is_normal is True


def test_normality_tiny_sample():
    """n < 3 → всегда True, тест нерелевантен."""
    is_normal, p_value = check_normality([1.0, 2.0])
    assert is_normal is True
    assert p_value == 1.0


# Mann-Whitney  

def test_mann_whitney_significant():
    """Явная разница медиан → значимо."""
    rng = np.random.default_rng(42)
    # Экспоненциальное распределение (ненормальное, как выручка)
    control = rng.exponential(scale=10.0, size=300).tolist()
    treatment = rng.exponential(scale=14.0, size=300).tolist()  # +40% к scale

    result = mann_whitney_test(control, treatment)
    assert result is not None
    assert result.is_significant is True
    assert result.p_value < 0.05
    assert result.test_used == "mann_whitney"
    assert result.effect_size > 0  # treatment > control


def test_mann_whitney_no_difference():
    """Одинаковые распределения → не значимо."""
    rng = np.random.default_rng(42)
    control = rng.exponential(scale=10.0, size=200).tolist()
    treatment = rng.exponential(scale=10.0, size=200).tolist()

    result = mann_whitney_test(control, treatment)
    assert result is not None
    assert result.is_significant is False


def test_mann_whitney_insufficient_data():
    """< 30 наблюдений → None."""
    result = mann_whitney_test([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
    assert result is None


# MDE post-experiment

def test_achieved_mde_revenue_decreases_with_sample():
    """Больше выборка → меньше MDE (больше чувствительности)."""
    mde_small = calculate_achieved_mde_revenue(100, baseline_std=50.0)
    mde_large = calculate_achieved_mde_revenue(10_000, baseline_std=50.0)
    assert mde_small > mde_large


def test_achieved_mde_revenue_formula():
    """Проверка формулы: mde = (z_α + z_β) * std * sqrt(2/n)."""
    from scipy.stats import norm as scipy_norm
    n, std = 1000, 100.0
    z_alpha = scipy_norm.ppf(0.975)  # alpha=0.05
    z_beta = scipy_norm.ppf(0.80)    # power=0.80
    expected = (z_alpha + z_beta) * std * (2 / n) ** 0.5

    result = calculate_achieved_mde_revenue(n, std)
    assert result == pytest.approx(expected, rel=1e-6)


def test_achieved_mde_conversion_consistent_with_sample_size():
    """
    MDE post-experiment согласован с pre-experiment калькулятором:
    если посчитать n для MDE=X, то achieved_mde(n) ≈ X.
    """
    baseline_rate = 0.05
    target_mde = 0.01

    # Pre-experiment: сколько нужно для MDE=0.01?
    n = calculate_for_conversion(baseline_rate, target_mde).sample_size_per_variant

    # Post-experiment: какой MDE при этой выборке?
    achieved = calculate_achieved_mde_conversion(n, baseline_rate)

    # Должны совпадать с точностью 5%
    assert achieved == pytest.approx(target_mde, rel=0.05)


def test_achieved_mde_invalid_inputs():
    """Некорректные входные данные → inf, не исключение."""
    assert calculate_achieved_mde_conversion(10, 0.05) == float("inf")   # n < 30
    assert calculate_achieved_mde_conversion(1000, 0.0) == float("inf")  # rate = 0
    assert calculate_achieved_mde_conversion(1000, 1.0) == float("inf")  # rate = 1
    assert calculate_achieved_mde_revenue(100, 0.0) == float("inf")      # std = 0


# mSPRT (M-007) ─────────────────────────────────────────────────────────────

def _binomial_arrays(p_c: float, p_t: float, n_c: int, n_t: int, seed: int = 42):
    """Build 0/1 arrays for control/treatment with given conversion rates."""
    rng = np.random.default_rng(seed)
    return (
        rng.binomial(1, p_c, n_c).astype(float).tolist(),
        rng.binomial(1, p_t, n_t).astype(float).tolist(),
    )


def test_msprt_no_effect():
    """Одинаковые распределения → высокий p-value, граница не пересечена."""
    ctrl, trt = _binomial_arrays(0.10, 0.10, n_c=2000, n_t=2000)
    result = always_valid_pvalue(ctrl, trt)
    assert result is not None
    # No effect → p-value should be well above α
    assert result.always_valid_pvalue > 0.10
    assert result.boundary_crossed is False
    assert result.likelihood_ratio < 1.0


def test_msprt_strong_effect():
    """Большой эффект → низкий p-value, граница пересечена."""
    # 10% control vs 15% treatment at large n — relative lift +50%.
    # mSPRT is inherently conservative vs fixed-horizon z-test, so we use
    # n=5000 to push the always-valid p-value well below 0.01.
    ctrl, trt = _binomial_arrays(0.10, 0.15, n_c=5000, n_t=5000)
    result = always_valid_pvalue(ctrl, trt)
    assert result is not None
    # Strong effect → p < 0.01 (mSPRT floor for this effect size)
    assert result.always_valid_pvalue < 0.01
    assert result.boundary_crossed is True
    assert result.likelihood_ratio > 100.0


def test_msprt_small_sample_returns_none():
    """n < 30 в любой группе → None (CLT floor)."""
    ctrl = [0.1] * 20
    trt  = [0.5] * 100
    result = always_valid_pvalue(ctrl, trt)
    assert result is None


def test_msprt_zero_variance_returns_none():
    """σ² = 0 (все значения идентичны) → None."""
    ctrl = [1.0] * 100
    trt  = [1.0] * 100
    result = always_valid_pvalue(ctrl, trt)
    assert result is None


def test_msprt_continuous_metric():
    """Revenue-style continuous data → mSPRT works on per-user values."""
    rng = np.random.default_rng(42)
    ctrl = rng.normal(loc=100, scale=20, size=500).tolist()
    trt  = rng.normal(loc=115, scale=20, size=500).tolist()
    result = always_valid_pvalue(ctrl, trt)
    assert result is not None
    assert result.always_valid_pvalue < 0.001
    assert result.boundary_crossed is True


def test_msprt_grows_strictly_with_sample_size():
    """При одинаковом эффекте больший sample → меньший always-valid p-value."""
    ctrl_small, trt_small = _binomial_arrays(0.10, 0.12, n_c=200, n_t=200)
    ctrl_big,   trt_big   = _binomial_arrays(0.10, 0.12, n_c=5000, n_t=5000)

    r_small = always_valid_pvalue(ctrl_small, trt_small)
    r_big   = always_valid_pvalue(ctrl_big, trt_big)
    assert r_small is not None and r_big is not None
    assert r_big.always_valid_pvalue < r_small.always_valid_pvalue


# Interpreter (M-007) ───────────────────────────────────────────────────────

def _make_metric(
    *,
    is_guardrail: bool = False,
    is_primary: bool = True,
    srm_detected: bool = False,
    srm_p_value: float = 0.5,
    guardrail_violated: bool = False,
    variants: list[VariantAnalysis] | None = None,
) -> MetricAnalysis:
    return MetricAnalysis(
        metric_id=None,
        metric_name="test_metric",
        metric_type="conversion",
        is_primary=is_primary,
        is_guardrail=is_guardrail,
        srm=SRMResult(
            srm_detected=srm_detected,
            p_value=srm_p_value,
            chi2=0.0,
            observed={},
            expected={},
        ),
        variants=variants or [],
        guardrail_violated=guardrail_violated,
    )


def _make_variant(
    *,
    name: str = "treatment",
    p_value: float | None = 0.04,
    effect_size: float | None = 0.1,
    relative_lift: float | None = 3.0,
    is_significant: bool | None = True,
    achieved_mde: float | None = 0.005,
    sequential_fpr: float | None = None,
    sequential_boundary_crossed: bool | None = None,
    mean: float = 0.10,
) -> VariantAnalysis:
    return VariantAnalysis(
        variant_id=None,
        variant_name=name,
        sample_size=1000,
        mean=mean,
        p_value=p_value,
        effect_size=effect_size,
        relative_lift=relative_lift,
        is_significant=is_significant,
        achieved_mde=achieved_mde,
        sequential_fpr=sequential_fpr,
        sequential_boundary_crossed=sequential_boundary_crossed,
    )


def test_interpreter_srm_detected():
    """SRM detected → один ERROR insight с srm_p_value в params."""
    metric = _make_metric(
        srm_detected=True, srm_p_value=0.001,
        variants=[_make_variant()],
    )
    insights = interpret([metric])
    srm_insights = [i for i in insights if i.type == "srm_detected"]
    assert len(srm_insights) == 1
    assert srm_insights[0].severity == InsightSeverity.ERROR
    assert srm_insights[0].params["p_value"] == 0.001


def test_interpreter_clear_winner():
    """p<0.01 + lift>2% + positive effect + no guardrail → SUCCESS."""
    metric = _make_metric(
        variants=[
            _make_variant(name="control", p_value=None, is_significant=None,
                          effect_size=None, relative_lift=None),
            _make_variant(
                name="treatment",
                p_value=0.005, is_significant=True,
                effect_size=0.05, relative_lift=5.0,
            ),
        ],
    )
    insights = interpret([metric])
    winners = [i for i in insights if i.type == "clear_winner"]
    assert len(winners) == 1
    assert winners[0].severity == InsightSeverity.SUCCESS
    assert winners[0].params["lift"] == 5.0


def test_interpreter_likely_winner():
    """p<0.05 + significant + positive but lift<2% → likely_winner."""
    metric = _make_metric(
        variants=[
            _make_variant(name="control", p_value=None, is_significant=None,
                          effect_size=None, relative_lift=None),
            _make_variant(
                name="treatment",
                p_value=0.04, is_significant=True,
                effect_size=0.005, relative_lift=0.5,
            ),
        ],
    )
    insights = interpret([metric])
    winners = [i for i in insights if i.type == "likely_winner"]
    assert len(winners) == 1
    assert winners[0].severity == InsightSeverity.SUCCESS


def test_interpreter_underpowered():
    """Не значимо + MDE > 50% от mean → WARNING underpowered."""
    metric = _make_metric(
        variants=[_make_variant(
            name="control", p_value=None, mean=0.10,
            effect_size=None, relative_lift=None,
            is_significant=None,
        ), _make_variant(
            name="treatment", p_value=0.4, is_significant=False,
            effect_size=0.001, relative_lift=1.0,
            achieved_mde=0.06,  # > 50% of 0.10
            mean=0.10,
        )],
    )
    insights = interpret([metric])
    underpowered = [i for i in insights if i.type == "underpowered"]
    assert len(underpowered) == 1
    assert underpowered[0].severity == InsightSeverity.WARNING


def test_interpreter_no_significance():
    """Не значимо + MDE small → INFO no_significance."""
    metric = _make_metric(
        variants=[_make_variant(
            name="control", p_value=None, mean=0.10,
            effect_size=None, relative_lift=None, is_significant=None,
        ), _make_variant(
            name="treatment", p_value=0.4, is_significant=False,
            effect_size=0.001, relative_lift=1.0,
            achieved_mde=0.005,  # < 50% of 0.10
            mean=0.10,
        )],
    )
    insights = interpret([metric])
    no_sig = [i for i in insights if i.type == "no_significance"]
    assert len(no_sig) == 1
    assert no_sig[0].severity == InsightSeverity.INFO


def test_interpreter_guardrail_violated():
    """Guardrail violation → один ERROR insight на эксперимент."""
    metric = _make_metric(guardrail_violated=True)
    insights = interpret([metric])
    guardrail = [i for i in insights if i.type == "guardrail_violated"]
    assert len(guardrail) == 1
    assert guardrail[0].severity == InsightSeverity.ERROR


def test_interpreter_sequential_boundary():
    """Sequential experiment + boundary crossed → INFO insight."""
    metric = _make_metric(
        variants=[
            _make_variant(name="control", p_value=None, is_significant=None,
                          effect_size=None, relative_lift=None),
            _make_variant(
                name="treatment",
                sequential_fpr=0.03, sequential_boundary_crossed=True,
                p_value=0.04, is_significant=True,
                effect_size=0.005, relative_lift=0.5,
            ),
        ],
    )
    insights = interpret([metric], is_sequential=True)
    seq = [i for i in insights if i.type == "sequential_boundary_crossed"]
    assert len(seq) == 1
    assert seq[0].severity == InsightSeverity.INFO
    assert seq[0].params["sequential_fpr"] == 0.03


def test_interpreter_sequential_boundary_only_for_sequential_experiments():
    """Boundary crossed, но is_sequential=False → insight не emit."""
    metric = _make_metric(
        variants=[
            _make_variant(name="control", p_value=None, is_significant=None,
                          effect_size=None, relative_lift=None),
            _make_variant(
                name="treatment",
                sequential_fpr=0.03, sequential_boundary_crossed=True,
                p_value=0.04, is_significant=True,
                effect_size=0.005, relative_lift=0.5,
            ),
        ],
    )
    insights = interpret([metric], is_sequential=False)
    seq = [i for i in insights if i.type == "sequential_boundary_crossed"]
    assert len(seq) == 0


def test_interpreter_srm_emitted_once_for_experiment():
    """Если SRM у нескольких метрик → emit только один insight."""
    metric_a = _make_metric(srm_detected=True, srm_p_value=0.001,
                            variants=[_make_variant()])
    metric_b = _make_metric(srm_detected=True, srm_p_value=0.001,
                            variants=[_make_variant(name="variant_b")])
    insights = interpret([metric_a, metric_b])
    srm_insights = [i for i in insights if i.type == "srm_detected"]
    assert len(srm_insights) == 1
