import { describe, expect, it } from 'vitest'
import PowerWarning from '../PowerWarning'
import { renderWithProviders } from '../../../test/utils'

describe('PowerWarning', () => {
  it('renders when MDE > 50% of baseline (clearly underpowered)', () => {
    const { container } = renderWithProviders(
      <PowerWarning achievedMde={0.06} baselineMean={0.10} />,
    )
    expect(container.firstChild).not.toBeNull()
    expect(container.textContent).toMatch(/power|MDE/i)
  })

  it('renders nothing when MDE <= 50% of baseline (test has sensitivity)', () => {
    const { container } = renderWithProviders(
      <PowerWarning achievedMde={0.01} baselineMean={0.10} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when inputs are null', () => {
    const { container } = renderWithProviders(
      <PowerWarning achievedMde={null} baselineMean={0.10} />,
    )
    expect(container.firstChild).toBeNull()
  })
})