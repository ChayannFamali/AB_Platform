import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'

import { createExperiment } from '../api/client'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../components/ui/card'
import { Checkbox } from '../components/ui/checkbox'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import SampleSizeCalculator from '../components/wizard/SampleSizeCalculator'
import WizardStep from '../components/wizard/WizardStep'
import WizardStepper from '../components/wizard/WizardStepper'
import { PageHeader } from '../components/PageContainer'
import { toast } from '../hooks/use-toast'

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
  is_sequential: false,
}

const isRatioType = (type) => type === 'revenue' || type === 'duration'

export default function CreateExperimentWizard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [stepIndex, setStepIndex] = useState(0)
  const [form, setForm] = useState(DEFAULT_FORM)

  const steps = useMemo(
    () => [
      { key: 'basics',   title: t('wizard.step1') },
      { key: 'variants', title: t('wizard.step2') },
      { key: 'metrics',  title: t('wizard.step3') },
      { key: 'review',   title: t('wizard.step4') },
      { key: 'settings', title: t('wizard.step5') },
    ],
    [t],
  )

  const validation = useMemo(() => validateStep(stepIndex, form), [stepIndex, form])

  const createMutation = useMutation({
    mutationFn: () => submitForm(form),
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

  const handleNext = () => {
    if (stepIndex < steps.length - 1) {
      setStepIndex(stepIndex + 1)
    } else {
      createMutation.mutate()
    }
  }

  const handleBack = () => {
    if (stepIndex > 0) setStepIndex(stepIndex - 1)
  }

  return (
    <>
      <PageHeader title={t('experiments.create.title')} />

      <WizardStepper steps={steps} currentIndex={stepIndex} />

      {stepIndex === 0 && (
        <Step1
          form={form}
          setForm={setForm}
          onBack={handleBack}
          onNext={handleNext}
          isNextDisabled={!validation.ok}
          error={validation.error}
        />
      )}
      {stepIndex === 1 && (
        <Step2
          form={form}
          setForm={setForm}
          onBack={handleBack}
          onNext={handleNext}
          isNextDisabled={!validation.ok}
          error={validation.error}
        />
      )}
      {stepIndex === 2 && (
        <Step3
          form={form}
          setForm={setForm}
          onBack={handleBack}
          onNext={handleNext}
          isNextDisabled={!validation.ok}
          error={validation.error}
        />
      )}
      {stepIndex === 3 && (
        <Step4
          form={form}
          setForm={setForm}
          onBack={handleBack}
          onNext={handleNext}
        />
      )}
      {stepIndex === 4 && (
        <Step5
          form={form}
          onBack={handleBack}
          onNext={handleNext}
          isSubmitting={createMutation.isLoading}
        />
      )}
    </>
  )
}

// ── Step 1: Basics ─────────────────────────────────────────────────────────

function Step1({ form, setForm, onBack, onNext, isNextDisabled, error }) {
  const { t } = useTranslation()
  return (
    <WizardStep
      title={t('experiments.create.basics')}
      onBack={onBack}
      onNext={onNext}
      isFirst
      isNextDisabled={isNextDisabled}
      error={error}
    >
      <Card>
        <CardContent className="space-y-4 pt-4">
          <div className="space-y-1.5">
            <Label htmlFor="w-name">
              {t('experiments.create.name')} *
            </Label>
            <Input
              id="w-name"
              required
              placeholder={t('experiments.create.namePlaceholder')}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="w-desc">
              {t('experiments.create.description')}
            </Label>
            <textarea
              id="w-desc"
              rows={3}
              placeholder={t('experiments.create.descriptionPlaceholder')}
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="w-traffic">
              {t('experiments.create.trafficPercentage')}
            </Label>
            <Input
              id="w-traffic"
              type="number"
              min={1}
              max={100}
              value={form.traffic_percentage}
              onChange={(e) =>
                setForm({ ...form, traffic_percentage: e.target.value })
              }
            />
          </div>
        </CardContent>
      </Card>
    </WizardStep>
  )
}

// ── Step 2: Variants ───────────────────────────────────────────────────────

function Step2({ form, setForm, onBack, onNext, isNextDisabled, error }) {
  const { t } = useTranslation()

  const updateVariant = (i, field, value) => {
    const variants = [...form.variants]
    variants[i] = { ...variants[i], [field]: value }
    setForm({ ...form, variants })
  }

  const addVariant = () =>
    setForm({
      ...form,
      variants: [
        ...form.variants,
        { name: `variant_${form.variants.length + 1}`, traffic_split: 0 },
      ],
    })

  const removeVariant = (i) => {
    if (form.variants.length <= 2) return
    setForm({
      ...form,
      variants: form.variants.filter((_, idx) => idx !== i),
    })
  }

  return (
    <WizardStep
      title={t('experiments.create.variants')}
      description={t('experiments.create.weightSumHint')}
      onBack={onBack}
      onNext={onNext}
      isNextDisabled={isNextDisabled}
      error={error}
    >
      <Card>
        <CardContent className="space-y-4 pt-4">
          {form.variants.map((v, i) => (
            <div
              key={i}
              className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_120px_40px]"
            >
              <div className="space-y-1.5">
                <Label htmlFor={`w-vname-${i}`}>
                  {t('experiments.create.variantName')}
                </Label>
                <Input
                  id={`w-vname-${i}`}
                  value={v.name}
                  onChange={(e) => updateVariant(i, 'name', e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`w-vsplit-${i}`}>
                  {t('experiments.create.weight')}
                </Label>
                <Input
                  id={`w-vsplit-${i}`}
                  type="number"
                  min={0}
                  max={100}
                  value={v.traffic_split}
                  onChange={(e) => updateVariant(i, 'traffic_split', e.target.value)}
                />
              </div>
              <div className="flex items-end">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeVariant(i)}
                  disabled={form.variants.length <= 2}
                  aria-label="Remove variant"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addVariant}
          >
            <Plus className="mr-1 h-4 w-4" />
            {t('experiments.create.addVariant')}
          </Button>
        </CardContent>
      </Card>
    </WizardStep>
  )
}

// ── Step 3: Metrics (+ inline sample-size calc) ────────────────────────────

function Step3({ form, setForm, onBack, onNext, isNextDisabled, error }) {
  const { t } = useTranslation()

  const updateMetric = (i, field, value) => {
    const metrics = [...form.metrics]
    let updated = { ...metrics[i], [field]: value }
    if (field === 'metric_type' && value === 'conversion') {
      updated.denominator_event_name = null
    }
    if (field === 'is_primary' && value === true) {
      metrics.forEach((m, j) => {
        if (j !== i) m.is_primary = false
      })
    }
    metrics[i] = updated
    setForm({ ...form, metrics })
  }

  const addMetric = () =>
    setForm({
      ...form,
      metrics: [...form.metrics, { ...DEFAULT_METRIC, is_primary: false }],
    })

  const removeMetric = (i) => {
    if (form.metrics.length <= 1) return
    setForm({
      ...form,
      metrics: form.metrics.filter((_, idx) => idx !== i),
    })
  }

  const primaryMetrics = form.metrics.filter((m) => m.is_primary)
  const showCalculator = primaryMetrics.some(
    (m) => m.metric_type && m.name,
  )

  return (
    <WizardStep
      title={t('experiments.create.metrics')}
      onBack={onBack}
      onNext={onNext}
      isNextDisabled={isNextDisabled}
      error={error}
    >
      <Card>
        <CardContent className="space-y-6 pt-4">
          {form.metrics.map((m, i) => (
            <div
              key={i}
              className={i > 0 ? 'space-y-4 border-t pt-4' : 'space-y-4'}
            >
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor={`w-mname-${i}`}>
                    {t('experiments.create.metricName')} *
                  </Label>
                  <Input
                    id={`w-mname-${i}`}
                    required
                    placeholder={t('experiments.create.metricNamePlaceholder')}
                    value={m.name}
                    onChange={(e) => updateMetric(i, 'name', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`w-mtype-${i}`}>
                    {t('experiments.create.metricType')}
                  </Label>
                  <select
                    id={`w-mtype-${i}`}
                    value={m.metric_type}
                    onChange={(e) => updateMetric(i, 'metric_type', e.target.value)}
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

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor={`w-mevt-${i}`}>
                    {t('experiments.create.eventName')} *
                  </Label>
                  <Input
                    id={`w-mevt-${i}`}
                    required
                    placeholder="button_click"
                    value={m.event_name}
                    onChange={(e) => updateMetric(i, 'event_name', e.target.value)}
                  />
                </div>
                {isRatioType(m.metric_type) && (
                  <div className="space-y-1.5">
                    <Label htmlFor={`w-mdenom-${i}`}>
                      {t('experiments.create.denominator')}
                    </Label>
                    <Input
                      id={`w-mdenom-${i}`}
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

              <div className="flex flex-wrap items-center gap-6">
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

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addMetric}
          >
            <Plus className="mr-1 h-4 w-4" />
            {t('experiments.create.addMetric')}
          </Button>
        </CardContent>
      </Card>

      {showCalculator && (
        <div className="mt-4">
          <SampleSizeCalculator />
        </div>
      )}
    </WizardStep>
  )
}

// ── Step 4: Settings (M-007) ─────────────────────────────────────────────

function Step4({ form, setForm, onBack, onNext }) {
  const { t } = useTranslation()
  return (
    <WizardStep
      title={t('wizard.settings.title')}
      description={t('wizard.settings.description')}
      onBack={onBack}
      onNext={onNext}
    >
      <Card>
        <CardContent className="space-y-6 pt-4">
          <label className="flex items-start gap-3">
            <Checkbox
              checked={form.is_sequential}
              onCheckedChange={(checked) =>
                setForm({ ...form, is_sequential: !!checked })
              }
            />
            <div className="space-y-1">
              <div className="text-sm font-medium">
                {t('wizard.settings.sequential')}
              </div>
              <p className="text-xs text-muted-foreground">
                {t('wizard.settings.sequentialHelp')}
              </p>
            </div>
          </label>

          <div className="rounded-md border border-dashed bg-muted/40 p-3">
            <div className="text-sm font-medium">
              {t('wizard.settings.holdout')}
            </div>
            <p className="text-xs text-muted-foreground">
              {t('wizard.settings.holdoutHelp')}
            </p>
          </div>
        </CardContent>
      </Card>
    </WizardStep>
  )
}

// ── Step 5: Review ─────────────────────────────────────────────────────────

function Step5({ form, onBack, onNext, isSubmitting }) {
  const { t } = useTranslation()
  return (
    <WizardStep
      title={t('wizard.review.title')}
      description={t('wizard.review.description')}
      onBack={onBack}
      onNext={onNext}
      isLast
      isSubmitting={isSubmitting}
      nextLabel={t('experiments.create.submit')}
      backLabel={t('wizard.back')}
    >
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t('experiments.create.basics')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label={t('experiments.create.name')} value={form.name} />
            <Row
              label={t('experiments.create.description')}
              value={form.description || '—'}
            />
            <Row
              label={t('experiments.create.trafficPercentage')}
              value={`${form.traffic_percentage}%`}
            />
            <Row
              label={t('experiments.detail.sequential')}
              value={
                form.is_sequential ? (
                  <Badge variant="info">
                    {t('experiments.detail.sequentialOn')}
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">
                    {t('experiments.detail.sequentialOff')}
                  </span>
                )
              }
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t('experiments.create.variants')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {form.variants.map((v, i) => (
              <div key={i} className="flex justify-between">
                <span className="font-medium">{v.name}</span>
                <span className="text-muted-foreground">
                  {v.traffic_split}%
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t('experiments.create.metrics')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {form.metrics.map((m, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded border bg-muted/40 px-3 py-2"
              >
                <div>
                  <div className="font-medium">{m.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {m.metric_type} · event: <code>{m.event_name}</code>
                    {m.denominator_event_name && (
                      <> · denom: <code>{m.denominator_event_name}</code></>
                    )}
                  </div>
                </div>
                <div className="flex gap-1">
                  {m.is_primary && (
                    <Badge variant="success">Primary</Badge>
                  )}
                  {m.is_guardrail && (
                    <Badge variant="warning">Guardrail</Badge>
                  )}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </WizardStep>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

// ── Validation & submit ────────────────────────────────────────────────────

function validateStep(stepIndex, form) {
  if (stepIndex === 0) {
    if (!form.name || form.name.trim() === '') {
      return { ok: false, error: 'Name is required' }
    }
    const tp = Number(form.traffic_percentage)
    if (!Number.isFinite(tp) || tp <= 0 || tp > 100) {
      return { ok: false, error: 'Traffic % must be between 1 and 100' }
    }
    return { ok: true, error: null }
  }
  if (stepIndex === 1) {
    if (form.variants.length < 2) {
      return { ok: false, error: 'At least two variants are required' }
    }
    const emptyName = form.variants.find(
      (v) => !v.name || v.name.trim() === '',
    )
    if (emptyName) {
      return { ok: false, error: 'Every variant must have a name' }
    }
    const total = form.variants.reduce(
      (acc, v) => acc + Number(v.traffic_split || 0),
      0,
    )
    if (Math.abs(total - 100) > 0.01) {
      return {
        ok: false,
        error: `Sum of weights must be 100% (got ${total}%)`,
      }
    }
    return { ok: true, error: null }
  }
  if (stepIndex === 2) {
    if (form.metrics.length < 1) {
      return { ok: false, error: 'At least one metric is required' }
    }
    const incomplete = form.metrics.find(
      (m) => !m.name || !m.event_name,
    )
    if (incomplete) {
      return { ok: false, error: 'Every metric needs a name and event_name' }
    }
    const primaryCount = form.metrics.filter((m) => m.is_primary).length
    if (primaryCount !== 1) {
      return { ok: false, error: 'Exactly one metric must be primary' }
    }
    if (
      form.metrics.some(
        (m) => m.metric_type === 'conversion' && m.denominator_event_name,
      )
    ) {
      return {
        ok: false,
        error: 'Conversion metrics cannot have a denominator',
      }
    }
    return { ok: true, error: null }
  }
  return { ok: true, error: null }
}

function submitForm(form) {
  return createExperiment({
    name: form.name,
    description: form.description || null,
    traffic_percentage: Number(form.traffic_percentage),
    is_sequential: !!form.is_sequential,
    variants: form.variants.map((v) => ({
      name: v.name,
      traffic_split: Number(v.traffic_split),
    })),
    metrics: form.metrics.map((m) => ({
      name: m.name,
      event_name: m.event_name,
      denominator_event_name: m.denominator_event_name || null,
      metric_type: m.metric_type,
      is_primary: m.is_primary,
      is_guardrail: m.is_guardrail,
    })),
  })
}
