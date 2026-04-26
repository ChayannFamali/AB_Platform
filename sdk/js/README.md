# AB Platform — JavaScript SDK

## Installation

```bash
npm install abplatform
# или локально:
npm install ./sdk/js
```

## Usage

```javascript
const { ABPlatformClient } = require('abplatform');

const client = new ABPlatformClient({
  apiUrl: 'http://your-ab-platform:8000',
});

// Получить вариант
const variant = await client.getVariant('user_123', 'experiment-uuid');
if (variant === 'treatment') {
  showNewButton();
}

// Трекать событие
client.trackEvent('user_123', 'button_click');
client.trackEvent('user_123', 'purchase', 49.99);
client.trackEvent('user_123', 'page_view', null, { page: '/home' });

// Анонимный пользователь (до логина)
const anonId = ABPlatformClient.getAnonymousId();
const variant = await client.getVariant(anonId, 'experiment-uuid');

// Shutdown
await client.destroy();
```

## Configuration

```javascript
const client = new ABPlatformClient({
  apiUrl: 'http://localhost:8000',
  timeout: 1000,          // таймаут запроса (мс)
  cacheTtl: 300_000,      // кэш варианта (мс)
  batchSize: 50,          // flush при N событиях
  flushInterval: 10_000,  // flush каждые N мс
});
```
