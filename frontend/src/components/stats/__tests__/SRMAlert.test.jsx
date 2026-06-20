import { describe, expect, it } from 'vitest'
import SRMAlert from '../SRMAlert'
import { renderWithProviders } from '../../../test/utils'

describe('SRMAlert', () => {
  it('renders the alert when SRM p-value provided', async () => {
    const { findAllByText } = renderWithProviders(<SRMAlert pValue={0.001} />)
    // The "Sample Ratio" phrase appears in both title and description —
    // use findAllByText and assert at least one match.
    const matches = await findAllByText(/Sample ratio|SRM detected/i)
    expect(matches.length).toBeGreaterThan(0)
  })

  it('renders nothing when p-value is null', () => {
    const { container } = renderWithProviders(<SRMAlert pValue={null} />)
    expect(container.firstChild).toBeNull()
  })
})