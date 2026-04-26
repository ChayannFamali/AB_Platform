/**
 * In-memory кэш с TTL.
 * Хранит вариант пользователя — не нужно дёргать API при каждом вызове.
 */
class TTLCache {
  constructor(ttl = 300_000) {
    this.ttl = ttl; // миллисекунды
    this.store = new Map(); // key → { value, expiresAt }
  }

  get(key) {
    const entry = this.store.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return entry.value;
  }

  set(key, value) {
    this.store.set(key, {
      value,
      expiresAt: Date.now() + this.ttl,
    });
  }

  clear() {
    this.store.clear();
  }

  get size() {
    return this.store.size;
  }
}

module.exports = { TTLCache };
