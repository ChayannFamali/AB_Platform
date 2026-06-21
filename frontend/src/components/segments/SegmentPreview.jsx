import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Play } from 'lucide-react'

import { evaluateSegment } from '../../api/client'
import { Button } from '../ui/button'
import { Label } from '../ui/label'
import { Alert, AlertDescription } from '../ui/alert'
import { Badge } from '../ui/badge'

/**
 * Dry-run a segment against a hypothetical user_properties payload.
 * Calls `POST /segments/{id}/evaluate` and renders the per-rule
 * breakdown returned by the backend so the user can see *why* the
 * segment does or doesn't match.
 */
export default function SegmentPreview({ segmentId }) {
  const { t } = useTranslation()
  const [rawProps, setRawProps] = useState('{\n  "country": "DE",\n  "plan": "pro"\n}')
  const [result, setResult] = useState(null)

  const evalMutation = useMutation({
    mutationFn: async () => {
      let parsed
      try {
        parsed = JSON.parse(rawProps || '{}')
      } catch {
        throw new Error(t('segments.previewInvalidJson'))
      }
      return evaluateSegment(segmentId, parsed)
    },
    onSuccess: (data) => setResult({ ok: true, data }),
    onError: (err) => setResult({ ok: false, error: err.message }),
  })

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="preview-props">{t('segments.previewPropsLabel')}</Label>
        <textarea
          id="preview-props"
          className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
          rows={5}
          value={rawProps}
          onChange={(e) => setRawProps(e.target.value)}
        />
      </div>
      <Button
        size="sm"
        onClick={() => evalMutation.mutate()}
        disabled={evalMutation.isPending}
      >
        <Play className="mr-1 h-4 w-4" />
        {t('segments.previewRun')}
      </Button>

      {result?.ok && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{t('segments.previewResult')}:</span>
            {result.data.matches ? (
              <Badge variant="success">{t('segments.previewMatches')}</Badge>
            ) : (
              <Badge variant="destructive">{t('segments.previewNoMatch')}</Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {t('segments.previewMatchedCount', {
                matched: result.data.matched_rules,
                total: result.data.total_rules,
              })}
            </span>
          </div>
          <ul className="divide-y rounded border text-xs">
            {(result.data.per_rule || []).map((r, i) => (
              <li key={i} className="flex items-center justify-between px-3 py-1.5">
                <span className="font-mono">
                  {r.field} {r.operator} {JSON.stringify(r.expected)}
                </span>
                {r.matched ? (
                  <Badge variant="secondary">{t('segments.previewRuleMatch')}</Badge>
                ) : (
                  <Badge variant="outline">{t('segments.previewRuleNoMatch')}</Badge>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {result && !result.ok && (
        <Alert variant="destructive">
          <AlertDescription>{result.error}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
