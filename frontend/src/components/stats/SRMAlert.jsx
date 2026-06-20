import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '../ui/alert'

export default function SRMAlert({ pValue }) {
  const { t } = useTranslation()
  if (pValue == null) return null
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>{t('stats.srm.title')}</AlertTitle>
      <AlertDescription>
        {t('stats.srm.description', { pValue: pValue.toFixed(4) })}
      </AlertDescription>
    </Alert>
  )
}