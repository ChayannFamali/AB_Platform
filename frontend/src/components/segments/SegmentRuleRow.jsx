import { useTranslation } from 'react-i18next'
import { Trash2 } from 'lucide-react'

import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Button } from '../ui/button'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select'

const OPERATORS = [
  'eq', 'neq', 'in', 'not_in',
  'gt', 'lt', 'gte', 'lte',
  'contains',
]

/**
 * Single rule row inside the segment builder. The operator select
 * switches the value input to the most useful shape for that operator
 * (multi-line JSON for `in` / `not_in`, plain text/number otherwise).
 *
 * Pure presentational component — `onChange(rule)` / `onRemove()` are
 * wired by the parent `SegmentBuilderPage`.
 */
export default function SegmentRuleRow({ rule, onChange, onRemove }) {
  const { t } = useTranslation()

  const setField   = (patch) => onChange({ ...rule, ...patch })
  const setValue   = (v)    => setField({ value: v })
  const setOp      = (op)   => {
    // If switching to/from `in` / `not_in`, normalise the value to an
    // array so the schema validation doesn't reject it on submit.
    const needsArray = ['in', 'not_in'].includes(op)
    const wasArray   = ['in', 'not_in'].includes(rule.operator)
    let nextValue = rule.value
    if (needsArray && !wasArray) {
      nextValue = Array.isArray(rule.value) ? rule.value : [rule.value]
    } else if (!needsArray && wasArray) {
      nextValue = Array.isArray(rule.value) && rule.value.length > 0
        ? rule.value[0] : ''
    }
    setField({ operator: op, value: nextValue })
  }

  const isList = ['in', 'not_in'].includes(rule.operator)
  const isNumeric = ['gt', 'lt', 'gte', 'lte'].includes(rule.operator)

  return (
    <div className="flex flex-wrap items-end gap-2 rounded border p-2">
      <div className="min-w-[140px] flex-1 space-y-1">
        <Label htmlFor={`field-${rule.id}`}>{t('segments.fieldLabel')}</Label>
        <Input
          id={`field-${rule.id}`}
          value={rule.field}
          onChange={(e) => setField({ field: e.target.value })}
          placeholder="country, plan, age, …"
        />
      </div>
      <div className="min-w-[140px] space-y-1">
        <Label htmlFor={`op-${rule.id}`}>{t('segments.operatorLabel')}</Label>
        <Select value={rule.operator} onValueChange={setOp}>
          <SelectTrigger id={`op-${rule.id}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPERATORS.map((op) => (
              <SelectItem key={op} value={op}>{t(`segments.op_${op}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="min-w-[160px] flex-1 space-y-1">
        <Label htmlFor={`val-${rule.id}`}>{t('segments.valueLabel')}</Label>
        {isList ? (
          <textarea
            id={`val-${rule.id}`}
            className="flex min-h-[36px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            rows={2}
            value={Array.isArray(rule.value) ? rule.value.join(', ') : ''}
            onChange={(e) => {
              const arr = e.target.value
                .split(',').map((s) => s.trim()).filter(Boolean)
              setValue(arr)
            }}
            placeholder="DE, FR, US"
          />
        ) : (
          <Input
            id={`val-${rule.id}`}
            type={isNumeric ? 'number' : 'text'}
            value={rule.value ?? ''}
            onChange={(e) => {
              const raw = e.target.value
              setValue(isNumeric && raw !== '' ? Number(raw) : raw)
            }}
          />
        )}
      </div>
      <div className="w-20 space-y-1">
        <Label htmlFor={`prio-${rule.id}`}>{t('segments.priorityLabel')}</Label>
        <Input
          id={`prio-${rule.id}`}
          type="number"
          value={rule.priority}
          onChange={(e) => setField({ priority: Number(e.target.value) })}
        />
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRemove}
        aria-label={t('segments.ruleRemove')}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  )
}
