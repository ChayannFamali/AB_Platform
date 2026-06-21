# ADR-003: Real-Time Results Transport (SSE vs WebSocket)

## Status
Accepted

## Context

The platform needs real-time updates of experiment results. Currently, results
are computed hourly by a cron worker. The user must manually click "Analyze"
or wait for the hourly cron. For a product competing with Optimizely, the user
should see results update live (or near-live) while watching the Results page.

The transport must work through:
- nginx reverse proxy (frontend container → api container)
- Docker Compose networking
- Corporate firewalls (self-hosted, potentially behind VPN)

The data flow is unidirectional: server → client. The client does not send
real-time data to the server (it uses normal REST for mutations). We only need
the server to push result updates, SRM alerts, and sequential testing boundary
crossings to the frontend.

## Decision

**Use Server-Sent Events (SSE)** via FastAPI `StreamingResponse` with
`text/event-stream` content type.

### Implementation
- Endpoint: `GET /api/v1/events/stream?experiment_id=<id>` (JWT or API key auth)
- Server uses Redis Pub/Sub: worker publishes to channel `results:{experiment_id}`
  after analysis completes; SSE endpoint subscribes to this channel and fans out
  to connected SSE clients.
- Event types: `result_updated`, `srm_alert`, `sequential_boundary_crossed`,
  `winner_detected`, `guardrail_violated`
- Client uses `EventSource` API (browser built-in, no library needed)
- Reconnection: `EventSource` auto-reconnects natively with exponential backoff
- Heartbeat: server sends `: ping\n\n` every 30s to keep connection alive

### nginx configuration
```nginx
location /api/v1/events/stream {
    proxy_pass http://api:8000;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding on;
    proxy_buffering off;        # critical for SSE
    proxy_cache off;
    proxy_read_timeout 3600s;   # 1h connection lifetime
}
```

### Why not WebSocket
- WebSocket requires HTTP upgrade handshake — nginx needs `Upgrade` and
  `Connection` headers, which is more complex to configure
- WebSocket is bidirectional — we only need server → client
- WebSocket needs a client library (`ws` or native `WebSocket` with custom
  reconnection logic) — SSE uses native `EventSource` with auto-reconnect
- WebSocket is blocked by some corporate proxies that don't support upgrade
  — SSE is plain HTTP and passes through all proxies
- FastAPI WebSocket requires `websockets` package and a separate `@app.websocket()`
  route — SSE uses the same `StreamingResponse` we already use

## Consequences

**Positive:**
- Zero new dependencies on the frontend (EventSource is built-in)
- Works through nginx with a 5-line config change (proxy_buffering off)
- Auto-reconnect handled by browser
- Simple server implementation (FastAPI StreamingResponse + Redis pub/sub)
- HTTP/1.1 compatible (no upgrade needed)
- Easy to debug (curl can subscribe: `curl -N http://localhost:8000/api/v1/events/stream`)

**Negative:**
- One-directional (server → client) — but that's all we need
- Max 6 concurrent SSE connections per browser (HTTP/1.1 limit) — mitigated
  by multiplexing all experiment events into one connection if needed
- No binary frames (text only) — not an issue for JSON event payloads

## Alternatives Considered

### WebSocket (FastAPI + `websockets` package)
- Pros: Bidirectional, binary frames, no connection limit
- Cons: More complex nginx config, needs client library, upgrade handshake
  blocked by some firewalls, separate route type in FastAPI
- Rejected: bidirectional capability unused, more operational complexity

### Long-polling (client polls every N seconds)
- Pros: Simplest, works everywhere, no server changes
- Cons: Latency (N seconds delay), unnecessary server load (empty polls),
  no true real-time, wastes bandwidth
- Rejected: not real-time enough for a competitive product

### Pusher/Ably (third-party hosted real-time)
- Pros: Managed, scalable, easy
- Cons: External dependency (violates self-hosted principle), sends data
  to external servers, cost
- Rejected: violates the core self-hosted value proposition
