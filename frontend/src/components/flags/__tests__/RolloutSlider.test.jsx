import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import RolloutSlider from '../RolloutSlider'
import { renderWithProviders } from '../../../test/utils'

describe('RolloutSlider', () => {
  it('renders the current value as a percentage', () => {
    renderWithProviders(<RolloutSlider value={42} onChange={() => {}} />)
    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('updates the displayed value when the parent updates value', () => {
    const { rerender } = renderWithProviders(
      <RolloutSlider value={0} onChange={() => {}} />,
    )
    expect(screen.getByText('0%')).toBeInTheDocument()
    rerender(<RolloutSlider value={75} onChange={() => {}} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('fires onChange on mouseup with the current value', () => {
    const onChange = vi.fn()
    renderWithProviders(<RolloutSlider value={10} onChange={onChange} />)
    const slider = screen.getByTestId('rollout-slider')
    fireEvent.change(slider, { target: { value: '80' } })
    fireEvent.mouseUp(slider)
    expect(onChange).toHaveBeenCalledWith(80)
  })

  it('honors disabled prop', () => {
    renderWithProviders(<RolloutSlider value={50} onChange={() => {}} disabled />)
    const slider = screen.getByTestId('rollout-slider')
    expect(slider).toBeDisabled()
  })
})