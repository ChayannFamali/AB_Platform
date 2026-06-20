import { describe, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/client', () => ({
  login: vi.fn(),
}))

import { login } from '../../api/client'
import LoginPage from '../LoginPage'
import { renderWithProviders } from '../../test/utils'

describe('LoginPage', () => {
  it('renders email and password fields and a submit button', () => {
    const { getByLabelText, getByRole } = renderWithProviders(<LoginPage />, {
      route: '/login',
    })
    expect(getByLabelText(/email/i)).toBeInTheDocument()
    expect(getByLabelText(/password/i)).toBeInTheDocument()
    expect(
      getByRole('button', { name: 'Sign in' })
    ).toBeInTheDocument()
  })

  it('calls login and stores token on successful submit', async () => {
    login.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-abc',
        user: { username: 'alice', email: 'alice@example.com', roles: ['admin'] },
      },
    })

    const { getByLabelText, getByRole } = renderWithProviders(<LoginPage />, {
      route: '/login',
    })

    await userEvent.type(getByLabelText(/email/i), 'alice@example.com')
    await userEvent.type(getByLabelText(/password/i), 'secret-password')
    await userEvent.click(getByRole('button', { name: 'Sign in' }))

    expect(login).toHaveBeenCalledWith({
      email: 'alice@example.com',
      password: 'secret-password',
    })
  })

  it('surfaces an error message when login fails', async () => {
    login.mockRejectedValueOnce({
      response: { data: { detail: 'Invalid credentials' } },
    })

    const { getByLabelText, getByRole, findByText } = renderWithProviders(
      <LoginPage />,
      { route: '/login' }
    )

    await userEvent.type(getByLabelText(/email/i), 'alice@example.com')
    await userEvent.type(getByLabelText(/password/i), 'wrong-password')
    await userEvent.click(getByRole('button', { name: 'Sign in' }))

    expect(await findByText('Invalid credentials')).toBeInTheDocument()
  })
})