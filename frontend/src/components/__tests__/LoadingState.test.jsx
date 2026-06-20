import { describe, expect, it } from 'vitest'

import LoadingState, { Spinner } from '../LoadingState'
import { renderWithProviders } from '../../test/utils'

describe('LoadingState', () => {
  it('renders the spinner variant by default', () => {
    const { container } = renderWithProviders(<LoadingState />)
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders the spinner variant when explicitly requested', () => {
    const { container, getByText } = renderWithProviders(
      <LoadingState variant="spinner" label="Loading data" />
    )
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
    expect(getByText('Loading data')).toBeInTheDocument()
  })

  it('renders the skeleton variant with the requested row count', () => {
    const { container } = renderWithProviders(
      <LoadingState variant="skeleton" count={3} />
    )
    const rows = container.querySelectorAll('.animate-pulse')
    expect(rows).toHaveLength(3)
  })

  it('exports Spinner as a named export', () => {
    const { container } = renderWithProviders(<Spinner />)
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })
})