import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getSampleSizeConversion:  vi.fn(),
  getSampleSizeContinuous: vi.fn(),
}))

import SampleSizeCalculatorPage from '../SampleSizeCalculatorPage'
import { renderWithProviders } from '../../test/utils'

describe('SampleSizeCalculatorPage', () => {
  it('renders the page header and the calculator', async () => {
    const { findAllByText } = renderWithProviders(
      <SampleSizeCalculatorPage />,
      { route: '/tools/sample-size' },
    )
    // "Sample size" appears in the nav AND the page header.
    const titles = await findAllByText(/Sample size|Калькулятор/i)
    expect(titles.length).toBeGreaterThan(0)
    // Tab labels are unique on the page
    expect(await findAllByText(/Conversion|Конверсия/i)).toBeTruthy()
    expect(await findAllByText(/Continuous|Непрерывн/i)).toBeTruthy()
  })
})
