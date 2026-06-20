import { useEffect, useRef } from 'react'

import { useAuthStore } from '../stores/authStore'

const SSE_EVENT_TYPES = [
  'result_updated',
  'srm_alert',
  'sequential_boundary_crossed',
  'winner_detected',
  'guardrail_violated',
]

/**
 * Subscribe to SSE events for an experiment.
 *
 * The native EventSource API does not allow custom request headers
 * (Authorization is impossible), so the JWT travels as a `?token=` query
 * parameter (per ADR-003). EventSource reconnects automatically with the
 * same URL on disconnect — including the token.
 *
 * @param {string} experimentId — UUID of the experiment to subscribe to.
 * @param {object} options
 * @param {(eventType: string, data: object) => void} options.onEvent
 *   Callback invoked for each named event. `data` is the parsed JSON
 *   payload.
 * @param {boolean} [options.enabled=true]
 *   When false, the connection is not opened (useful for hiding the
 *   subscription behind a feature flag or permission check).
 */
export function useSSE(experimentId, { onEvent, enabled = true } = {}) {
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!enabled || !experimentId) return undefined

    const token = useAuthStore.getState().token
    if (!token) return undefined

    const params = new URLSearchParams({
      experiment_id: experimentId,
      token,
    })
    const url = `/api/v1/events/stream?${params.toString()}`

    const source = new EventSource(url)

    const handleMessage = (eventType) => (event) => {
      let payload = {}
      try {
        payload = event.data ? JSON.parse(event.data) : {}
      } catch {
        payload = { raw: event.data }
      }
      if (onEventRef.current) {
        onEventRef.current(eventType, payload)
      }
    }

    const listeners = SSE_EVENT_TYPES.map((type) => {
      const handler = handleMessage(type)
      source.addEventListener(type, handler)
      return [type, handler]
    })

    // `connected` is fired by the backend right after the socket opens —
    // we don't propagate it as a typed event, but we listen so the
    // browser doesn't drop the frame and we can confirm the stream is
    // alive even before the first analysis.
    source.addEventListener('connected', () => {
      // no-op; consumers don't need this signal
    })

    return () => {
      for (const [type, handler] of listeners) {
        source.removeEventListener(type, handler)
      }
      source.removeEventListener('connected', () => {})
      source.close()
    }
  }, [experimentId, enabled])
}