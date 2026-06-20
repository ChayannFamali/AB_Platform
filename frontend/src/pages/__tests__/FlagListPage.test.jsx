import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('../../api/client', () => ({
  getFlags: vi.fn(),
  createFlag: vi.fn(),
  deleteFlag: vi.fn(),
  getFlagSummary: vi.fn(),
}))

import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../../test/utils'
import FlagListPage from '../FlagListPage'
import * as api from '../../api/client'

describe('FlagListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton then empty state', async () => {
    api.getFlags.mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
      has_next: false,
      has_prev: false,
      summary: {
        total: 0,
        enabled_total: 0,
        enabled_with_rollout: 0,
        disabled_total: 0,
      },
    })
    api.getFlagSummary.mockResolvedValue({
      total: 0, enabled_total: 0, enabled_with_rollout: 0, disabled_total: 0,
    })

    renderWithProviders(<FlagListPage />)

    await waitFor(() => {
      expect(api.getFlags).toHaveBeenCalled()
    })
    expect(await screen.findByText(/No feature flags yet/i)).toBeInTheDocument()
  })

  it('renders flag rows from the API response', async () => {
    api.getFlags.mockResolvedValue({
      items: [
        {
          id: 'flag-1',
          key: 'new_checkout',
          name: 'New Checkout',
          description: null,
          enabled: true,
          rollout_percentage: 50,
          created_at: '2026-06-22T00:00:00Z',
          updated_at: '2026-06-22T00:00:00Z',
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
      has_next: false,
      has_prev: false,
      summary: {
        total: 1,
        enabled_total: 1,
        enabled_with_rollout: 1,
        disabled_total: 0,
      },
    })
    api.getFlagSummary.mockResolvedValue({
      total: 1, enabled_total: 1, enabled_with_rollout: 1, disabled_total: 0,
    })

    renderWithProviders(<FlagListPage />)

    await waitFor(() => {
      expect(screen.getByText('New Checkout')).toBeInTheDocument()
    })
    expect(screen.getByText('new_checkout')).toBeInTheDocument()
    expect(screen.getByText('Live')).toBeInTheDocument()
  })

  it('renders summary stats', async () => {
    api.getFlags.mockResolvedValue({
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
      has_next: false,
      has_prev: false,
      summary: {
        total: 5,
        enabled_total: 3,
        enabled_with_rollout: 2,
        disabled_total: 2,
      },
    })
    api.getFlagSummary.mockResolvedValue({
      total: 5, enabled_total: 3, enabled_with_rollout: 2, disabled_total: 2,
    })

    renderWithProviders(<FlagListPage />)

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument()
    })
  })
})