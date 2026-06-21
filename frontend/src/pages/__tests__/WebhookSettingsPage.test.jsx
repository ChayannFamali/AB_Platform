import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'

import { renderWithProviders } from '../../test/utils'
import WebhookSettingsPage from '../WebhookSettingsPage'

vi.mock('../../api/client', () => ({
  getWebhooks: vi.fn().mockResolvedValue({
    items: [], total: 0, limit: 100, offset: 0, has_next: false, has_prev: false,
  }),
  createWebhook: vi.fn(),
  updateWebhook: vi.fn(),
  deleteWebhook: vi.fn(),
  testWebhook:   vi.fn(),
  getWebhookDeliveries: vi.fn().mockResolvedValue({
    items: [], total: 0, limit: 50, offset: 0, has_next: false, has_prev: false,
  }),
}))

describe('WebhookSettingsPage', () => {
  it('shows the empty state when no webhooks exist', async () => {
    renderWithProviders(<WebhookSettingsPage />)
    await waitFor(() =>
      expect(screen.getByText(/No webhooks yet/i)).toBeInTheDocument()
    )
  })

  it('shows the "New webhook" button', async () => {
    renderWithProviders(<WebhookSettingsPage />)
    await waitFor(() =>
      expect(screen.getByText(/New webhook/i)).toBeInTheDocument()
    )
  })
})