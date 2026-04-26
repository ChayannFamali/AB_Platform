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
from app.services.stats.sample_size import (
    calculate_achieved_mde_conversion,
    calculate_achieved_mde_revenue,
    calculate_for_conversion,
)
from app.services.stats.srm import check_srm


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
