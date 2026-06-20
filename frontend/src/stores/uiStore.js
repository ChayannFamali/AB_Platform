import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useUiStore = create(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'light',
      locale: 'ru',
      toggleSidebar: () =>
        set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebar: (open) => set({ sidebarOpen: open }),
      setTheme: (theme) => set({ theme }),
      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'dark' ? 'light' : 'dark',
        })),
      setLocale: (locale) => set({ locale }),
    }),
    {
      name: 'ab-platform-ui',
    }
  )
)

export const selectTheme = (state) => state.theme
export const selectLocale = (state) => state.locale
export const selectSidebarOpen = (state) => state.sidebarOpen