import { describe, expect, it } from 'vitest'
import CIBar from '../CIBar'
import { renderWithProviders } from '../../../test/utils'

describe('CIBar', () => {
  it('renders an SVG when CI bounds + estimate are provided', () => {
    const { container } = renderWithProviders(
      <CIBar ciLow={0.03} ciHigh={0.05} estimate={0.04} />,
    )
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg.getAttribute('aria-label')).toBe('confidence interval')
  })

  it('renders nothing when bounds are missing', () => {
    const { container } = renderWithProviders(
      <CIBar ciLow={null} ciHigh={0.05} estimate={0.04} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when CI high <= low', () => {
    const { container } = renderWithProviders(
      <CIBar ciLow={0.05} ciHigh={0.05} estimate={0.05} />,
    )
    expect(container.firstChild).toBeNull()
  })
})