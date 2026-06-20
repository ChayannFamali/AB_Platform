import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useUiStore } from '../stores/uiStore'

import '../i18n'

export default function I18nProvider({ children }) {
  const locale = useUiStore((s) => s.locale)
  const { i18n } = useTranslation()

  useEffect(() => {
    if (i18n.language !== locale) {
      i18n.changeLanguage(locale)
    }
  }, [locale, i18n])

  return children
}