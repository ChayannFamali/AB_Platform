import { describe, expect, it } from 'vitest'
import { Beaker } from 'lucide-react'

import EmptyState from '../EmptyState'
import { renderWithProviders } from '../../test/utils'

describe('EmptyState', () => {
  it('renders title and description', () => {
    const { getByText } = renderWithProviders(
      <EmptyState
        title="No experiments"
        description="Create your first one"
      />
    )
    expect(getByText('No experiments')).toBeInTheDocument()
    expect(getByText('Create your first one')).toBeInTheDocument()
  })

  it('renders an action when provided', () => {
    const { getByRole } = renderWithProviders(
      <EmptyState
        title="No data"
        action={<button>Create new</button>}
      />
    )
    expect(getByRole('button', { name: 'Create new' })).toBeInTheDocument()
  })

  it('uses the provided icon', () => {
    const { container } = renderWithProviders(
      <EmptyState title="Empty" icon={Beaker} />
    )
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders nothing extra when only title is given', () => {
    const { getByText, queryByText } = renderWithProviders(
      <EmptyState title="Just a title" />
    )
    expect(getByText('Just a title')).toBeInTheDocument()
    expect(queryByText('Create your first one')).not.toBeInTheDocument()
  })
})