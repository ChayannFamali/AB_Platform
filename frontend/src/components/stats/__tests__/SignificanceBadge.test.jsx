import { describe, expect, it } from 'vitest'
import SignificanceBadge from '../SignificanceBadge'
import { renderWithProviders } from '../../../test/utils'

describe('SignificanceBadge', () => {
  it('renders high significance when p<0.01', () => {
    const { getByText } = renderWithProviders(<SignificanceBadge pValue={0.005} />)
    // p-value displayed with 3 decimals
    expect(getByText(/p = 0\.005/)).toBeInTheDocument()
  })

  it('renders placeholder when p-value is null', () => {
    const { container } = renderWithProviders(<SignificanceBadge pValue={null} />)
    expect(container.textContent).toContain('—')
  })
})