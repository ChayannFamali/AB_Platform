import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
}))

import { getApiKeys } from '../../api/client'
import ApiKeysPage from '../ApiKeysPage'
import { renderWithProviders } from '../../test/utils'

describe('ApiKeysPage', () => {
  it('renders the empty state when no API keys exist', async () => {
    getApiKeys.mockResolvedValueOnce({ data: [] })

    const { findByText, findByLabelText } = renderWithProviders(
      <ApiKeysPage />,
      { route: '/api-keys' }
    )

    expect(
      await findByText('You have no API keys')
    ).toBeInTheDocument()
    expect(
      await findByLabelText(/name/i)
    ).toBeInTheDocument()
  })

  it('renders an existing API key in the list', async () => {
    getApiKeys.mockResolvedValueOnce({
      data: [
        {
          id: 'k-1',
          name: 'sdk-prod',
          key_preview: 'abp_a1b2c3d4***',
          scopes: ['assignments:read', 'events:write'],
          is_active: true,
          created_at: '2026-06-01T00:00:00Z',
          last_used_at: null,
        },
      ],
    })

    const { findByText } = renderWithProviders(<ApiKeysPage />, {
      route: '/api-keys',
    })

    expect(await findByText('sdk-prod')).toBeInTheDocument()
    expect(await findByText('abp_a1b2c3d4***')).toBeInTheDocument()
  })
})