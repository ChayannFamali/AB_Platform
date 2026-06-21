import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import { renderWithProviders } from '../../../test/utils'
import DecisionLogTab from '../DecisionLogTab'

// Mock the api client module so we don't hit the real network.
vi.mock('../../../api/client', () => ({
  getDecisions: vi.fn().mockResolvedValue({
    items: [], total: 0, limit: 100, offset: 0, has_next: false, has_prev: false,
  }),
  addDecision:  vi.fn().mockResolvedValue({}),
}))

vi.mock('../../../stores/authStore', () => ({
  useAuthStore: vi.fn((selector) =>
    selector({
      user: {
        permissions: ['decisions:write', 'results:read'],
      },
    })
  ),
}))

describe('DecisionLogTab', () => {
  it('shows the empty state when no decisions are recorded', async () => {
    renderWithProviders(<DecisionLogTab experimentId="exp-1" />)
    await waitFor(() =>
      expect(screen.getByText(/No decisions yet/i)).toBeInTheDocument()
    )
  })

  it('shows the "Record decision" button when the user has decisions:write', async () => {
    renderWithProviders(<DecisionLogTab experimentId="exp-1" />)
    await waitFor(() =>
      expect(screen.getByText(/Record decision/i)).toBeInTheDocument()
    )
  })
})

describe('DecisionLogTab without decisions:write', () => {
  it('hides the form button for analysts/viewers', async () => {
    // Re-mock the auth store for this subset.
    const { useAuthStore } = await import('../../../stores/authStore')
    useAuthStore.mockImplementation((selector) =>
      selector({
        user: {
          permissions: ['results:read'],  // no decisions:write
        },
      })
    )

    renderWithProviders(<DecisionLogTab experimentId="exp-1" />)
    await waitFor(() =>
      expect(screen.getByText(/No decisions yet/i)).toBeInTheDocument()
    )
    expect(screen.queryByText(/Record decision/i)).not.toBeInTheDocument()
  })
})