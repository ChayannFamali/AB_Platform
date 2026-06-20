import { useTranslation } from 'react-i18next'

import { Badge } from '../ui/badge'

const LEVELS = [
  { max: 0.01, variant: 'success', labelKey: 'stats.significance.high' },
  { max: 0.05, variant: 'info',    labelKey: 'stats.significance.medium' },
  { max: 0.10, variant: 'warning', labelKey: 'stats.significance.low' },
  { max: Infinity, variant: 'outline', labelKey: 'stats.significance.none' },
]

function levelFor(pValue) {
  if (pValue == null) return LEVELS[LEVELS.length - 1]
  return LEVELS.find((l) => pValue < l.max)
}

export default function SignificanceBadge({ pValue, alpha = 0.05, className }) {
  const { t } = useTranslation()
  const lvl = levelFor(pValue)
  const display = pValue == null ? '—' : pValue.toFixed(3)
  const tooltip =
    pValue == null
      ? t('stats.significance.noTest')
      : t('stats.significance.tooltip', { pValue: display, alpha })

  return (
    <Badge variant={lvl.variant} className={className} title={tooltip}>
      <span className="font-mono">p = {display}</span>
      <span className="ml-1.5 text-[10px] uppercase opacity-80">
        {t(lvl.labelKey)}
      </span>
    </Badge>
  )
}