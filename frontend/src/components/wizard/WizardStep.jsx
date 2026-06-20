import { ArrowLeft, ArrowRight } from 'lucide-react'

import { Button } from '../ui/button'

/**
 * Single-step wrapper used by the Create Experiment wizard.
 *
 * Renders children plus a fixed footer with Back / Next (or Create) buttons.
 * The parent owns form state and validation; this component just wires the
 * navigation callbacks. `isNextDisabled` is a controlled flag — set it from
 * the parent's per-step validation.
 */
export default function WizardStep({
  title,
  description,
  children,
  onBack,
  onNext,
  isFirst,
  isLast,
  isNextDisabled = false,
  isSubmitting = false,
  nextLabel,
  backLabel,
  error,
}) {
  return (
    <div>
      {title && (
        <h2 className="mb-1 text-lg font-semibold tracking-tight">
          {title}
        </h2>
      )}
      {description && (
        <p className="mb-4 text-sm text-muted-foreground">{description}</p>
      )}

      {children}

      {error && (
        <p className="mt-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="mt-6 flex items-center justify-between border-t pt-4">
        <Button
          variant="ghost"
          onClick={onBack}
          disabled={isFirst || isSubmitting}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          {backLabel ?? 'Back'}
        </Button>
        <Button
          onClick={onNext}
          disabled={isNextDisabled || isSubmitting}
        >
          {isSubmitting
            ? 'Loading…'
            : (nextLabel ?? (isLast ? 'Create' : 'Next'))}
          {!isLast && !isSubmitting && (
            <ArrowRight className="ml-1 h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  )
}
