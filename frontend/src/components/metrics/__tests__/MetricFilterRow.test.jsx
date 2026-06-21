import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'

import { renderWithProviders } from '../../../test/utils'
import MetricFilterRow from '../MetricFilterRow'

const baseRule = {
  id: 'filter-1',
  field: 'country',
  operator: 'eq',
  value: 'DE',
  priority: 0,
  enabled: true,
}

describe('MetricFilterRow', () => {
  it('renders with default values from the rule prop', () => {
    renderWithProviders(
      <MetricFilterRow rule={baseRule} onChange={() => {}} onRemove={() => {}} />,
    )
    expect(screen.getByDisplayValue('country')).toBeInTheDocument()
    expect(screen.getByDisplayValue('DE')).toBeInTheDocument()
  })

  it('calls onChange with the updated field', () => {
    const onChange = vi.fn()
    renderWithProviders(
      <MetricFilterRow rule={baseRule} onChange={onChange} onRemove={() => {}} />,
    )
    const fieldInput = screen.getByDisplayValue('country')
    fireEvent.change(fieldInput, { target: { value: 'plan' } })
    expect(onChange).toHaveBeenCalled()
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(lastCall.field).toBe('plan')
  })

  it('renders the value as a comma-joined textarea when operator is in', () => {
    renderWithProviders(
      <MetricFilterRow
        rule={{ ...baseRule, operator: 'in', value: ['DE', 'FR'] }}
        onChange={() => {}}
        onRemove={() => {}}
      />,
    )
    const textarea = screen.getByLabelText(/value/i)
    expect(textarea.value).toContain('DE')
    expect(textarea.value).toContain('FR')
  })

  it('calls onRemove when the trash button is clicked', () => {
    const onRemove = vi.fn()
    renderWithProviders(
      <MetricFilterRow rule={baseRule} onChange={() => {}} onRemove={onRemove} />,
    )
    const removeBtn = screen.getByRole('button')
    fireEvent.click(removeBtn)
    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})
