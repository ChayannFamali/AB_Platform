"""
Rule-based insights engine.

Produces human-readable insights from analysis output. No AI — pure rules.
Each rule fires when its preconditions are met and emits one Insight record
the frontend can render (and translate via i18n keys).

Rule catalog:
  - SRM detected               → ERROR
  - Guardrail violation        → ERROR
  - Clear winner               → SUCCESS   (p<0.01 AND |lift|>2% AND positive effect)
  - Likely winner              → SUCCESS   (significant AND positive effect)
  - Underpowered               → WARNING   (not significant AND MDE > 50% of mean)
  - No significant effect yet  → INFO
  - Sequential boundary crossed→ INFO      (sequential experiments only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services.stats.engine import MetricAnalysis


class InsightSeverity(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


@dataclass
class Insight:
    """
    A single rule-based finding.

    `title` and `description` are i18n keys; `params` provides values for
    interpolation on the frontend. The frontend falls back to English when
    keys are missing.
    """
    type: str
    severity: InsightSeverity
    title: str
    description: str
    metric_id: str | None = None
    variant_id: str | None = None
    params: dict = field(default_factory=dict)


def interpret(
    metric_results: list[MetricAnalysis],
    alpha: float = 0.05,
    is_sequential: bool = False,
) -> list[Insight]:
    """
    Apply rule-based interpretation across all metric results.

    Returns a flat list of insights. The same rule can fire multiple times
    across (metric, variant) pairs — the frontend groups them by severity.
    """
    insights: list[Insight] = []

    # Experiment-wide signals (emit once per experiment)
    srm_emitted = False
    guardrail_violated_any = any(
        m.guardrail_violated for m in metric_results
    )
    if guardrail_violated_any:
        insights.append(Insight(
            type="guardrail_violated",
            severity=InsightSeverity.ERROR,
            title="stats.insights.guardrailViolated.title",
            description="stats.insights.guardrailViolated.description",
        ))

    for metric in metric_results:
        # SRM applies to the experiment as a whole — emit once
        if metric.srm.srm_detected and not srm_emitted:
            insights.append(Insight(
                type="srm_detected",
                severity=InsightSeverity.ERROR,
                title="stats.insights.srm.title",
                description="stats.insights.srm.description",
                params={"p_value": metric.srm.p_value},
            ))
            srm_emitted = True

        control_va = next(
            (v for v in metric.variants if v.variant_name == "control"),
            None,
        )

        for va in metric.variants:
            if va.variant_name == "control" or control_va is None:
                continue

            # Sequential boundary crossing — always-valid p-value < α
            if is_sequential and va.sequential_boundary_crossed:
                insights.append(Insight(
                    type="sequential_boundary_crossed",
                    severity=InsightSeverity.INFO,
                    title="stats.insights.sequentialBoundary.title",
                    description="stats.insights.sequentialBoundary.description",
                    metric_id=str(metric.metric_id),
                    variant_id=str(va.variant_id),
                    params={"sequential_fpr": va.sequential_fpr},
                ))

            if va.p_value is None:
                # No test ran (insufficient data) — skip
                continue

            positive_effect = (
                va.effect_size is not None and va.effect_size > 0
            )

            # Clear winner — strong signal, large effect, no guardrail block
            if (
                va.is_significant
                and va.p_value < 0.01
                and va.relative_lift is not None
                and abs(va.relative_lift) > 2.0
                and positive_effect
                and not guardrail_violated_any
            ):
                insights.append(Insight(
                    type="clear_winner",
                    severity=InsightSeverity.SUCCESS,
                    title="stats.insights.clearWinner.title",
                    description="stats.insights.clearWinner.description",
                    metric_id=str(metric.metric_id),
                    variant_id=str(va.variant_id),
                    params={
                        "lift": va.relative_lift,
                        "p_value": va.p_value,
                    },
                ))

            # Likely winner — significant, positive, but weaker signal
            elif va.is_significant and positive_effect and not guardrail_violated_any:
                insights.append(Insight(
                    type="likely_winner",
                    severity=InsightSeverity.SUCCESS,
                    title="stats.insights.likelyWinner.title",
                    description="stats.insights.likelyWinner.description",
                    metric_id=str(metric.metric_id),
                    variant_id=str(va.variant_id),
                ))

            # Underpowered — test didn't reject AND we can't detect
            # reasonably small effects. Heuristic: achieved_mde > 50%
            # of the baseline mean means we cannot detect effects
            # smaller than 50% of the baseline (very low sensitivity).
            elif (
                not va.is_significant
                and va.achieved_mde is not None
                and control_va.mean > 0
                and va.achieved_mde > 0.5 * control_va.mean
            ):
                insights.append(Insight(
                    type="underpowered",
                    severity=InsightSeverity.WARNING,
                    title="stats.insights.underpowered.title",
                    description="stats.insights.underpowered.description",
                    metric_id=str(metric.metric_id),
                    variant_id=str(va.variant_id),
                    params={"achieved_mde": va.achieved_mde},
                ))

            # No significance yet — but test has some sensitivity
            elif not va.is_significant:
                insights.append(Insight(
                    type="no_significance",
                    severity=InsightSeverity.INFO,
                    title="stats.insights.noSignificance.title",
                    description="stats.insights.noSignificance.description",
                    metric_id=str(metric.metric_id),
                    variant_id=str(va.variant_id),
                    params={"p_value": va.p_value},
                ))

    return insights