import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getExperiment:    vi.fn(),
  getResults:       vi.fn(),
  getDailyResults:  vi.fn(),
  analyzeExperiment: vi.fn(),
  updateStatus:     vi.fn(),
  exportResults:    vi.fn(),
}))

import {
  exportResults,
  getDailyResults,
  getExperiment,
  getResults,
} from '../../api/client'
import ExperimentDetailPage from '../ExperimentDetailPage'
import { renderWithProviders } from '../../test/utils'

const EXP_ID = '11111111-1111-1111-1111-111111111111'

function mockExperiment(status = 'draft') {
  getExperiment.mockResolvedValue({
    data: {
      id: EXP_ID,
      name: 'Detail Test',
      status,
      description: 'desc',
      traffic_percentage: 100,
      mutex_group_id: null,
      started_at: null,
      ended_at: null,
      created_at: '2026-06-20T00:00:00Z',
      updated_at: '2026-06-20T00:00:00Z',
      variants: [
        { id: 'v1', name: 'control',   traffic_split: 50 },
        { id: 'v2', name: 'treatment', traffic_split: 50 },
      ],
      metrics: [
        {
          id: 'm1',
          name: 'Click Rate',
          event_name: 'button_click',
          metric_type: 'conversion',
          is_primary: true,
        },
      ],
    },
  })
  getResults.mockResolvedValue({ data: { items: [], metrics: [] } })
  getDailyResults.mockResolvedValue({ data: { items: [] } })
  exportResults.mockResolvedValue({ data: new Blob() })
}

describe('ExperimentDetailPage', () => {
  it('renders the experiment name and tab list', async () => {
    mockExperiment()
    const { findByText, findByRole } = renderWithProviders(
      <ExperimentDetailPage />,
      { route: `/experiments/${EXP_ID}` },
    )
    expect(await findByText('Detail Test')).toBeInTheDocument()
    // All 4 tab triggers must be present
    expect(await findByRole('tab', { name: /overview|обзор/i })).toBeInTheDocument()
  })

  it('shows the results tab content when ?tab=results', async () => {
    mockExperiment('running')
    const { findByText } = renderWithProviders(
      <ExperimentDetailPage />,
      { route: `/experiments/${EXP_ID}?tab=results` },
    )
    // "Run analysis" button appears in the results tab for running experiments
    expect(await findByText(/Run analysis|Запустить анализ/i)).toBeInTheDocument()
  })
})
