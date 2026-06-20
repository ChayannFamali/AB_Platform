import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'

import i18n from '../i18n'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export function renderWithProviders(
  ui,
  {
    route = '/',
    queryClient = createTestQueryClient(),
    locale = 'en',
  } = {}
) {
  if (i18n.language !== locale) {
    i18n.changeLanguage(locale)
  }
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
  return { ...result, queryClient }
}

export * from '@testing-library/react'