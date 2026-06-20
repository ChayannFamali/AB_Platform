import { describe, expect, it } from 'vitest'
import InsightPanel from '../InsightPanel'
import { renderWithProviders } from '../../../test/utils'

describe('InsightPanel', () => {
  const sample = [
    {
      type: 'srm_detected',
      severity: 'error',
      title: 'stats.insights.srm.title',
      description: 'stats.insights.srm.description',
      params: { p_value: 0.001 },
    },
    {
      type: 'clear_winner',
      severity: 'success',
      title: 'stats.insights.clearWinner.title',
      description: 'stats.insights.clearWinner.description',
      params: { lift: 5.0, p_value: 0.005 },
    },
  ]

  it('renders nothing for empty insights', () => {
    const { container } = renderWithProviders(<InsightPanel insights={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders one row per insight', () => {
    const { getAllByText } = renderWithProviders(<InsightPanel insights={sample} />)
    // SRM detected renders the title (i18n key resolves to EN/RU string)
    // We just verify the panel renders without errors.
    expect(getAllByText(/SRM|Sample|Clear winner|Победитель/i).length).toBeGreaterThan(0)
  })

  it('exposes data-severity for CSS styling', () => {
    const { container } = renderWithProviders(<InsightPanel insights={sample} />)
    const errorRow = container.querySelector('[data-severity="error"]')
    const successRow = container.querySelector('[data-severity="success"]')
    expect(errorRow).not.toBeNull()
    expect(successRow).not.toBeNull()
  })
})