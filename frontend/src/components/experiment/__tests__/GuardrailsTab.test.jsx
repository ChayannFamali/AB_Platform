import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import { renderWithProviders } from '../../../test/utils'
import GuardrailsTab from '../GuardrailsTab'

// Mock the api client module so we don't hit the real network.
vi.mock('../../../api/client', () => ({
  getGuardrails: vi.fn().mockResolvedValue({
    items: [], total: 0, limit: 100, offset: 0, has_next: false, has_prev: false,
  }),
  createGuardrail: vi.fn(),
  updateGuardrail: vi.fn(),
  deleteGuardrail: vi.fn(),
}))

const expWithGuardrailMetrics = {
  id: 'exp-1',
  metrics: [
    { id: 'm-1', name: 'Page Load', is_guardrail: true },
    { id: 'm-2', name: 'Conversion', is_guardrail: false },
  ],
}

const expWithoutGuardrailMetrics = {
  id: 'exp-2',
  metrics: [{ id: 'm-3', name: 'Conversion', is_guardrail: false }],
}

describe('GuardrailsTab', () => {
  it('shows the no-guardrail-metrics hint when none are marked', () => {
    renderWithProviders(<GuardrailsTab experiment={expWithoutGuardrailMetrics} />)
    expect(
      screen.getByText(/Mark a metric as guardrail/i),
    ).toBeInTheDocument()
  })

  it('renders empty state when there are guardrail metrics but no configs', async () => {
    renderWithProviders(<GuardrailsTab experiment={expWithGuardrailMetrics} />)
    await waitFor(() =>
      expect(screen.getByText(/No guardrails yet/i)).toBeInTheDocument(),
    )
  })

  it('renders the "Add guardrail" button when guardrail metrics exist', () => {
    renderWithProviders(<GuardrailsTab experiment={expWithGuardrailMetrics} />)
    expect(screen.getByText(/Add guardrail/i)).toBeInTheDocument()
  })
})
