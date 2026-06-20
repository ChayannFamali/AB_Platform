import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export default function AppQueryClientProvider({ children }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 2,
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 1,
          },
        },
      })
  )
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}