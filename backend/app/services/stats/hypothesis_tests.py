import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import mannwhitneyu, norm, shapiro, ttest_ind


@dataclass
class TestResult:
    control_mean: float
    treatment_mean: float
    effect_size: float            # абсолютный lift
    relative_lift: float | None   # относительный lift (%)
    p_value: float
    ci_low: float
    ci_high: float
    is_significant: bool
    control_sample_size: int
    treatment_sample_size: int
    std_dev_control: float | None = None
    std_dev_treatment: float | None = None
    test_used: str = "unknown"    # "z_test"|"welch_t_test"|"mann_whitney"|"delta_method"


def check_normality(values: list[float], alpha: float = 0.05) -> tuple[bool, float]:
    """
    Тест Шапиро-Уилка на нормальность распределения.

    Shapiro-Wilk надёжен для 3 <= n <= 5000.
    При n > 5000: ЦПТ гарантирует сходимость → считаем нормальным.
    При n < 3:    слишком мало данных → тест нерелевантен, считаем нормальным.

    Returns:
        (is_normal, p_value)
        is_normal=True означает: нет оснований отвергнуть нормальность
    """
    n = len(values)
    if n < 3:
        return True, 1.0
    if n > 5000:
        return True, 1.0

    arr = np.array(values, dtype=float)
    if float(np.std(arr)) == 0.0:
        return True, 1.0

    stat, p_value = shapiro(arr)
    return bool(p_value > alpha), float(p_value)


def z_test_proportions(
    control_conversions: int,
    control_total: int,
    treatment_conversions: int,
    treatment_total: int,
    alpha: float = 0.05,
) -> TestResult | None:
    """
    Z-тест для пропорций. Используется для conversion метрик.
    """
    if control_total < 30 or treatment_total < 30:
        return None

    p_control = control_conversions / control_total
    p_treatment = treatment_conversions / treatment_total

    p_pool = (control_conversions + treatment_conversions) / (control_total + treatment_total)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / control_total + 1 / treatment_total))

    if se_pool == 0:
        return None

    z = (p_treatment - p_control) / se_pool
    p_value = float(2 * (1 - norm.cdf(abs(z))))

    se_diff = math.sqrt(
        p_control * (1 - p_control) / control_total +
        p_treatment * (1 - p_treatment) / treatment_total
    )
    z_crit = float(norm.ppf(1 - alpha / 2))
    effect = p_treatment - p_control

    return TestResult(
        control_mean=p_control,
        treatment_mean=p_treatment,
        effect_size=effect,
        relative_lift=(effect / p_control * 100) if p_control > 0 else None,
        p_value=p_value,
        ci_low=float(effect - z_crit * se_diff),
        ci_high=float(effect + z_crit * se_diff),
        is_significant=p_value < alpha,
        control_sample_size=control_total,
        treatment_sample_size=treatment_total,
        test_used="z_test",
    )


def welch_t_test(
    control_values: list[float],
    treatment_values: list[float],
    alpha: float = 0.05,
) -> TestResult | None:
    """
    T-тест Уэлча. Для нормально распределённых непрерывных метрик.
    Не предполагает равенство дисперсий.
    """
    if len(control_values) < 30 or len(treatment_values) < 30:
        return None

    c = np.array(control_values, dtype=float)
    t = np.array(treatment_values, dtype=float)

    t_stat, p_value = ttest_ind(c, t, equal_var=False)

    c_mean, t_mean = float(np.mean(c)), float(np.mean(t))
    c_std, t_std = float(np.std(c, ddof=1)), float(np.std(t, ddof=1))
    effect = t_mean - c_mean

    se_c = c_std ** 2 / len(c)
    se_t = t_std ** 2 / len(t)
    se_diff = math.sqrt(max(se_c + se_t, 1e-10))

    df_num = (se_c + se_t) ** 2
    df_den = (se_c ** 2 / (len(c) - 1)) + (se_t ** 2 / (len(t) - 1))
    df = df_num / df_den if df_den > 0 else 1

    from scipy.stats import t as t_dist
    t_crit = float(t_dist.ppf(1 - alpha / 2, df))

    return TestResult(
        control_mean=c_mean,
        treatment_mean=t_mean,
        effect_size=effect,
        relative_lift=(effect / c_mean * 100) if c_mean != 0 else None,
        p_value=float(p_value),
        ci_low=float(effect - t_crit * se_diff),
        ci_high=float(effect + t_crit * se_diff),
        is_significant=float(p_value) < alpha,
        control_sample_size=len(control_values),
        treatment_sample_size=len(treatment_values),
        std_dev_control=c_std,
        std_dev_treatment=t_std,
        test_used="welch_t_test",
    )


def mann_whitney_test(
    control_values: list[float],
    treatment_values: list[float],
    alpha: float = 0.05,
) -> TestResult | None:
    """
    Тест Манна-Уитни (U-тест). Непараметрический.

    Когда использовать:
        - Shapiro-Wilk отверг нормальность в одной из групп (p < 0.05)
        - n < 5000 (иначе t-тест устойчив через ЦПТ)

    CI: аппроксимация через Welch SE — допустимо для отображения.
    """
    if len(control_values) < 30 or len(treatment_values) < 30:
        return None

    c = np.array(control_values, dtype=float)
    t = np.array(treatment_values, dtype=float)

    _, p_value = mannwhitneyu(c, t, alternative="two-sided", method="auto")

    c_mean, t_mean = float(np.mean(c)), float(np.mean(t))
    c_std, t_std = float(np.std(c, ddof=1)), float(np.std(t, ddof=1))
    effect = t_mean - c_mean

    se_c = c_std ** 2 / len(c)
    se_t = t_std ** 2 / len(t)
    se_diff = math.sqrt(max(se_c + se_t, 1e-10))

    df_num = (se_c + se_t) ** 2
    df_den = (se_c ** 2 / (len(c) - 1)) + (se_t ** 2 / (len(t) - 1))
    df = df_num / df_den if df_den > 0 else 1

    from scipy.stats import t as t_dist
    t_crit = float(t_dist.ppf(1 - alpha / 2, df))

    return TestResult(
        control_mean=c_mean,
        treatment_mean=t_mean,
        effect_size=effect,
        relative_lift=(effect / c_mean * 100) if c_mean != 0 else None,
        p_value=float(p_value),
        ci_low=float(effect - t_crit * se_diff),
        ci_high=float(effect + t_crit * se_diff),
        is_significant=float(p_value) < alpha,
        control_sample_size=len(control_values),
        treatment_sample_size=len(treatment_values),
        std_dev_control=c_std,
        std_dev_treatment=t_std,
        test_used="mann_whitney",
    )


def delta_method_test(
    control_numerator: list[float],
    control_denominator: list[float],
    treatment_numerator: list[float],
    treatment_denominator: list[float],
    alpha: float = 0.05,
) -> TestResult | None:
    """
    Delta method (линеаризация Тейлора) для ratio метрик.

    Когда использовать:
        Metric = sum(X_i) / sum(Y_i) — отношение двух агрегатов.
        Примеры: выручка/сессия, CTR (клики/показы), конверсия/визит.

    Проблема наивного Welch t-test для ratio:
        Не учитывает ковариацию числителя и знаменателя.
        Переоценивает/недооценивает дисперсию → неверные p-value.

    Линеаризация (разложение первого порядка):
        θ = sum(X) / sum(Y)          ← ratio estimate
        Z_i = X_i - θ * Y_i          ← linearized per-user observation
        Затем Welch t-test на Z_ctrl vs Z_trt.

    control_mean / treatment_mean в TestResult = θ_ctrl, θ_trt (сами ratio).
    std_dev_control / std_dev_treatment = std(Z) — std линеаризованных значений,
        используется для MDE расчёта.

    Returns None если n < 30 или знаменатель = 0.
    """
    n_c = len(control_numerator)
    n_t = len(treatment_numerator)

    if n_c < 30 or n_t < 30:
        return None
    if len(control_denominator) != n_c or len(treatment_denominator) != n_t:
        return None

    c_x = np.array(control_numerator, dtype=float)
    c_y = np.array(control_denominator, dtype=float)
    t_x = np.array(treatment_numerator, dtype=float)
    t_y = np.array(treatment_denominator, dtype=float)

    sum_c_y = float(np.sum(c_y))
    sum_t_y = float(np.sum(t_y))

    if sum_c_y == 0 or sum_t_y == 0:
        return None

    # Ratio estimates (aggregate level — состоятельная оценка)
    theta_c = float(np.sum(c_x)) / sum_c_y
    theta_t = float(np.sum(t_x)) / sum_t_y

    # Linearized observations: Z_i = X_i - θ * Y_i
    z_c = c_x - theta_c * c_y
    z_t = t_x - theta_t * t_y

    # Welch t-test на линеаризованных значениях
    _, p_value = ttest_ind(z_c, z_t, equal_var=False)

    effect = theta_t - theta_c

    # Welch-Satterthwaite SE и df для CI
    var_c = float(np.var(z_c, ddof=1)) / n_c
    var_t = float(np.var(z_t, ddof=1)) / n_t
    se_diff = math.sqrt(max(var_c + var_t, 1e-10))

    df_num = (var_c + var_t) ** 2
    df_den = (var_c ** 2 / (n_c - 1)) + (var_t ** 2 / (n_t - 1))
    df = df_num / df_den if df_den > 0 else 1.0

    from scipy.stats import t as t_dist
    t_crit = float(t_dist.ppf(1 - alpha / 2, df))

    return TestResult(
        control_mean=theta_c,
        treatment_mean=theta_t,
        effect_size=effect,
        relative_lift=(effect / theta_c * 100) if theta_c != 0 else None,
        p_value=float(p_value),
        ci_low=float(effect - t_crit * se_diff),
        ci_high=float(effect + t_crit * se_diff),
        is_significant=float(p_value) < alpha,
        control_sample_size=n_c,
        treatment_sample_size=n_t,
        std_dev_control=float(np.std(z_c, ddof=1)),
        std_dev_treatment=float(np.std(z_t, ddof=1)),
        test_used="delta_method",
    )
