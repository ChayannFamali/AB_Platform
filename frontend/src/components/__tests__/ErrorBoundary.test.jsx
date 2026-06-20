import { describe, expect, it } from 'vitest'

import ErrorBoundary from '../ErrorBoundary'
import { renderWithProviders } from '../../test/utils'

function Boom() {
  throw new Error('kaboom')
}

describe('ErrorBoundary', () => {
  it('renders children when nothing throws', () => {
    const { getByText } = renderWithProviders(
      <ErrorBoundary>
        <div>healthy child</div>
      </ErrorBoundary>
    )
    expect(getByText('healthy child')).toBeInTheDocument()
  })

  it('renders the default fallback when a child throws', () => {
    const { getByText } = renderWithProviders(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    )
    expect(getByText('Something went wrong')).toBeInTheDocument()
    expect(getByText('kaboom')).toBeInTheDocument()
    expect(getByText('Try again')).toBeInTheDocument()
  })

  it('renders a custom fallback when provided', () => {
    const fallback = () => <div>custom error ui</div>
    const { getByText, queryByText } = renderWithProviders(
      <ErrorBoundary fallback={fallback}>
        <Boom />
      </ErrorBoundary>
    )
    expect(getByText('custom error ui')).toBeInTheDocument()
    expect(queryByText('Something went wrong')).not.toBeInTheDocument()
  })
})