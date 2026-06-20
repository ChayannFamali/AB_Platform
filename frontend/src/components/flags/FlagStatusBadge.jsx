import { useTranslation } from 'react-i18next'

import { Badge } from '../ui/badge'

/**
 * Visual indicator for a flag's runtime state:
 *   - "off"   → kill switch engaged
 *   - "live"  → enabled, rollout > 0
 *   - "ready" → enabled, rollout = 0 (waiting to be turned up)
 */
export default function FlagStatusBadge({ flag }) {
  const { t } = useTranslation()

  if (!flag.enabled) {
    return <Badge variant="destructive">{t('flags.statusOff')}</Badge>
  }
  if (flag.rollout_percentage > 0) {
    return <Badge variant="success">{t('flags.statusLive')}</Badge>
  }
  return <Badge variant="secondary">{t('flags.statusReady')}</Badge>
}