import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../ui/button'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '../ui/dialog'
import { Label } from '../ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select'

const STATUSES = ['ship', 'stop', 'iterate', 'inconclusive']

/**
 * Modal form for recording a new decision. Status + optional comment.
 *
 * Resets `comment` when the dialog reopens (so a previous draft does
 * not leak into a new decision). Status is preserved across opens as
 * a reasonable default — most analysts iterate through the same
 * status during a session.
 *
 * Uses the "derived state from props" trick (mirrors GuardrailEditor)
 * to reset comment without an effect-driven setState, which ESLint's
 * react-hooks/set-state-in-effect rule rejects.
 */
export default function DecisionForm({ open, onOpenChange, onSubmit, submitting }) {
  const { t } = useTranslation()
  const [status, setStatus] = useState('iterate')
  const [comment, setComment] = useState('')
  const [lastOpen, setLastOpen] = useState(open)

  // Re-initialise when the dialog transitions closed → open. The
  // unconditional setState below is fine — it runs only on the render
  // where `open` differs from what we last saw, not in an effect.
  if (open !== lastOpen) {
    setLastOpen(open)
    if (open) {
      setComment('')
    }
  }

  const submit = () => {
    onSubmit({
      status,
      comment: comment.trim() ? comment.trim() : null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('decisions.formTitle')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="d-status">{t('decisions.statusLabel')}</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger id="d-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {t(`decisions.${s}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="d-comment">{t('decisions.commentLabel')}</Label>
            <textarea
              id="d-comment"
              rows={4}
              value={comment}
              placeholder={t('decisions.commentPlaceholder')}
              onChange={(e) => setComment(e.target.value)}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="text-xs text-muted-foreground">
              {t('decisions.commentHelp')}
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={submit} disabled={submitting}>
            {t('decisions.record')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}