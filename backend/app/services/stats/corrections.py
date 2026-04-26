import numpy as np


def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """
    Коррекция Benjamini-Hochberg на множественные сравнения.

    Проблема без коррекции:
        1 метрика  → 5% false positive
        10 метрик  → ~40% шанс хотя бы одного ложного позитива

    BH контролирует False Discovery Rate (FDR) — менее консервативна
    чем Bonferroni, лучше подходит для A/B тестов.

    Возвращает список bool: True = значимо после коррекции.
    """
    n = len(p_values)
    if n == 0:
        return []
    if n == 1:
        return [p_values[0] < alpha]

    arr = np.array(p_values)
    sorted_indices = np.argsort(arr)
    sorted_p = arr[sorted_indices]

    # BH threshold: p(k) <= (k/n) * alpha
    thresholds = (np.arange(1, n + 1) / n) * alpha
    below = sorted_p <= thresholds

    # Всё до последнего значимого — тоже значимо
    if below.any():
        last = int(np.where(below)[0][-1])
        below[:last + 1] = True

    # Возвращаем в исходном порядке
    result = np.zeros(n, dtype=bool)
    result[sorted_indices] = below
    return result.tolist()
