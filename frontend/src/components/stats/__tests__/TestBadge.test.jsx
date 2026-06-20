import { describe, expect, it } from 'vitest'
import TestBadge from '../TestBadge'
import { renderWithProviders } from '../../../test/utils'

describe('TestBadge', () => {
  it('renders a localized label for known test ids', () => {
    const { getByText } = renderWithProviders(<TestBadge testUsed="z_test" />)
    // i18n key 'stats.test.zTest' resolves to "Z-test" / "Z-тест"
    expect(getByText(/Z-test|Z-тест/i)).toBeInTheDocument()
  })

  it('renders nothing when testUsed is null', () => {
    const { container } = renderWithProviders(<TestBadge testUsed={null} />)
    expect(container.firstChild).toBeNull()
  })
})