import { useTranslation } from 'react-i18next'

/**
 * Rollout slider with a numeric display. Pure controlled component —
 * the parent owns the value and persists it.
 *
 * Uses `key={value}` so React resets the native input's internal drag
 * state when the parent commits a new value. The native browser still
 * handles visual drag feedback while the user moves the thumb; we only
 * call `onChange` once per release (mouseup / touchend / keyup).
 */
export default function RolloutSlider({
  value,
  onChange,
  disabled = false,
  testId = 'rollout-slider',
}) {
  const { t } = useTranslation()
  const display = value ?? 0

  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        defaultValue={display}
        key={display}
        disabled={disabled}
        onMouseUp={(e) => onChange?.(Number(e.currentTarget.value))}
        onTouchEnd={(e) => onChange?.(Number(e.currentTarget.value))}
        onKeyUp={(e) => onChange?.(Number(e.currentTarget.value))}
        data-testid={testId}
        className="h-2 flex-1 cursor-pointer appearance-none rounded bg-muted disabled:opacity-50"
        aria-label={t('flags.rollout')}
      />
      <span className="w-12 text-right font-mono text-sm tabular-nums">
        {display}%
      </span>
    </div>
  )
}