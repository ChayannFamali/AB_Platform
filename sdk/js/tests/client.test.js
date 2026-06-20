const fetchMock = require('jest-fetch-mock');
fetchMock.enableMocks();

const { ABPlatformClient } = require('../src/client');
const { TTLCache } = require('../src/cache');

beforeEach(() => {
  fetch.resetMocks();
});

// ─── TTLCache ──────────────────────────────────────────────────────────────

describe('TTLCache', () => {
  test('stores and retrieves value', () => {
    const cache = new TTLCache(60_000);
    cache.set('key', 'value');
    expect(cache.get('key')).toBe('value');
  });

  test('returns null for missing key', () => {
    const cache = new TTLCache(60_000);
    expect(cache.get('nonexistent')).toBeNull();
  });

  test('expires after TTL', async () => {
    const cache = new TTLCache(50); // 50ms
    cache.set('key', 'value');
    await new Promise((r) => setTimeout(r, 100));
    expect(cache.get('key')).toBeNull();
  });

  test('clear removes all entries', () => {
    const cache = new TTLCache(60_000);
    cache.set('a', '1');
    cache.set('b', '2');
    cache.clear();
    expect(cache.size).toBe(0);
  });
});

// ─── getVariant ────────────────────────────────────────────────────────────

describe('getVariant', () => {
  test('returns variant when assigned', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ assigned: true, variant: 'treatment', experiment_id: 'exp-1' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const variant = await client.getVariant('user_1', 'exp-1');
    expect(variant).toBe('treatment');
    await client.destroy();
  });

  test('returns default when not assigned', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ assigned: false, variant: null, experiment_id: 'exp-1' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const variant = await client.getVariant('user_1', 'exp-1', 'control');
    expect(variant).toBe('control');
    await client.destroy();
  });

  test('returns default on server error', async () => {
    fetch.mockResponseOnce('Internal Server Error', { status: 500 });
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const variant = await client.getVariant('user_1', 'exp-1', 'control');
    expect(variant).toBe('control');
    await client.destroy();
  });

  test('returns default when fetch throws', async () => {
    fetch.mockRejectOnce(new Error('Network error'));
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const variant = await client.getVariant('user_1', 'exp-1', 'control');
    expect(variant).toBe('control');
    await client.destroy();
  });

  test('caches result — second call no HTTP request', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ assigned: true, variant: 'treatment', experiment_id: 'exp-1' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    await client.getVariant('user_1', 'exp-1');
    await client.getVariant('user_1', 'exp-1');
    await client.getVariant('user_1', 'exp-1');

    expect(fetch).toHaveBeenCalledTimes(1); // только один запрос
    await client.destroy();
  });
});

// ─── trackEvent + flush ────────────────────────────────────────────────────

describe('trackEvent and flush', () => {
  test('buffers events without sending immediately', () => {
    const client = new ABPlatformClient({
      apiUrl: 'http://localhost:8000',
      batchSize: 100,
    });
    client.trackEvent('user_1', 'click');
    client.trackEvent('user_1', 'purchase', 49.99);

    expect(client._eventBuffer.length).toBe(2);
    expect(fetch).not.toHaveBeenCalled();
    clearInterval(client._flushTimer);
  });

  test('flush sends all events in one request', async () => {
    fetch.mockResponseOnce(JSON.stringify({ received: 2, inserted: 2 }), {
      status: 201,
    });
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    client.trackEvent('user_1', 'click');
    client.trackEvent('user_2', 'purchase', 100.0);
    await client.flush();

    expect(fetch).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetch.mock.calls[0][1].body);
    expect(body.events).toHaveLength(2);
    expect(body.events[1].value).toBe(100.0);
    await client.destroy();
  });

  test('auto flush when batchSize reached', async () => {
    fetch.mockResponse(JSON.stringify({ received: 3, inserted: 3 }), {
      status: 201,
    });
    const client = new ABPlatformClient({
      apiUrl: 'http://localhost:8000',
      batchSize: 3,
    });
    client.trackEvent('u1', 'e1');
    client.trackEvent('u2', 'e2');
    client.trackEvent('u3', 'e3'); // ← flush должен сработать

    await new Promise((r) => setTimeout(r, 50));
    expect(fetch).toHaveBeenCalledTimes(1);
    await client.destroy();
  });

  test('flush with empty buffer does nothing', async () => {
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    await client.flush();
    expect(fetch).not.toHaveBeenCalled();
    await client.destroy();
  });

  test('flush does not throw when server is down', async () => {
    fetch.mockRejectOnce(new Error('Connection refused'));
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    client.trackEvent('user_1', 'click');
    await expect(client.flush()).resolves.not.toThrow();
    await client.destroy();
  });
});

// ─── Anonymous ID ──────────────────────────────────────────────────────────

describe('getAnonymousId', () => {
  test('returns a string ID', () => {
    const id = ABPlatformClient.getAnonymousId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
  });
});

// ─── getFlag (M-009) ──────────────────────────────────────────────────────

describe('getFlag', () => {
  test('returns true when the flag is enabled', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ key: 'new_checkout', value: true, reason: 'rollout_in' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const value = await client.getFlag('user_1', 'new_checkout');
    expect(value).toBe(true);
    await client.destroy();
  });

  test('returns false when the flag is disabled', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ key: 'new_checkout', value: false, reason: 'kill_switch' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const value = await client.getFlag('user_1', 'new_checkout');
    expect(value).toBe(false);
    await client.destroy();
  });

  test('returns defaultValue on server error', async () => {
    fetch.mockResponseOnce('Internal Server Error', { status: 500 });
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const value = await client.getFlag('user_1', 'any', true);
    expect(value).toBe(true);
    await client.destroy();
  });

  test('returns defaultValue when fetch throws', async () => {
    fetch.mockRejectOnce(new Error('Connection refused'));
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const value = await client.getFlag('user_1', 'any', false);
    expect(value).toBe(false);
    await client.destroy();
  });

  test('caches the result — second call skips fetch', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ key: 'cached_flag', value: true, reason: 'rollout_in' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000', cacheTtl: 60_000 });
    await client.getFlag('user_1', 'cached_flag');
    await client.getFlag('user_1', 'cached_flag');
    await client.getFlag('user_1', 'cached_flag');
    expect(fetch).toHaveBeenCalledTimes(1);
    await client.destroy();
  });

  test('distinct users have distinct cache entries', async () => {
    fetch.mockResponse(
      JSON.stringify({ key: 'per_user', value: true, reason: 'rollout_in' })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    await client.getFlag('user_A', 'per_user');
    await client.getFlag('user_B', 'per_user');
    expect(fetch).toHaveBeenCalledTimes(2);
    await client.destroy();
  });
});

// ─── getFlags (M-009 batch) ────────────────────────────────────────────────

describe('getFlags', () => {
  test('returns all keys in one request when nothing is cached', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ values: { a: true, b: false, c: true }, details: {} })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const result = await client.getFlags('user_1', ['a', 'b', 'c']);
    expect(result).toEqual({ a: true, b: false, c: true });
    expect(fetch).toHaveBeenCalledTimes(1);
    await client.destroy();
  });

  test('returns empty object for empty key list', async () => {
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const result = await client.getFlags('user_1', []);
    expect(result).toEqual({});
    expect(fetch).not.toHaveBeenCalled();
    await client.destroy();
  });

  test('uses cache for already-resolved keys — only fetches the missing ones', async () => {
    fetch.mockResponseOnce(
      JSON.stringify({ key: 'cached_flag', value: true, reason: 'rollout_in' })
    );
    fetch.mockResponseOnce(
      JSON.stringify({ values: { fresh_flag: false }, details: {} })
    );
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000', cacheTtl: 60_000 });
    await client.getFlag('user_1', 'cached_flag');
    const result = await client.getFlags('user_1', ['cached_flag', 'fresh_flag']);
    expect(result).toEqual({ cached_flag: true, fresh_flag: false });
    expect(fetch).toHaveBeenCalledTimes(2);
    const lastCall = fetch.mock.calls[1];
    expect(lastCall[0]).toContain('/flags/evaluate-batch');
    await client.destroy();
  });

  test('returns all defaults when server is unreachable', async () => {
    fetch.mockRejectOnce(new Error('Connection refused'));
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const result = await client.getFlags('user_1', ['a', 'b', 'c']);
    expect(result).toEqual({ a: false, b: false, c: false });
    await client.destroy();
  });

  test('returns defaults when server returns 403 (missing scope)', async () => {
    fetch.mockResponseOnce('Forbidden', { status: 403 });
    const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
    const result = await client.getFlags('user_1', ['x']);
    expect(result).toEqual({ x: false });
    await client.destroy();
  });
});
