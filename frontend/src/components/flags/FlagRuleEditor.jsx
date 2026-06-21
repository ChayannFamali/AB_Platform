import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'

import { addFlagRule, deleteFlagRule, getSegments } from '../../api/client'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Alert, AlertDescription } from '../ui/alert'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select'
import { toast } from '../../hooks/use-toast'

/**
 * Rule editor for a flag. M-010 adds an optional segment selector —
 * rules with a segment act as overrides for users matching that
 * segment; rules without one (segment_id === "") are the
 * "default for everyone" override, ordered by priority.
 */
export default function FlagRuleEditor({ flag }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [rollout, setRollout] = useState(0)
  const [priority, setPriority] = useState(0)
  // Sentinel value "" means "no segment" (acts as default-for-everyone
  // override). shadcn Select doesn't accept null directly.
  const [segmentId, setSegmentId] = useState('')

  const { data: segmentsData } = useQuery({
    queryKey: ['segments'],
    queryFn: () => getSegments({ limit: 100 }),
  })
  const segments = segmentsData?.items || []

  const addMutation = useMutation({
    mutationFn: () => addFlagRule(flag.id, {
      rollout_percentage: rollout,
      priority,
      enabled: true,
      segment_id: segmentId || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flag', flag.id] })
      setRollout(0)
      setPriority(0)
      setSegmentId('')
      toast({ description: t('flags.ruleAdded') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const removeMutation = useMutation({
    mutationFn: (ruleId) => deleteFlagRule(flag.id, ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flag', flag.id] })
      toast({ description: t('flags.ruleRemoved') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  const rules = flag.rules || []

  // Helper for showing a human-readable segment name (or "All users")
  // for existing rules — the rule response only carries the segment_id.
  const segmentNameById = (id) => {
    if (!id) return t('flags.ruleSegmentAllUsers')
    const seg = segments.find((s) => s.id === id)
    return seg ? `${seg.key} (${seg.name})` : t('flags.ruleSegmentAllUsers')
  }

  return (
    <div className="space-y-3">
      <div className="rounded border bg-muted/30 p-3 text-xs text-muted-foreground">
        {t('flags.rulesHelp')}
      </div>

      {rules.length > 0 && (
        <ul className="divide-y rounded border">
          {rules.map((rule) => (
            <li
              key={rule.id}
              className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
            >
              <span className="space-x-2">
                <span className="font-mono">{rule.priority}</span>
                <span className="text-muted-foreground">·</span>
                <span>{segmentNameById(rule.segment_id)}</span>
                <span className="text-muted-foreground">·</span>
                <span>{t('flags.ruleRollout', { pct: rule.rollout_percentage })}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeMutation.mutate(rule.id)}
                disabled={removeMutation.isPending}
                aria-label={t('flags.ruleRemove')}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[180px] flex-1 space-y-1">
          <Label htmlFor="rule-segment">{t('flags.ruleSegmentLabel')}</Label>
          <Select value={segmentId} onValueChange={setSegmentId}>
            <SelectTrigger id="rule-segment">
              <SelectValue placeholder={t('flags.ruleSegmentAllUsers')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">{t('flags.ruleSegmentAllUsers')}</SelectItem>
              {segments.map((s) => (
                <SelectItem key={s.id} value={s.id}>{s.key} — {s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-24 space-y-1">
          <Label htmlFor="rule-rollout">{t('flags.ruleRolloutLabel')}</Label>
          <Input
            id="rule-rollout"
            type="number"
            min={0}
            max={100}
            step={1}
            value={rollout}
            onChange={(e) => setRollout(Number(e.target.value))}
            disabled={addMutation.isPending}
          />
        </div>
        <div className="w-20 space-y-1">
          <Label htmlFor="rule-priority">{t('flags.rulePriority')}</Label>
          <Input
            id="rule-priority"
            type="number"
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            disabled={addMutation.isPending}
          />
        </div>
        <Button
          onClick={() => addMutation.mutate()}
          disabled={addMutation.isPending || rollout < 0 || rollout > 100}
        >
          <Plus className="mr-1 h-4 w-4" />
          {t('flags.ruleAdd')}
        </Button>
      </div>

      {rules.length === 0 && (
        <Alert>
          <AlertDescription>{t('flags.rulesEmpty')}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
