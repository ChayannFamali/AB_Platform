import math
from dataclasses import dataclass

from scipy.stats import norm


@dataclass
class SampleSizeResult:
    sample_size_per_variant: int
    total_sample_size: int
    baseline_rate: float
    target_rate: float
    mde: float
    alpha: float
    power: float
    days_needed: int | None = None


def calculate_for_conversion(
    baseline_rate: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
    daily_traffic: int | None = None,
) -> SampleSizeResult:
    """
    Минимальная выборка для обнаружения эффекта mde при заданной мощности.
    Pre-experiment: считать ДО запуска.
    """
    p1 = baseline_rate
    p2 = baseline_rate + mde

    z_alpha = float(norm.ppf(1 - alpha / 2))
    z_beta = float(norm.ppf(power))
    p_avg = (p1 + p2) / 2

    numerator = (
        z_alpha * math.sqrt(2 * p_avg * (1 - p_avg)) +
        z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    denominator = (p2 - p1) ** 2

    n = math.ceil(numerator / denominator)
    days = math.ceil((n * 2) / daily_traffic) if daily_traffic else None

    return SampleSizeResult(
        sample_size_per_variant=n,
        total_sample_size=n * 2,
        baseline_rate=p1,
        target_rate=p2,
        mde=mde,
        alpha=alpha,
        power=power,
        days_needed=days,
    )


def calculate_for_revenue(
    baseline_mean: float,
    baseline_std: float,
    mde_absolute: float,
    alpha: float = 0.05,
    power: float = 0.80,
    daily_traffic: int | None = None,
) -> SampleSizeResult:
    """Минимальная выборка для непрерывных метрик (revenue, duration)."""
    z_alpha = float(norm.ppf(1 - alpha / 2))
    z_beta = float(norm.ppf(power))

    n = math.ceil(2 * ((z_alpha + z_beta) * baseline_std / mde_absolute) ** 2)
    days = math.ceil((n * 2) / daily_traffic) if daily_traffic else None

    return SampleSizeResult(
        sample_size_per_variant=n,
        total_sample_size=n * 2,
        baseline_rate=baseline_mean,
        target_rate=baseline_mean + mde_absolute,
        mde=mde_absolute,
        alpha=alpha,
        power=power,
        days_needed=days,
    )


# Post-experiment MDE ──────────────────────────────────────────────────────

def calculate_achieved_mde_revenue(
    sample_size_per_variant: int,
    baseline_std: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """
    MDE при имеющейся выборке для continuous метрики (revenue, duration).

    Обратная формула: n = 2 * ((z_α + z_β) * std / mde)²
    → mde = (z_α + z_β) * std * sqrt(2 / n)

    Применение: "не значимо — но мы бы увидели эффект ≥ X руб. если он был."
    """
    if sample_size_per_variant < 2 or baseline_std <= 0:
        return float("inf")

    z_alpha = float(norm.ppf(1 - alpha / 2))
    z_beta = float(norm.ppf(power))
    return (z_alpha + z_beta) * baseline_std * math.sqrt(2 / sample_size_per_variant)


def calculate_achieved_mde_conversion(
    sample_size_per_variant: int,
    baseline_rate: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """
    MDE при имеющейся выборке для conversion метрики.

    Аналитической формулы нет — используем бинарный поиск:
    ищем min_mde такое что calculate_for_conversion(...).sample_size ≈ n.

    Применение: "не значимо — но мы бы увидели эффект ≥ +X.X% если он был."

    Returns float("inf") если расчёт невозможен (нет данных, rate=0 или 1).
    """
    if sample_size_per_variant < 30:
        return float("inf")
    if baseline_rate <= 0.0 or baseline_rate >= 1.0:
        return float("inf")

    # Максимально возможный MDE ограничен: не выходим за [0, 1]
    max_mde = min(1.0 - baseline_rate, baseline_rate, 0.5)
    if max_mde <= 1e-6:
        return float("inf")

    def n_for_mde(mde: float) -> int:
        try:
            return calculate_for_conversion(
                baseline_rate, mde, alpha, power
            ).sample_size_per_variant
        except Exception:
            return int(1e9)

    # Если даже max_mde не достижим при данной выборке
    if n_for_mde(max_mde) > sample_size_per_variant:
        return max_mde

    lo, hi = 1e-6, max_mde
    for _ in range(60):  # точность ~1e-18, более чем достаточно
        mid = (lo + hi) / 2
        if n_for_mde(mid) > sample_size_per_variant:
            lo = mid
        else:
            hi = mid

    return (lo + hi) / 2
