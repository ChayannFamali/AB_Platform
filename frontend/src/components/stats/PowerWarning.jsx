import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '../ui/alert'

export default function PowerWarning({ achievedMde, baselineMean }) {
  const { t } = useTranslation()
  if (achievedMde == null || baselineMean == null) return null
  // Only show when MDE > 50% of baseline — i.e. test cannot detect effects
  // smaller than 50% of the current value (clearly underpowered).
  if (baselineMean <= 0 || achievedMde <= 0.5 * baselineMean) return null

  return (
    <Alert variant="warning">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>{t('stats.power.title')}</AlertTitle>
      <AlertDescription>
        {t('stats.power.description', {
          mde: achievedMde.toFixed(4),
          ratio: ((achievedMde / baselineMean) * 100).toFixed(0),
        })}
      </AlertDescription>
    </Alert>
  )
}