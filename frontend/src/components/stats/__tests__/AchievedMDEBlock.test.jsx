import { describe, expect, it } from 'vitest'
import AchievedMDEBlock from '../AchievedMDEBlock'
import { renderWithProviders } from '../../../test/utils'

describe('AchievedMDEBlock', () => {
  it('renders the MDE value formatted to 4 decimals', () => {
    const { getByText } = renderWithProviders(
      <AchievedMDEBlock mde={0.0123} relativeToMean={0.10} />,
    )
    expect(getByText('0.0123')).toBeInTheDocument()
  })

  it('renders nothing when mde is null', () => {
    const { container } = renderWithProviders(
      <AchievedMDEBlock mde={null} relativeToMean={0.10} />,
    )
    expect(container.firstChild).toBeNull()
  })
})