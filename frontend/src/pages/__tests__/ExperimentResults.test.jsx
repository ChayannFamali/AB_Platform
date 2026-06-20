import { describe, expect, it, vi } from 'vitest'

vi.mock('../../api/client', () => ({
  getExperiment: vi.fn(),
  getResults: vi.fn(),
  getDailyResults: vi.fn(),
  analyzeExperiment: vi.fn(),
  updateStatus: vi.fn(),
}))

import {
  analyzeExperiment,
  getDailyResults,
  getExperiment,
  getResults,
} from '../../api/client'
import ExperimentResults from '../ExperimentResults'
import { renderWithProviders } from '../../test/utils'

const EXP_ID = '11111111-1111-1111-1111-111111111111'

function mockAllEmpty() {
  getExperiment.mockResolvedValue({
    data: {
      id: EXP_ID,
      name: 'Empty Experiment',
      status: 'draft',
      description: 'No data yet',
      traffic_percentage: 100,
      variants: [
        { id: 'v1', name: 'control', traffic_split: 50 },
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
  getResults.mockResolvedValue({ data: { items: [], total: 0, metrics: [] } })
  getDailyResults.mockResolvedValue({ data: { items: [] } })
  analyzeExperiment.mockResolvedValue({ data: {} })
}

describe('ExperimentResults', () => {
  it('renders the experiment name as the page header', async () => {
    mockAllEmpty()
    const { findByText } = renderWithProviders(<ExperimentResults />, {
      route: `/experiments/${EXP_ID}`,
    })

    expect(await findByText('Empty Experiment')).toBeInTheDocument()
  })
})