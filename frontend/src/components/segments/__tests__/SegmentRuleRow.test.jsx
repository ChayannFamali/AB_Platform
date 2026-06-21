import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'

import { renderWithProviders } from '../../../test/utils'
import SegmentRuleRow from '../SegmentRuleRow'

const baseRule = {
  id: 'rule-1',
  field: 'country',
  operator: 'eq',
  value: 'DE',
  priority: 0,
  enabled: true,
}

describe('SegmentRuleRow', () => {
  it('renders with default values from the rule prop', () => {
    renderWithProviders(
      <SegmentRuleRow rule={baseRule} onChange={() => {}} onRemove={() => {}} />,
    )
    expect(screen.getByDisplayValue('country')).toBeInTheDocument()
    expect(screen.getByDisplayValue('DE')).toBeInTheDocument()
    expect(screen.getByDisplayValue('0')).toBeInTheDocument()
  })

  it('calls onChange with the updated field', () => {
    const onChange = vi.fn()
    renderWithProviders(
      <SegmentRuleRow rule={baseRule} onChange={onChange} onRemove={() => {}} />,
    )
    const fieldInput = screen.getByDisplayValue('country')
    fireEvent.change(fieldInput, { target: { value: 'plan' } })
    expect(onChange).toHaveBeenCalled()
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(lastCall.field).toBe('plan')
  })

  it('calls onRemove when the trash button is clicked', () => {
    const onRemove = vi.fn()
    renderWithProviders(
      <SegmentRuleRow rule={baseRule} onChange={() => {}} onRemove={onRemove} />,
    )
    const removeBtn = screen.getByRole('button')
    fireEvent.click(removeBtn)
    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})
