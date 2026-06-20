import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getExperiments: vi.fn(),
  updateStatus: vi.fn(),
  deleteExperiment: vi.fn(),
}))

import { getExperiments } from '../../api/client'
import ExperimentList from '../ExperimentList'
import { renderWithProviders } from '../../test/utils'

describe('ExperimentList', () => {
  it('renders the empty state when there are no experiments', async () => {
    getExperiments.mockResolvedValueOnce({
      data: { items: [], total: 0 },
    })

    const { findByText } = renderWithProviders(<ExperimentList />, {
      route: '/',
    })

    expect(
      await findByText(/No experiments yet/i)
    ).toBeInTheDocument()
  })

  it('renders experiment rows when data is present', async () => {
    getExperiments.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 'exp-1',
            name: 'Homepage button',
            status: 'running',
            traffic_percentage: 100,
            created_at: '2026-06-01T00:00:00Z',
          },
          {
            id: 'exp-2',
            name: 'Checkout flow',
            status: 'draft',
            traffic_percentage: 50,
            created_at: '2026-06-02T00:00:00Z',
          },
        ],
        total: 2,
      },
    })

    const { findByText } = renderWithProviders(<ExperimentList />, {
      route: '/',
    })

    expect(await findByText('Homepage button')).toBeInTheDocument()
    expect(await findByText('Checkout flow')).toBeInTheDocument()
  })
})