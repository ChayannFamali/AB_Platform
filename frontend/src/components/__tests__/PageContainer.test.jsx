import { describe, expect, it } from 'vitest'

import PageContainer, { PageHeader } from '../PageContainer'
import { renderWithProviders } from '../../test/utils'

describe('PageContainer', () => {
  it('renders its children', () => {
    const { getByText } = renderWithProviders(
      <PageContainer>
        <span>hello world</span>
      </PageContainer>
    )
    expect(getByText('hello world')).toBeInTheDocument()
  })

  it('passes className to the wrapper', () => {
    const { container } = renderWithProviders(
      <PageContainer className="extra-class">x</PageContainer>
    )
    const wrapper = container.firstChild
    expect(wrapper).toHaveClass('extra-class')
  })
})

describe('PageHeader', () => {
  it('renders title and description', () => {
    const { getByText } = renderWithProviders(
      <PageHeader
        title="Experiments"
        description="Manage your tests"
      />
    )
    expect(getByText('Experiments')).toBeInTheDocument()
    expect(getByText('Manage your tests')).toBeInTheDocument()
  })

  it('renders the actions slot', () => {
    const { getByRole } = renderWithProviders(
      <PageHeader
        title="x"
        actions={<button>Create</button>}
      />
    )
    expect(getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })

  it('skips description when not provided', () => {
    const { queryByText } = renderWithProviders(<PageHeader title="only title" />)
    expect(queryByText('Manage your tests')).not.toBeInTheDocument()
  })
})