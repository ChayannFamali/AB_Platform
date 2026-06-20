import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { toggleFlag } from '../../api/client'
import { Switch } from '../ui/switch'
import { toast } from '../../hooks/use-toast'

/**
 * Optimistic kill-switch toggle.
 * Flips the local value immediately; on error it rolls back and shows a toast.
 */
export default function FlagToggle({ flag, disabled = false }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (enabled) => toggleFlag(flag.id, enabled),
    onMutate: async (enabled) => {
      await queryClient.cancelQueries({ queryKey: ['flags'] })
      const previous = queryClient.getQueryData(['flags'])
      queryClient.setQueryData(['flags'], (old) => {
        if (!old) return old
        return {
          ...old,
          items: old.items.map((f) =>
            f.id === flag.id ? { ...f, enabled } : f,
          ),
          summary: old.summary && {
            ...old.summary,
            enabled_total:
              old.summary.enabled_total + (enabled ? 1 : -1),
            disabled_total:
              old.summary.disabled_total + (enabled ? -1 : 1),
          },
        }
      })
      return { previous }
    },
    onError: (err, _enabled, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['flags'], context.previous)
      }
      toast({
        variant: 'destructive',
        description:
          err.response?.data?.detail || t('errors.serverError'),
      })
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['flags'] })
      queryClient.invalidateQueries({ queryKey: ['flag', flag.id] })
    },
  })

  return (
    <Switch
      checked={flag.enabled}
      onCheckedChange={(next) => mutation.mutate(next)}
      disabled={disabled || mutation.isPending}
      aria-label={t('flags.killSwitch')}
    />
  )
}