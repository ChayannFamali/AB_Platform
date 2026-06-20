import { describe, expect, it } from 'vitest'

import SettingsPage from '../SettingsPage'
import { renderWithProviders } from '../../test/utils'

describe('SettingsPage', () => {
  it('renders the page header', async () => {
    const { findByText } = renderWithProviders(<SettingsPage />, {
      route: '/settings',
    })
    // The header is rendered via PageHeader; both locales must be present
    // because PageHeader uses t('settings.title') and so does the nav link.
    expect(await findByText(/Settings|Настройки/i)).toBeInTheDocument()
  })

  it('exposes a language toggle', async () => {
    const { findByText } = renderWithProviders(<SettingsPage />, {
      route: '/settings',
    })
    expect(await findByText('English')).toBeInTheDocument()
    expect(await findByText('Русский')).toBeInTheDocument()
  })

  it('exposes a theme toggle', async () => {
    const { findByText } = renderWithProviders(<SettingsPage />, {
      route: '/settings',
    })
    // Either the light or dark label is shown depending on current theme.
    const labelRegex = /Dark mode|T\s*m mode|Light mode|Светлая|С\s*тная/i
    expect(await findByText(labelRegex)).toBeInTheDocument()
  })
})
