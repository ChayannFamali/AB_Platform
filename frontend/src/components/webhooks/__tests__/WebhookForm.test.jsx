import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'

import { renderWithProviders } from '../../../test/utils'
import WebhookForm from '../WebhookForm'

describe('WebhookForm', () => {
  it('renders the create title when editing is null', () => {
    renderWithProviders(
      <WebhookForm
        open={true}
        onOpenChange={() => {}}
        editing={null}
        onSubmit={() => Promise.resolve(null)}
        submitting={false}
      />
    )
    expect(screen.getByText(/New webhook/i)).toBeInTheDocument()
  })

  it('renders the edit title when editing is provided', () => {
    renderWithProviders(
      <WebhookForm
        open={true}
        onOpenChange={() => {}}
        editing={{
          id: 'wh-1',
          name: 'Slack #experiments',
          url: 'https://hooks.slack.com/services/x',
          events: ['winner_detected'],
          format: 'slack',
          is_active: true,
          has_secret: true,
        }}
        onSubmit={() => Promise.resolve(null)}
        submitting={false}
      />
    )
    expect(screen.getByText(/Edit webhook/i)).toBeInTheDocument()
  })

  it('exposes the four event checkboxes', () => {
    renderWithProviders(
      <WebhookForm
        open={true}
        onOpenChange={() => {}}
        editing={null}
        onSubmit={() => Promise.resolve(null)}
        submitting={false}
      />
    )
    expect(screen.getByLabelText(/Winner detected/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Sample Ratio Mismatch/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Guardrail violated/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Sequential boundary crossed/i)).toBeInTheDocument()
  })
})