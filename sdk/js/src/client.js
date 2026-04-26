const { TTLCache } = require('./cache');

class ABPlatformClient {
  /**
   * JavaScript SDK для AB Platform.
   *
   * С API ключом (рекомендуется):
   *   const client = new ABPlatformClient({
   *     apiUrl: 'http://localhost:8000',
   *     apiKey: 'abp_ваш_ключ',
   *   });
   *
   * Без ключа (для локальной разработки):
   *   const client = new ABPlatformClient({ apiUrl: 'http://localhost:8000' });
   */
  constructor({
    apiUrl,
    apiKey      = null,       // X-API-Key для авторизации
    timeout     = 1000,
    cacheTtl    = 300_000,
    batchSize   = 50,
    flushInterval = 10_000,
  }) {
    this.apiUrl   = apiUrl.replace(/\/$/, '');
    this.timeout  = timeout;
    this._cache   = new TTLCache(cacheTtl);
    this._eventBuffer = [];
    this._batchSize   = batchSize;

    // Базовые заголовки для всех запросов
    this._headers = { 'Content-Type': 'application/json' };
    if (apiKey) {
      this._headers['X-API-Key'] = apiKey;
    }

    this._flushTimer = setInterval(() => this.flush(), flushInterval);

    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => this.flush());
    }
  }

  // ─── Public API ────────────────────────────────────────────────────────────

  /**
   * Возвращает вариант эксперимента для пользователя.
   * Никогда не бросает исключение — при ошибке возвращает defaultVariant.
   */
  async getVariant(userId, experimentId, defaultVariant = 'control') {
    const cacheKey = `${userId}:${experimentId}`;

    const cached = this._cache.get(cacheKey);
    if (cached !== null) return cached;

    try {
      const controller = new AbortController();
      const timeoutId  = setTimeout(() => controller.abort(), this.timeout);

      const response = await fetch(`${this.apiUrl}/api/v1/assignments`, {
        method:  'POST',
        headers: this._headers,
        body:    JSON.stringify({ user_id: userId, experiment_id: experimentId }),
        signal:  controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        if (data.assigned && data.variant) {
          this._cache.set(cacheKey, data.variant);
          return data.variant;
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.warn('ABPlatform: getVariant timeout');
      } else {
        console.warn('ABPlatform: getVariant failed:', err.message);
      }
    }

    return defaultVariant;
  }

  /**
   * Буферизует событие для батч отправки. Синхронный вызов.
   */
  trackEvent(userId, eventName, value = null, properties = null) {
    this._eventBuffer.push({
      user_id:    userId,
      event_name: eventName,
      value,
      properties,
    });

    if (this._eventBuffer.length >= this._batchSize) {
      this.flush();
    }
  }

  /**
   * Отправляет все буферизованные события.
   */
  async flush() {
    if (this._eventBuffer.length === 0) return;

    const events = [...this._eventBuffer];
    this._eventBuffer = [];

    try {
      await fetch(`${this.apiUrl}/api/v1/events/batch`, {
        method:  'POST',
        headers: this._headers,
        body:    JSON.stringify({ events }),
      });
    } catch (err) {
      console.warn('ABPlatform: flush failed:', err.message);
    }
  }

  /**
   * Генерирует анонимный ID и сохраняет в localStorage.
   */
  static getAnonymousId() {
    if (typeof localStorage === 'undefined') {
      return ABPlatformClient._generateId();
    }
    let id = localStorage.getItem('_ab_anon_id');
    if (!id) {
      id = ABPlatformClient._generateId();
      localStorage.setItem('_ab_anon_id', id);
    }
    return id;
  }

  static mergeIdentity(anonymousId, userId) {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('_ab_anon_id');
    }
    return userId;
  }

  async destroy() {
    clearInterval(this._flushTimer);
    await this.flush();
  }

  static _generateId() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
  }
}

module.exports = { ABPlatformClient };
