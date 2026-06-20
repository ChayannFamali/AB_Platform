import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getAuditLog: vi.fn(),
}))

import { getAuditLog } from '../../api/client'
import AuditLogPage from '../AuditLogPage'
import { renderWithProviders } from '../../test/utils'

describe('AuditLogPage', () => {
  it('renders the empty state when there are no audit entries', async () => {
    getAuditLog.mockResolvedValueOnce({
      data: { items: [], total: 0 },
    })

    const { findByText } = renderWithProviders(<AuditLogPage />, {
      route: '/settings/audit',
    })

    expect(
      await findByText(/no audit entries yet|записей пока нет/i)
    ).toBeInTheDocument()
  })

  it('renders rows for existing audit entries', async () => {
    getAuditLog.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 'a-1',
            user_id: 'u-1',
            user_username: 'audit-actor',
            action: 'create',
            resource_type: 'role',
            resource_id: 'r-1',
            details: { key: 'qa', name: 'QA' },
            ip_address: '127.0.0.1',
            user_agent: 'test',
            created_at: '2026-06-20T10:00:00Z',
          },
          {
            id: 'a-2',
            user_id: 'u-1',
            user_username: 'audit-actor',
            action: 'assign',
            resource_type: 'user_role',
            resource_id: 'u-2',
            details: { role_key: 'editor' },
            ip_address: null,
            user_agent: null,
            created_at: '2026-06-20T11:00:00Z',
          },
        ],
        total: 2,
        limit: 30,
        offset: 0,
        has_next: false,
        has_prev: false,
      },
    })

    const { findAllByText } = renderWithProviders(<AuditLogPage />, {
      route: '/settings/audit',
    })

    const actors = await findAllByText('audit-actor')
    expect(actors.length).toBeGreaterThan(0)
  })
})