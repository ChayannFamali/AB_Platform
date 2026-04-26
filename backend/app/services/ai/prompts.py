from dataclasses import dataclass


@dataclass
class MetricContext:
    experiment_name: str
    metric_name: str
    metric_type: str          # conversion / revenue / duration
    control_mean: float
    treatment_mean: float
    control_size: int
    treatment_size: int
    effect_size: float
    relative_lift: float | None
    p_value: float | None
    ci_low: float | None
    ci_high: float | None
    is_significant: bool | None
    is_winner: bool
    srm_detected: bool
    guardrail_violated: bool


def _format_value(value: float, metric_type: str) -> str:
    if metric_type == "conversion":
        return f"{value:.1%}"
    return f"{value:.2f}"


def build_result_prompt(ctx: MetricContext) -> str:
    """
    Структурированный промпт — работает даже с маленькими локальными моделями.
    Явно указываем что нужно и что нельзя делать.
    """
    fmt = lambda v: _format_value(v, ctx.metric_type)

    # Предупреждения
    warnings = []
    if ctx.srm_detected:
        warnings.append(" ВАЖНО: Обнаружен Sample Ratio Mismatch (SRM) — "
                        "соотношение пользователей отклонилось от ожидаемого. "
                        "Результаты могут быть ненадёжны из-за технической проблемы.")
    if ctx.guardrail_violated:
        warnings.append(" ВАЖНО: Нарушена guardrail метрика — "
                        "вспомогательный показатель ухудшился значимо.")

    warning_block = "\n".join(warnings) if warnings else "Технических проблем не обнаружено."

    # Значимость
    if ctx.is_significant is None:
        significance = "Недостаточно данных для статистического вывода."
    elif ctx.is_significant:
        significance = f"Результат статистически значим (p={ctx.p_value:.3f} < 0.05)."
    else:
        p_str = f"p={ctx.p_value:.3f}" if ctx.p_value is not None else "p=н/д"
        significance = f"Результат статистически НЕ значим ({p_str} ≥ 0.05) — разница может быть случайной."

    # Доверительный интервал
    if ctx.ci_low is not None and ctx.ci_high is not None:
        ci_block = f"95% доверительный интервал изменения: [{fmt(ctx.ci_low)}, {fmt(ctx.ci_high)}]"
    else:
        ci_block = ""

    # Итог
    if ctx.is_winner:
        conclusion = "ВЫВОД: Treatment вариант победил. Рекомендуется деплой."
    elif ctx.srm_detected:
        conclusion = "ВЫВОД: Результатам нельзя доверять до исправления SRM. Нужна диагностика SDK."
    elif ctx.guardrail_violated:
        conclusion = "ВЫВОД: Деплой не рекомендуется — нарушена guardrail метрика."
    elif ctx.is_significant is False:
        conclusion = "ВЫВОД: Разница не доказана. Продолжайте сбор данных или пересмотрите гипотезу."
    else:
        conclusion = "ВЫВОД: Недостаточно данных. Дождитесь запланированного окончания эксперимента."

    prompt = f"""Ты аналитик A/B тестов. Объясни результаты эксперимента простым языком на русском.
Пиши 3-4 предложения. Избегай статистического жаргона. Не придумывай информацию которой нет в данных.

ДАННЫЕ ЭКСПЕРИМЕНТА:
Название: {ctx.experiment_name}
Метрика: {ctx.metric_name} (тип: {ctx.metric_type})

Control  ({ctx.control_size} пользователей):   {fmt(ctx.control_mean)}
Treatment ({ctx.treatment_size} пользователей): {fmt(ctx.treatment_mean)}

Изменение: {ctx.effect_size:+.4f} ({f'{ctx.relative_lift:+.1f}%' if ctx.relative_lift is not None else 'н/д'})
{ci_block}
{significance}

Статус: {warning_block}
{conclusion}

Интерпретация для команды:"""

    return prompt


def build_srm_diagnosis_prompt(
    experiment_name: str,
    expected_split: dict[str, float],
    observed_split: dict[str, int],
    srm_p_value: float,
) -> str:
    """Промпт для диагностики причин SRM."""
    lines = []
    for variant, count in observed_split.items():
        expected = expected_split.get(variant, 0)
        lines.append(f"  {variant}: ожидалось {expected:.0f}%, получено {count} пользователей")

    return f"""Обнаружен Sample Ratio Mismatch в эксперименте "{experiment_name}".
p-value = {srm_p_value:.4f} (< 0.01 означает проблему).

Соотношение вариантов:
{chr(10).join(lines)}

Перечисли 3-4 наиболее вероятные технические причины этой проблемы
и что нужно проверить в коде SDK и assignment логике. Отвечай на русском.

Возможные причины:"""
