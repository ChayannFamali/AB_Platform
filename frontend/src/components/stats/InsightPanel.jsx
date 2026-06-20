import { useTranslation } from 'react-i18next'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
} from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'

const SEVERITY_STYLES = {
  success: {
    icon: CheckCircle2,
    iconClass: 'text-emerald-600',
    borderClass: 'border-emerald-200',
  },
  warning: {
    icon: AlertTriangle,
    iconClass: 'text-amber-600',
    borderClass: 'border-amber-200',
  },
  error: {
    icon: AlertCircle,
    iconClass: 'text-red-600',
    borderClass: 'border-red-200',
  },
  info: {
    icon: Info,
    iconClass: 'text-sky-600',
    borderClass: 'border-sky-200',
  },
}

function InsightRow({ insight }) {
  const { t } = useTranslation()
  const style = SEVERITY_STYLES[insight.severity] ?? SEVERITY_STYLES.info
  const Icon = style.icon

  // `title` and `description` are i18n keys; `params` interpolates values.
  // When keys are missing, the t() call falls back to the key string —
  // harmless because the backend always emits the canonical keys.
  const title = t(insight.title, insight.params ?? {})
  const description = t(insight.description, insight.params ?? {})

  return (
    <div
      className={`flex items-start gap-3 rounded-md border ${style.borderClass} bg-card p-3`}
      data-severity={insight.severity}
      data-insight-type={insight.type}
    >
      <Icon className={`mt-0.5 h-4 w-4 flex-shrink-0 ${style.iconClass}`} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium leading-tight">{title}</div>
        <div className="mt-1 text-xs text-muted-foreground">
          {description}
        </div>
      </div>
    </div>
  )
}

export default function InsightPanel({ insights }) {
  const { t } = useTranslation()
  if (!insights || insights.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {t('stats.insights.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {insights.map((ins, i) => (
          <InsightRow key={`${ins.type}-${i}`} insight={ins} />
        ))}
      </CardContent>
    </Card>
  )
}