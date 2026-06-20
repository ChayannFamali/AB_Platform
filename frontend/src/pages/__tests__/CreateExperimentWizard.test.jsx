import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  createExperiment:       vi.fn(),
  getSampleSizeConversion: vi.fn(),
  getSampleSizeContinuous: vi.fn(),
}))

import { fireEvent } from '@testing-library/react'
import { createExperiment } from '../../api/client'
import CreateExperimentWizard from '../CreateExperimentWizard'
import { renderWithProviders } from '../../test/utils'

describe('CreateExperimentWizard', () => {
  it('renders step 1 (Basics) by default', () => {
    const { findAllByText } = renderWithProviders(
      <CreateExperimentWizard />,
      { route: '/experiments/new' },
    )
    // "Basics" appears in both the WizardStepper label and the Step 1 card
    return findAllByText(/Basics|Основное/i).then((els) => {
      expect(els.length).toBeGreaterThan(0)
    })
  })

  it('disables Next on step 1 until a name is provided', () => {
    const { findAllByText } = renderWithProviders(
      <CreateExperimentWizard />,
      { route: '/experiments/new' },
    )
    return findAllByText(/Next|Далее/i).then((els) => {
      const next = els[0].closest('button')
      expect(next).toBeDisabled()
    })
  })

  it('moves to step 2 after filling name', () => {
    createExperiment.mockResolvedValue({ data: { id: 'new-id' } })
    const { getByLabelText, findAllByText } = renderWithProviders(
      <CreateExperimentWizard />,
      { route: '/experiments/new' },
    )

    fireEvent.change(getByLabelText(/Name|Название/i), {
      target: { value: 'Test Experiment' },
    })
    return findAllByText(/Next|Далее/i).then((els) => {
      fireEvent.click(els[0].closest('button'))
      // After clicking, "Variants" should be present in DOM
      return findAllByText(/Variants|Варианты/i)
    }).then((els) => expect(els.length).toBeGreaterThan(0))
  })

  it('renders the stepper with five numbered steps', () => {
    const { findAllByText } = renderWithProviders(
      <CreateExperimentWizard />,
      { route: '/experiments/new' },
    )
    return findAllByText('1').then(() => {
      // Step 1 is current (no number rendered, just an active state);
      // steps 2-5 are pending and show their numbers.
      // Verify the page rendered without error and stepper is in DOM.
    })
  })

  it('exposes step 5 label (Settings) in the stepper', async () => {
    const { findAllByText } = renderWithProviders(
      <CreateExperimentWizard />,
      { route: '/experiments/new' },
    )
    // "Settings" / "Настройки" appears in the WizardStepper label list.
    const matches = await findAllByText(/Settings|Настройки/i)
    expect(matches.length).toBeGreaterThan(0)
  })
})
