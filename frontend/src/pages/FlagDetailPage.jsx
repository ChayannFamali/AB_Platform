import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'

import {
  getFlagByKey,
  updateFlag,
} from '../api/client'
import { Button } from '../components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Alert, AlertDescription } from '../components/ui/alert'
import FlagToggle from '../components/flags/FlagToggle'
import FlagStatusBadge from '../components/flags/FlagStatusBadge'
import FlagRuleEditor from '../components/flags/FlagRuleEditor'
import RolloutSlider from '../components/flags/RolloutSlider'
import LoadingState from '../components/LoadingState'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

export default function FlagDetailPage() {
  const { t } = useTranslation()
  const { key } = useParams()
  const decodedKey = decodeURIComponent(key || '')
  const queryClient = useQueryClient()

  const flagQuery = useQuery({
    queryKey: ['flag', decodedKey],
    queryFn: () => getFlagByKey(decodedKey),
    enabled: Boolean(decodedKey),
  })

  // Local form state mirrors the server value until the user edits.
  const flag = flagQuery.data
  const updateMutation = useMutation({
    mutationFn: ({ name, description, rollout_percentage }) =>
      updateFlag(flag.id, { name, description, rollout_percentage }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flag', decodedKey] })
      queryClient.invalidateQueries({ queryKey: ['flags'] })
      toast({ description: t('flags.updated') })
    },
    onError: (err) => toast({
      variant: 'destructive',
      description: err.response?.data?.detail || t('errors.serverError'),
    }),
  })

  if (flagQuery.isLoading) return <LoadingState variant="skeleton" count={3} />
  if (flagQuery.isError || !flag) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {flagQuery.error?.response?.status === 404
            ? t('flags.notFound')
            : t('errors.serverError')}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <>
      <PageHeader
        title={flag.name}
        description={
          <span className="flex items-center gap-2">
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {flag.key}
            </code>
            <FlagStatusBadge flag={flag} />
          </span>
        }
        actions={
          <Button asChild variant="ghost" size="sm">
            <Link to="/flags">
              <ChevronLeft className="mr-1 h-4 w-4" />
              {t('common.back')}
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t('flags.config')}</CardTitle>
            <CardDescription>{t('flags.configHelp')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>{t('flags.killSwitch')}</Label>
              <FlagToggle flag={flag} />
            </div>

            <div className="space-y-1">
              <Label htmlFor="flag-name-input">{t('flags.nameLabel')}</Label>
              <Input
                id="flag-name-input"
                defaultValue={flag.name}
                onBlur={(e) => {
                  if (e.target.value !== flag.name) {
                    updateMutation.mutate({
                      name: e.target.value,
                      description: flag.description || '',
                      rollout_percentage: flag.rollout_percentage,
                    })
                  }
                }}
                disabled={updateMutation.isPending}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="flag-desc-input">{t('flags.description')}</Label>
              <Input
                id="flag-desc-input"
                defaultValue={flag.description || ''}
                onBlur={(e) => {
                  if (e.target.value !== (flag.description || '')) {
                    updateMutation.mutate({
                      name: flag.name,
                      description: e.target.value,
                      rollout_percentage: flag.rollout_percentage,
                    })
                  }
                }}
                disabled={updateMutation.isPending}
              />
            </div>

            <div className="space-y-1">
              <Label>{t('flags.rollout')}</Label>
              <RolloutSlider
                value={flag.rollout_percentage}
                onChange={(next) => {
                  if (next !== flag.rollout_percentage) {
                    updateMutation.mutate({
                      name: flag.name,
                      description: flag.description || '',
                      rollout_percentage: next,
                    })
                  }
                }}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t('flags.rules')}</CardTitle>
            <CardDescription>{t('flags.rulesDescription')}</CardDescription>
          </CardHeader>
          <CardContent>
            <FlagRuleEditor flag={flag} />
          </CardContent>
        </Card>
      </div>
    </>
  )
}