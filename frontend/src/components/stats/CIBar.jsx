/**
 * Horizontal error-bar visualization for a single 95% CI.
 *
 * Renders an inline SVG so we don't pull in a charting library for a
 * 100-px widget. The bar is centered on the point estimate; ticks mark
 * the lower / upper bounds.
 */
export default function CIBar({
  ciLow,
  ciHigh,
  estimate,
  width = 160,
  height = 24,
  className,
}) {
  if (ciLow == null || ciHigh == null || estimate == null) return null
  if (ciHigh <= ciLow) return null

  // Expand domain to include the estimate (in case it's outside the CI
  // for one-sided cases) with 10% padding on each side.
  const minVal = Math.min(ciLow, estimate)
  const maxVal = Math.max(ciHigh, estimate)
  const span = Math.max(maxVal - minVal, 1e-9)
  const pad = span * 0.1
  const domainMin = minVal - pad
  const domainMax = maxVal + pad
  const domainSpan = domainMax - domainMin

  const xOf = (v) => ((v - domainMin) / domainSpan) * width
  const xLow = xOf(ciLow)
  const xHigh = xOf(ciHigh)
  const xEst = xOf(estimate)
  const yMid = height / 2

  return (
    <svg
      width={width}
      height={height}
      className={className}
      role="img"
      aria-label="confidence interval"
    >
      <line
        x1={xLow}
        x2={xHigh}
        y1={yMid}
        y2={yMid}
        stroke="currentColor"
        strokeWidth="2"
        className="text-muted-foreground"
      />
      <line
        x1={xLow}
        x2={xLow}
        y1={yMid - 4}
        y2={yMid + 4}
        stroke="currentColor"
        strokeWidth="2"
        className="text-muted-foreground"
      />
      <line
        x1={xHigh}
        x2={xHigh}
        y1={yMid - 4}
        y2={yMid + 4}
        stroke="currentColor"
        strokeWidth="2"
        className="text-muted-foreground"
      />
      <circle
        cx={xEst}
        cy={yMid}
        r={3}
        className="fill-foreground"
      />
    </svg>
  )
}