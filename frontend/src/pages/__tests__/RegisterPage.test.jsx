import { describe, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/client', () => ({
  register: vi.fn(),
  login: vi.fn(),
}))

import { login, register } from '../../api/client'
import RegisterPage from '../RegisterPage'
import { renderWithProviders } from '../../test/utils'

describe('RegisterPage', () => {
  it('renders username/email/password/confirm fields', () => {
    const { getByLabelText, getByRole } = renderWithProviders(
      <RegisterPage />,
      { route: '/register' }
    )
    expect(getByLabelText(/username/i)).toBeInTheDocument()
    expect(getByLabelText(/email/i)).toBeInTheDocument()
    expect(getByLabelText(/^password/i)).toBeInTheDocument()
    expect(getByLabelText(/confirm/i)).toBeInTheDocument()
    expect(getByRole('button', { name: 'Sign up' })).toBeInTheDocument()
  })

  it('rejects submission when passwords do not match', async () => {
    const { getByLabelText, getByRole, findByText } = renderWithProviders(
      <RegisterPage />,
      { route: '/register' }
    )

    await userEvent.type(getByLabelText(/username/i), 'bob')
    await userEvent.type(getByLabelText(/email/i), 'bob@example.com')
    await userEvent.type(getByLabelText(/^password/i), 'password-1234')
    await userEvent.type(getByLabelText(/confirm/i), 'different-1234')
    await userEvent.click(getByRole('button', { name: 'Sign up' }))

    expect(register).not.toHaveBeenCalled()
    expect(
      await findByText('Passwords do not match')
    ).toBeInTheDocument()
  })

  it('calls register then login on a valid submit', async () => {
    register.mockResolvedValueOnce({ data: { id: 'u1' } })
    login.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-xyz',
        user: { username: 'bob', email: 'bob@example.com', roles: ['viewer'] },
      },
    })

    const { getByLabelText, getByRole } = renderWithProviders(
      <RegisterPage />,
      { route: '/register' }
    )

    await userEvent.type(getByLabelText(/username/i), 'bob')
    await userEvent.type(getByLabelText(/email/i), 'bob@example.com')
    await userEvent.type(getByLabelText(/^password/i), 'password-1234')
    await userEvent.type(getByLabelText(/confirm/i), 'password-1234')
    await userEvent.click(getByRole('button', { name: 'Sign up' }))

    expect(register).toHaveBeenCalledWith({
      username: 'bob',
      email: 'bob@example.com',
      password: 'password-1234',
    })
    expect(login).toHaveBeenCalledWith({
      email: 'bob@example.com',
      password: 'password-1234',
    })
  })
})