import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.jsx'
import AppQueryClientProvider from './providers/QueryClientProvider.jsx'
import I18nProvider from './providers/I18nProvider.jsx'
import ThemeProvider from './providers/ThemeProvider.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'

import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <AppQueryClientProvider>
        <I18nProvider>
          <ThemeProvider>
            <App />
          </ThemeProvider>
        </I18nProvider>
      </AppQueryClientProvider>
    </ErrorBoundary>
  </StrictMode>
)