import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getUsers: vi.fn(),
  getRoles: vi.fn(),
  assignRole: vi.fn(),
  revokeRole: vi.fn(),
  updateUserActive: vi.fn(),
}))

import { getRoles, getUsers } from '../../api/client'
import UsersPage from '../UsersPage'
import { renderWithProviders } from '../../test/utils'

describe('UsersPage', () => {
  it('renders the empty state when there are no users', async () => {
    getUsers.mockResolvedValueOnce({
      data: { items: [], total: 0 },
    })
    getRoles.mockResolvedValueOnce({ data: { items: [] } })

    const { findByText } = renderWithProviders(<UsersPage />, {
      route: '/settings/users',
    })

    expect(await findByText(/no users yet|нет пользователей/i)).toBeInTheDocument()
  })

  it('renders user rows with their roles', async () => {
    getUsers.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 'u-1',
            username: 'alice',
            email: 'alice@example.com',
            is_active: true,
            roles: [
              { id: 'r-admin',   key: 'admin',  name: 'Administrator' },
              { id: 'r-editor',  key: 'editor', name: 'Editor' },
            ],
          },
          {
            id: 'u-2',
            username: 'bob',
            email: 'bob@example.com',
            is_active: true,
            roles: [{ id: 'r-viewer', key: 'viewer', name: 'Viewer' }],
          },
        ],
        total: 2,
      },
    })
    getRoles.mockResolvedValueOnce({
      data: {
        items: [
          { id: 'r-admin',  key: 'admin',  name: 'Administrator' },
          { id: 'r-editor', key: 'editor', name: 'Editor' },
          { id: 'r-viewer', key: 'viewer', name: 'Viewer' },
        ],
      },
    })

    const { findByText } = renderWithProviders(<UsersPage />, {
      route: '/settings/users',
    })

    expect(await findByText('alice')).toBeInTheDocument()
    expect(await findByText('alice@example.com')).toBeInTheDocument()
    expect(await findByText('bob@example.com')).toBeInTheDocument()
  })
})