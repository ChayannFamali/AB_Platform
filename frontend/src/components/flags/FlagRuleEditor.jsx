import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'

import { addFlagRule, deleteFlagRule } from '../../api/client'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Alert, AlertDescription } from '../ui/alert'
import { toast } from '../../hooks/use-toast'

/**
 * Minimal rule editor. Rules are optional overrides — until M-010 lands
 * (Segments + Holdouts) all rules act as "default for everyone" with
 * priority ordering.
 *
 * `segment_id` is reserved for M-010; UI does not expose it yet.
 */
export default function FlagRuleEditor({ flag }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [rollout, setRollout] = useState(0)
  const [priority, setPriority] = useState(0)

  const addMutation = useMutation({
    mutationFn: () => addFlagRule(flag.id, {
      rollout_percentage: rollout,
      priority,
      enabled: true,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flag', flag.id] })
      setRollout(0)
      setPriority(0)
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
              <span>
                <span className="font-mono">{rule.priority}</span>
                {' · '}
                {t('flags.ruleRollout', { pct: rule.rollout_percentage })}
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

      <div className="flex items-end gap-2">
        <div className="flex-1 space-y-1">
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
        <div className="w-24 space-y-1">
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
          disabled={
            addMutation.isPending
            || rollout < 0
            || rollout > 100
          }
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