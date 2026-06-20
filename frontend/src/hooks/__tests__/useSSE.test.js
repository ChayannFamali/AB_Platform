import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

// Mock the auth store so we control the JWT.
const mockGetToken = vi.fn()
vi.mock('../../stores/authStore', () => ({
  useAuthStore: {
    getState: () => ({ token: mockGetToken() }),
  },
}))

// Track the latest EventSource instance so tests can inspect addEventListener calls.
let lastSource = null
class FakeEventSource {
  constructor(url) {
    this.url = url
    this.readyState = 0
    this.listeners = new Map()
    lastSource = this
  }
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, [])
    this.listeners.get(type).push(handler)
  }
  removeEventListener(type, handler) {
    const arr = this.listeners.get(type) || []
    this.listeners.set(type, arr.filter((h) => h !== handler))
  }
  close() {
    this.readyState = 2
    this._closed = true
  }
  // Test helper — fire a typed event.
  fire(type, data) {
    const arr = this.listeners.get(type) || []
    arr.forEach((h) => h({ data: JSON.stringify(data) }))
  }
}
globalThis.EventSource = FakeEventSource

import { renderHook, act } from '@testing-library/react'
import { useSSE } from '../useSSE'

describe('useSSE', () => {
  beforeEach(() => {
    lastSource = null
    mockGetToken.mockReturnValue('jwt-token-xyz')
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('does not open a connection when disabled', () => {
    renderHook(() => useSSE('exp-1', { enabled: false }))
    expect(lastSource).toBeNull()
  })

  it('does not open a connection when token is missing', () => {
    mockGetToken.mockReturnValue(null)
    renderHook(() => useSSE('exp-1', { enabled: true }))
    expect(lastSource).toBeNull()
  })

  it('opens an EventSource with the right URL when enabled with a token', () => {
    renderHook(() => useSSE('exp-uuid', { enabled: true }))
    expect(lastSource).not.toBeNull()
    expect(lastSource.url).toContain('/api/v1/events/stream?')
    expect(lastSource.url).toContain('experiment_id=exp-uuid')
    expect(lastSource.url).toContain('token=jwt-token-xyz')
  })

  it('subscribes to all 5 named event types plus connected', () => {
    renderHook(() => useSSE('exp-1', { enabled: true }))
    const types = [...lastSource.listeners.keys()]
    expect(types).toContain('result_updated')
    expect(types).toContain('srm_alert')
    expect(types).toContain('winner_detected')
    expect(types).toContain('guardrail_violated')
    expect(types).toContain('sequential_boundary_crossed')
    expect(types).toContain('connected')
  })

  it('invokes onEvent callback when a typed event fires', () => {
    const onEvent = vi.fn()
    renderHook(() => useSSE('exp-1', { enabled: true, onEvent }))

    act(() => {
      lastSource.fire('result_updated', { experiment_id: 'exp-1', foo: 'bar' })
    })

    expect(onEvent).toHaveBeenCalledWith('result_updated', { experiment_id: 'exp-1', foo: 'bar' })
  })

  it('closes the EventSource on unmount', () => {
    const { unmount } = renderHook(() => useSSE('exp-1', { enabled: true }))
    const source = lastSource
    unmount()
    expect(source._closed).toBe(true)
  })
})