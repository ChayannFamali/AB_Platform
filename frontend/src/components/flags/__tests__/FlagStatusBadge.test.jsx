import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import FlagStatusBadge from '../FlagStatusBadge'
import { renderWithProviders } from '../../../test/utils'

describe('FlagStatusBadge', () => {
  it('shows "Off" when the flag is disabled', () => {
    renderWithProviders(
      <FlagStatusBadge flag={{ enabled: false, rollout_percentage: 50 }} />,
    )
    expect(screen.getByText(/^Off$/)).toBeInTheDocument()
  })

  it('shows "Live" when enabled with rollout > 0', () => {
    renderWithProviders(
      <FlagStatusBadge flag={{ enabled: true, rollout_percentage: 25 }} />,
    )
    expect(screen.getByText(/^Live$/)).toBeInTheDocument()
  })

  it('shows "Ready" when enabled but rollout is 0', () => {
    renderWithProviders(
      <FlagStatusBadge flag={{ enabled: true, rollout_percentage: 0 }} />,
    )
    expect(screen.getByText(/^Ready$/)).toBeInTheDocument()
  })
})