import { describe, expect, it } from 'vitest'

import WizardStepper from '../WizardStepper'
import { renderWithProviders } from '../../../test/utils'

const STEPS = [
  { key: 'a', title: 'Basics' },
  { key: 'b', title: 'Variants' },
  { key: 'c', title: 'Metrics' },
  { key: 'd', title: 'Review' },
]

describe('WizardStepper', () => {
  it('renders all step labels', () => {
    const { getByText } = renderWithProviders(
      <WizardStepper steps={STEPS} currentIndex={0} />,
    )
    STEPS.forEach((s) => expect(getByText(s.title)).toBeInTheDocument())
  })

  it('marks the current step with aria-current="step"', () => {
    const { getByText } = renderWithProviders(
      <WizardStepper steps={STEPS} currentIndex={2} />,
    )
    const current = getByText('Metrics')
    expect(current.closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('shows step numbers for pending steps', () => {
    const { getByText } = renderWithProviders(
      <WizardStepper steps={STEPS} currentIndex={0} />,
    )
    // Step 1 is the only one rendered as a number for non-done pending steps.
    expect(getByText('2')).toBeInTheDocument()
    expect(getByText('3')).toBeInTheDocument()
    expect(getByText('4')).toBeInTheDocument()
  })
})
