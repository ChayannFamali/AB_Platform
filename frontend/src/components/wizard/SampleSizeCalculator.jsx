import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Calculator, Loader2 } from 'lucide-react'

import {
  getSampleSizeContinuous,
  getSampleSizeConversion,
} from '../../api/client'
import { Alert, AlertDescription } from '../ui/alert'
import { Button } from '../ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../ui/card'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'

/**
 * Reusable sample size calculator with two modes:
 * - `conversion` — for binary metrics (clicked / didn't click)
 * - `continuous` — for revenue, duration, etc.
 *
 * Used in:
 * - The standalone page at /tools/sample-size
 * - Step 3 of the Create Experiment Wizard
 *
 * Each call to either `getSampleSizeConversion` or `getSampleSizeContinuous`
 * returns the per-variant N, total N, and `days_needed` if `daily_traffic`
 * is provided. Errors (validation 400s, network) are caught and rendered
 * inline.
 */
export default function SampleSizeCalculator() {
  const { t } = useTranslation()

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Calculator className="h-4 w-4" />
          {t('sampleSize.title')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="conversion">
          <TabsList className="mb-4">
            <TabsTrigger value="conversion">
              {t('sampleSize.conversion')}
            </TabsTrigger>
            <TabsTrigger value="continuous">
              {t('sampleSize.continuous')}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="conversion">
            <ConversionForm />
          </TabsContent>
          <TabsContent value="continuous">
            <ContinuousForm />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

// ── Conversion ────────────────────────────────────────────────────────────

function ConversionForm() {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    baseline_rate: '',
    mde: '',
    daily_traffic: '',
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const update = (key, value) => setForm({ ...form, [key]: value })

  const handleCalc = async () => {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const params = {
        baseline_rate: parseFloat(form.baseline_rate),
        mde: parseFloat(form.mde),
      }
      if (form.daily_traffic) {
        params.daily_traffic = parseInt(form.daily_traffic, 10)
      }
      const { data } = await getSampleSizeConversion(params)
      setResult(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : detail || t('sampleSize.error'),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field
          id="ss-baseline"
          label={t('sampleSize.baselineRate')}
          hint={t('sampleSize.baselineHint')}
        >
          <Input
            id="ss-baseline"
            type="number"
            step="0.001"
            placeholder="0.032"
            value={form.baseline_rate}
            onChange={(e) => update('baseline_rate', e.target.value)}
          />
        </Field>
        <Field
          id="ss-mde"
          label={t('sampleSize.mde')}
          hint={t('sampleSize.mdeHint')}
        >
          <Input
            id="ss-mde"
            type="number"
            step="0.001"
            placeholder="0.005"
            value={form.mde}
            onChange={(e) => update('mde', e.target.value)}
          />
        </Field>
      </div>
      <Field
        id="ss-traffic"
        label={t('sampleSize.dailyTraffic')}
        hint={t('sampleSize.dailyTrafficHint')}
      >
        <Input
          id="ss-traffic"
          type="number"
          placeholder="10000"
          value={form.daily_traffic}
          onChange={(e) => update('daily_traffic', e.target.value)}
        />
      </Field>
      <Button
        onClick={handleCalc}
        disabled={loading || !form.baseline_rate || !form.mde}
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {t('sampleSize.calculate')}
      </Button>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && <ResultPanel result={result} />}
    </div>
  )
}

// ── Continuous (revenue / duration) ──────────────────────────────────────

function ContinuousForm() {
  const { t } = useTranslation()
  const [form, setForm] = useState({
    baseline_mean: '',
    baseline_std: '',
    mde_absolute: '',
    daily_traffic: '',
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const update = (key, value) => setForm({ ...form, [key]: value })

  const handleCalc = async () => {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const params = {
        baseline_mean: parseFloat(form.baseline_mean),
        baseline_std: parseFloat(form.baseline_std),
        mde_absolute: parseFloat(form.mde_absolute),
      }
      if (form.daily_traffic) {
        params.daily_traffic = parseInt(form.daily_traffic, 10)
      }
      const { data } = await getSampleSizeContinuous(params)
      setResult(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join(', ')
          : detail || t('sampleSize.error'),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field
          id="css-mean"
          label={t('sampleSize.baselineMean')}
          hint={t('sampleSize.meanHint')}
        >
          <Input
            id="css-mean"
            type="number"
            step="0.01"
            placeholder="120"
            value={form.baseline_mean}
            onChange={(e) => update('baseline_mean', e.target.value)}
          />
        </Field>
        <Field
          id="css-std"
          label={t('sampleSize.baselineStd')}
          hint={t('sampleSize.stdHint')}
        >
          <Input
            id="css-std"
            type="number"
            step="0.01"
            placeholder="50"
            value={form.baseline_std}
            onChange={(e) => update('baseline_std', e.target.value)}
          />
        </Field>
        <Field
          id="css-mde"
          label={t('sampleSize.mdeAbsolute')}
          hint={t('sampleSize.mdeAbsoluteHint')}
        >
          <Input
            id="css-mde"
            type="number"
            step="0.01"
            placeholder="5"
            value={form.mde_absolute}
            onChange={(e) => update('mde_absolute', e.target.value)}
          />
        </Field>
      </div>
      <Field
        id="css-traffic"
        label={t('sampleSize.dailyTraffic')}
        hint={t('sampleSize.dailyTrafficHint')}
      >
        <Input
          id="css-traffic"
          type="number"
          placeholder="10000"
          value={form.daily_traffic}
          onChange={(e) => update('daily_traffic', e.target.value)}
        />
      </Field>
      <Button
        onClick={handleCalc}
        disabled={
          loading ||
          !form.baseline_mean ||
          !form.baseline_std ||
          !form.mde_absolute
        }
      >
        {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {t('sampleSize.calculate')}
      </Button>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && <ResultPanel result={result} />}
    </div>
  )
}

// ── Shared bits ───────────────────────────────────────────────────────────

function Field({ id, label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function ResultPanel({ result }) {
  const { t } = useTranslation()
  return (
    <Alert variant="info">
      <AlertDescription className="space-y-2">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat
            label={t('sampleSize.perVariant')}
            value={result.sample_size_per_variant.toLocaleString()}
          />
          <Stat
            label={t('sampleSize.total')}
            value={result.total_sample_size.toLocaleString()}
          />
          {result.days_needed != null && (
            <Stat
              label={t('sampleSize.days')}
              value={result.days_needed}
            />
          )}
          <Stat label={t('sampleSize.alpha')} value={result.alpha} />
          <Stat label={t('sampleSize.power')} value={result.power} />
        </div>
        <p className="text-sm text-muted-foreground">
          {t('sampleSize.explanation', {
            perVariant: result.sample_size_per_variant.toLocaleString(),
            total: result.total_sample_size.toLocaleString(),
            from: result.baseline_rate,
            to: result.target_rate,
            alpha: result.alpha,
            power: result.power,
          })}
        </p>
      </AlertDescription>
    </Alert>
  )
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-base font-semibold">{value}</div>
    </div>
  )
}
