import { useTranslation } from 'react-i18next'

import { Card, CardContent } from '../ui/card'

export default function AchievedMDEBlock({ mde, relativeToMean }) {
  const { t } = useTranslation()
  if (mde == null) return null

  const pct = relativeToMean != null && relativeToMean > 0
    ? ((mde / relativeToMean) * 100).toFixed(1)
    : null

  return (
    <Card className="border-dashed">
      <CardContent className="space-y-1 px-4 py-3">
        <div className="text-xs font-medium uppercase text-muted-foreground">
          {t('stats.mde.title')}
        </div>
        <div className="font-mono text-lg">{mde.toFixed(4)}</div>
        {pct != null && (
          <div className="text-xs text-muted-foreground">
            {t('stats.mde.percentOfBaseline', { pct })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}