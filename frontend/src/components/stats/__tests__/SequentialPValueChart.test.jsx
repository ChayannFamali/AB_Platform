import { describe, expect, it } from 'vitest'
import SequentialPValueChart from '../SequentialPValueChart'
import { renderWithProviders } from '../../../test/utils'

describe('SequentialPValueChart', () => {
  it('renders nothing when snapshots are empty', () => {
    const { container } = renderWithProviders(
      <SequentialPValueChart snapshots={[]} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders the chart card when snapshots exist', async () => {
    const { container, findAllByText } = renderWithProviders(
      <SequentialPValueChart
        snapshots={[
          {
            snapshot_date: '2026-06-20',
            metric_name: 'clicks',
            variant_name: 'treatment',
            sequential_fpr: 0.03,
          },
          {
            snapshot_date: '2026-06-21',
            metric_name: 'clicks',
            variant_name: 'treatment',
            sequential_fpr: 0.02,
          },
        ]}
      />,
    )
    // ResponsiveContainer in jsdom can't measure its parent (no real layout),
    // so the inner <svg> doesn't render — but the surrounding Card and the
    // chart title do. Verify the wrapper rendered.
    expect(container.firstChild).not.toBeNull()
    const titles = await findAllByText(/Always-valid p-value|mSPRT/i)
    expect(titles.length).toBeGreaterThan(0)
  })
})