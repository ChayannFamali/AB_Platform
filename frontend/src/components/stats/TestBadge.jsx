import { useTranslation } from 'react-i18next'

import { Badge } from '../ui/badge'

const LABELS = {
  z_test:       'stats.test.zTest',
  welch_t_test: 'stats.test.welchT',
  mann_whitney: 'stats.test.mannWhitney',
  delta_method: 'stats.test.deltaMethod',
}

export default function TestBadge({ testUsed, className }) {
  const { t } = useTranslation()
  if (!testUsed) return null
  const labelKey = LABELS[testUsed] ?? null
  const display = labelKey ? t(labelKey) : testUsed
  return (
    <Badge variant="outline" className={className} title={testUsed}>
      {display}
    </Badge>
  )
}