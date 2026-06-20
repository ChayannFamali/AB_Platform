import { describe, expect, it } from 'vitest'

import CreateExperiment from '../CreateExperiment'
import { renderWithProviders } from '../../test/utils'

describe('CreateExperiment', () => {
  it('renders the page header and primary form fields', () => {
    const { getByText, getByLabelText } = renderWithProviders(
      <CreateExperiment />,
      { route: '/experiments/new' }
    )

    expect(getByText('New experiment')).toBeInTheDocument()
    expect(getByLabelText(/name/i)).toBeInTheDocument()
    expect(getByLabelText(/traffic share/i)).toBeInTheDocument()
  })

  it('renders two variant inputs by default (control + treatment)', () => {
    const { getAllByDisplayValue } = renderWithProviders(
      <CreateExperiment />,
      { route: '/experiments/new' }
    )
    expect(getAllByDisplayValue('control')).toHaveLength(1)
    expect(getAllByDisplayValue('treatment')).toHaveLength(1)
  })
})