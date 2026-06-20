import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getExperiments: vi.fn(),
  getAuditLog:    vi.fn(),
}))

import { getAuditLog, getExperiments } from '../../api/client'
import DashboardPage from '../DashboardPage'
import { renderWithProviders } from '../../test/utils'

describe('DashboardPage', () => {
  it('renders summary cards with experiment counts', async () => {
    getExperiments.mockResolvedValueOnce({
      data: {
        items: [
          { id: '1', name: 'A', status: 'running' },
          { id: '2', name: 'B', status: 'running' },
          { id: '3', name: 'C', status: 'completed' },
          { id: '4', name: 'D', status: 'draft' },
        ],
        total: 4,
      },
    })
    getAuditLog.mockResolvedValueOnce({ data: { items: [], total: 0 } })

    const { findByText, findAllByText } = renderWithProviders(
      <DashboardPage />,
      { route: '/' },
    )

    // 2 running, 1 completed, 4 total
    const runningCards = await findAllByText('2')
    expect(runningCards.length).toBeGreaterThan(0)
    expect(await findByText('4')).toBeInTheDocument()
  })

  it('renders recent audit activity', async () => {
    getExperiments.mockResolvedValueOnce({ data: { items: [], total: 0 } })
    getAuditLog.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 'a-1',
            user_id: 'u-1',
            user_username: 'dashboard-actor',
            action: 'create',
            resource_type: 'role',
            resource_id: 'r-1',
            details: null,
            created_at: '2026-06-20T10:00:00Z',
          },
        ],
        total: 1,
      },
    })

    const { findByText } = renderWithProviders(<DashboardPage />, {
      route: '/',
    })

    expect(await findByText('dashboard-actor')).toBeInTheDocument()
  })
})
