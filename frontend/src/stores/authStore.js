import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,
      roles: [],
      setAuth: (user, token, roles = []) =>
        set({ user, token, roles }),
      setUser: (user, roles = []) =>
        set({ user, roles }),
      logout: () =>
        set({ user: null, token: null, roles: [] }),
    }),
    {
      name: 'ab-platform-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        roles: state.roles,
      }),
    }
  )
)

export const selectUser = (state) => state.user
export const selectToken = (state) => state.token
export const selectRoles = (state) => state.roles
export const selectIsAuthenticated = (state) => Boolean(state.user && state.token)
export const selectHasRole = (role) => (state) =>
  Array.isArray(state.roles) && state.roles.includes(role)