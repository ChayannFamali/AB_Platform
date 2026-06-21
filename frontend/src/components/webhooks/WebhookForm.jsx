import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../ui/button'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../ui/dialog'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select'

const EVENTS = [
  'winner_detected',
  'srm_alert',
  'guardrail_violated',
  'sequential_boundary_crossed',
]
const FORMATS = ['generic', 'slack', 'discord']

/**
 * Modal form for create + edit. When `editing` is null we POST a new
 * webhook; otherwise PATCH the existing one. `onCreated` receives the
 * create response (which includes the plain secret, returned only
 * once) so the caller can show a copy-to-clipboard prompt.
 *
 * Uses the "derived state from props" trick (mirrors GuardrailEditor
 * + DecisionForm) to reset fields on open without an effect-driven
 * setState — ESLint's react-hooks/set-state-in-effect rule rejects
 * the simpler approach.
 */
export default function WebhookForm({
  open,
  onOpenChange,
  editing,
  onSubmit,
  submitting,
  onCreated,
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState(() => initialForm(editing))
  const [editingId, setEditingId] = useState(editing?.id ?? null)

  if (editingId !== (editing?.id ?? null)) {
    setForm(initialForm(editing))
    setEditingId(editing?.id ?? null)
  }

  const toggleEvent = (ev) => {
    setForm((f) => ({
      ...f,
      events: f.events.includes(ev)
        ? f.events.filter((e) => e !== ev)
        : [...f.events, ev],
    }))
  }

  const submit = async () => {
    const body = {
      name:      form.name.trim(),
      url:       form.url.trim(),
      events:    form.events,
      format:    form.format,
      is_active: form.is_active,
    }
    // Only send the secret on create or when the user explicitly
    // entered one (PATCH with empty string = clear).
    if (!editing || form.secret.trim()) {
      body.secret = form.secret.trim() || null
    }
    const result = await onSubmit(body)
    if (!editing && result && result.id && onCreated) {
      onCreated(result)
    }
  }

  const urlError = form.url && !/^https?:\/\/.+/.test(form.url.trim())
  const saveDisabled =
    submitting
    || !form.name.trim()
    || !form.url.trim()
    || urlError
    || form.events.length === 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {editing ? t('webhooks.editTitle') : t('webhooks.newTitle')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="wh-name">{t('webhooks.name')}</Label>
            <Input
              id="wh-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('webhooks.namePlaceholder')}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="wh-url">{t('webhooks.url')}</Label>
            <Input
              id="wh-url"
              type="url"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="https://hooks.slack.com/services/..."
            />
            {urlError && (
              <p className="text-xs text-destructive">
                {t('webhooks.urlError')}
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="wh-format">{t('webhooks.format')}</Label>
              <Select
                value={form.format}
                onValueChange={(v) => setForm({ ...form, format: v })}
              >
                <SelectTrigger id="wh-format">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FORMATS.map((f) => (
                    <SelectItem key={f} value={f}>
                      {t(`webhooks.formats.${f}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="wh-secret">{t('webhooks.secret')}</Label>
              <Input
                id="wh-secret"
                type="password"
                value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
                placeholder={editing ? '••••••••' : 'whsec_...'}
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            {t('webhooks.secretHelp')}
          </p>
          <div className="space-y-1">
            <Label>{t('webhooks.events')}</Label>
            <div className="grid grid-cols-2 gap-2">
              {EVENTS.map((ev) => (
                <label key={ev} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.events.includes(ev)}
                    onChange={() => toggleEvent(ev)}
                  />
                  <span>{t(`webhooks.eventNames.${ev}`)}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            {t('webhooks.isActive')}
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={submit} disabled={saveDisabled}>
            {t('common.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function initialForm(editing) {
  if (editing) {
    return {
      name:      editing.name || '',
      url:       editing.url || '',
      events:    Array.isArray(editing.events) ? editing.events : [],
      format:    editing.format || 'generic',
      secret:    '',  // never pre-fill — secret is write-only after create
      is_active: editing.is_active ?? true,
    }
  }
  return {
    name:      '',
    url:       '',
    events:    ['winner_detected'],
    format:    'generic',
    secret:    '',
    is_active: true,
  }
}