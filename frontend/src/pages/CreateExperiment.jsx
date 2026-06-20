import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus } from 'lucide-react'

import { createExperiment, getSampleSizeConversion } from '../api/client'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Checkbox } from '../components/ui/checkbox'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card'
import { Alert, AlertDescription } from '../components/ui/alert'
import { toast } from '../hooks/use-toast'
import { PageHeader } from '../components/PageContainer'

const DEFAULT_METRIC = {
  name: '',
  event_name: '',
  denominator_event_name: null,
  metric_type: 'conversion',
  is_primary: true,
  is_guardrail: false,
}

const DEFAULT_FORM = {
  name: '',
  description: '',
  traffic_percentage: 100,
  variants: [
    { name: 'control', traffic_split: 50 },
    { name: 'treatment', traffic_split: 50 },
  ],
  metrics: [{ ...DEFAULT_METRIC }],
}

export default function CreateExperiment() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [form, setForm] = useState(DEFAULT_FORM)
  const [sampleSize, setSampleSize] = useState(null)
  const [calc, setCalc] = useState({
    baseline_rate: '',
    mde: '',
    daily_traffic: '',
  })
  const [calcError, setCalcError] = useState('')

  const updateMetric = (i, field, value) => {
    const metrics = [...form.metrics]
    let updated = { ...metrics[i], [field]: value }
    if (field === 'metric_type' && value === 'conversion') {
      updated.denominator_event_name = null
    }
    metrics[i] = updated
    setForm({ ...form, metrics })
  }

  const addMetric = () =>
    setForm({
      ...form,
      metrics: [...form.metrics, { ...DEFAULT_METRIC, is_primary: false }],
    })

  const removeMetric = (i) =>
    setForm({
      ...form,
      metrics: form.metrics.filter((_, idx) => idx !== i),
    })

  const calcSampleSize = async () => {
    setCalcError('')
    setSampleSize(null)

    const baselineRate = parseFloat(calc.baseline_rate)
    const mde = parseFloat(calc.mde)

    if (!calc.baseline_rate || !calc.mde) {
      setCalcError(t('experiments.create.errors.fillBaselineMde'))
      return
    }
    if (isNaN(baselineRate) || isNaN(mde)) {
      setCalcError(t('experiments.create.errors.numericValues'))
      return
    }
    if (baselineRate <= 0 || baselineRate >= 1) {
      setCalcError(t('experiments.create.errors.baselineRange'))
      return
    }
    if (mde <= 0 || mde >= 1) {
      setCalcError(t('experiments.create.errors.mdeRange'))
      return
    }
    if (baselineRate + mde > 1) {
      setCalcError(t('experiments.create.errors.baselinePlusMde'))
      return
    }

    try {
      const { data } = await getSampleSizeConversion({
        baseline_rate: baselineRate,
        mde,
        daily_traffic: calc.daily_traffic
          ? parseInt(calc.daily_traffic)
          : undefined,
      })
      setSampleSize(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      setCalcError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : detail || t('experiments.create.errors.calcFailed')
      )
    }
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createExperiment({
        ...form,
        traffic_percentage: Number(form.traffic_percentage),
        variants: form.variants.map((v) => ({
          ...v,
          traffic_split: Number(v.traffic_split),
        })),
        metrics: form.metrics.map((m) => ({
          ...m,
          denominator_event_name: m.denominator_event_name || null,
        })),
      }),
    onSuccess: (response) => {
      toast({ description: t('experiments.create.success') })
      navigate(`/experiments/${response.data.id}`)
    },
    onError: (err) => {
      const detail = err.response?.data?.detail
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(', ')
        : detail || t('experiments.create.failed')
      toast({ variant: 'destructive', description: msg })
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    createMutation.mutate()
  }

  const isRatioType = (type) => type === 'revenue' || type === 'duration'

  return (
    <>
      <PageHeader title={t('experiments.create.title')} />

      {/* Sample size calculator */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">
            {t('experiments.create.sampleSizeCalc')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>{t('experiments.create.baselineRate')}</Label>
              <Input
                type="number"
                step="0.001"
                placeholder="0.032"
                value={calc.baseline_rate}
                onChange={(e) =>
                  setCalc({ ...calc, baseline_rate: e.target.value })
                }
              />
              <p className="text-xs text-muted-foreground">
                {t('experiments.create.baselineHint')}
              </p>
            </div>
            <div className="space-y-2">
              <Label>{t('experiments.create.mde')}</Label>
              <Input
                type="number"
                step="0.001"
                placeholder="0.005"
                value={calc.mde}
                onChange={(e) => setCalc({ ...calc, mde: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                {t('experiments.create.mdeHint')}
              </p>
            </div>
          </div>
          <div className="space-y-2">
            <Label>{t('experiments.create.dailyTraffic')}</Label>
            <Input
              type="number"
              placeholder="500"
              value={calc.daily_traffic}
              onChange={(e) =>
                setCalc({ ...calc, daily_traffic: e.target.value })
              }
            />
          </div>
          <Button variant="secondary" onClick={calcSampleSize}>
            {t('experiments.create.calculate')}
          </Button>

          {calcError && (
            <Alert variant="warning">
              <AlertDescription>{calcError}</AlertDescription>
            </Alert>
          )}

          {sampleSize && (
            <Alert variant="info">
              <AlertDescription>
                <strong>{t('experiments.create.perVariant')}:</strong>{' '}
                {sampleSize.sample_size_per_variant.toLocaleString()}{' '}
                &nbsp;·&nbsp;
                <strong>{t('experiments.create.total')}:</strong>{' '}
                {sampleSize.total_sample_size.toLocaleString()}
                {sampleSize.days_needed && (
                  <span>
                    &nbsp;·&nbsp;
                    <strong>{t('experiments.create.days')}:</strong>{' '}
                    {sampleSize.days_needed}
                  </span>
                )}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basics */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t('experiments.create.basics')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t('experiments.create.name')} *</Label>
              <Input
                id="name"
                required
                placeholder={t('experiments.create.namePlaceholder')}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">
                {t('experiments.create.description')}
              </Label>
              <textarea
                id="description"
                rows={2}
                placeholder={t('experiments.create.descriptionPlaceholder')}
                className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="traffic">
                {t('experiments.create.trafficPercentage')}
              </Label>
              <Input
                id="traffic"
                type="number"
                min={1}
                max={100}
                value={form.traffic_percentage}
                onChange={(e) =>
                  setForm({
                    ...form,
                    traffic_percentage: e.target.value,
                  })
                }
              />
            </div>
          </CardContent>
        </Card>

        {/* Variants */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t('experiments.create.variants')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {form.variants.map((v, i) => (
              <div
                key={i}
                className="grid grid-cols-1 gap-4 sm:grid-cols-2"
              >
                <div className="space-y-2">
                  <Label>{t('experiments.create.variantName')}</Label>
                  <Input
                    value={v.name}
                    onChange={(e) => {
                      const variants = [...form.variants]
                      variants[i] = { ...variants[i], name: e.target.value }
                      setForm({ ...form, variants })
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('experiments.create.weight')}</Label>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={v.traffic_split}
                    onChange={(e) => {
                      const variants = [...form.variants]
                      variants[i] = {
                        ...variants[i],
                        traffic_split: e.target.value,
                      }
                      setForm({ ...form, variants })
                    }}
                  />
                </div>
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              {t('experiments.create.weightSumHint')}
            </p>
          </CardContent>
        </Card>

        {/* Metrics */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">
              {t('experiments.create.metrics')}
            </CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addMetric}
            >
              <Plus className="mr-1 h-4 w-4" />
              {t('experiments.create.addMetric')}
            </Button>
          </CardHeader>
          <CardContent className="space-y-6">
            {form.metrics.map((m, i) => (
              <div
                key={i}
                className={
                  i > 0
                    ? 'space-y-4 border-t pt-4'
                    : 'space-y-4'
                }
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>{t('experiments.create.metricName')} *</Label>
                    <Input
                      required
                      placeholder={t('experiments.create.metricNamePlaceholder')}
                      value={m.name}
                      onChange={(e) => updateMetric(i, 'name', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('experiments.create.metricType')}</Label>
                    <select
                      value={m.metric_type}
                      onChange={(e) =>
                        updateMetric(i, 'metric_type', e.target.value)
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="conversion">
                        {t('experiments.create.conversion')}
                      </option>
                      <option value="revenue">
                        {t('experiments.create.revenue')}
                      </option>
                      <option value="duration">
                        {t('experiments.create.duration')}
                      </option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>{t('experiments.create.eventName')} *</Label>
                    <Input
                      required
                      placeholder="button_click"
                      value={m.event_name}
                      onChange={(e) =>
                        updateMetric(i, 'event_name', e.target.value)
                      }
                    />
                  </div>
                  {isRatioType(m.metric_type) && (
                    <div className="space-y-2">
                      <Label>{t('experiments.create.denominator')}</Label>
                      <Input
                        placeholder="session_start"
                        value={m.denominator_event_name || ''}
                        onChange={(e) =>
                          updateMetric(
                            i,
                            'denominator_event_name',
                            e.target.value || null,
                          )
                        }
                      />
                    </div>
                  )}
                </div>

                {isRatioType(m.metric_type) && m.denominator_event_name && (
                  <Alert variant="success">
                    <AlertDescription>
                      <strong>{t('experiments.create.ratioBadge')}</strong> —{' '}
                      {t('experiments.create.ratioHint')}
                    </AlertDescription>
                  </Alert>
                )}

                <div className="flex items-center gap-6">
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={m.is_primary}
                      onCheckedChange={(checked) =>
                        updateMetric(i, 'is_primary', checked)
                      }
                    />
                    {t('experiments.create.primary')}
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={m.is_guardrail}
                      onCheckedChange={(checked) =>
                        updateMetric(i, 'is_guardrail', checked)
                      }
                    />
                    {t('experiments.create.guardrail')}
                  </label>
                  {form.metrics.length > 1 && (
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={() => removeMetric(i)}
                    >
                      {t('common.delete')}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Button type="submit" disabled={createMutation.isLoading}>
          {createMutation.isLoading
            ? t('common.loading')
            : t('experiments.create.submit')}
        </Button>
      </form>
    </>
  )
}