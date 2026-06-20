import { ClipboardList } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import EmptyState from '../EmptyState'

/**
 * Placeholder for the decision log (populated in M-012).
 *
 * Until then, shows an empty state so the tab is navigable and the user
 * can see what's coming. No backend calls — no data to fetch yet.
 */
export default function DecisionLogTab() {
  const { t } = useTranslation()
  return (
    <EmptyState
      icon={ClipboardList}
      title={t('decisions.empty')}
      description={t('decisions.comingSoon')}
    />
  )
}
