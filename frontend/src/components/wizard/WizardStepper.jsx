import { Check } from 'lucide-react'

import { cn } from '../../lib/utils'

/**
 * Horizontal step indicator for multi-step wizards.
 *
 * Renders an ordered list of step labels with three visual states:
 * - `done` — past steps, green check
 * - `current` — active step, highlighted
 * - `pending` — future steps, muted
 *
 * Clicking a step is a no-op; navigation is controlled by the parent
 * (next/back buttons or per-step validation). This is intentional:
 * skipping ahead without validation would let users create invalid
 * experiments.
 */
export default function WizardStepper({ steps, currentIndex }) {
  return (
    <ol className="mb-6 flex items-center gap-2 overflow-x-auto pb-2">
      {steps.map((step, idx) => {
        const isDone = idx < currentIndex
        const isCurrent = idx === currentIndex
        return (
          <li
            key={step.key ?? step.title}
            className="flex items-center gap-2"
            aria-current={isCurrent ? 'step' : undefined}
          >
            <span
              className={cn(
                'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                isDone && 'bg-emerald-500 text-white',
                isCurrent && 'bg-primary text-primary-foreground',
                !isDone && !isCurrent && 'bg-muted text-muted-foreground',
              )}
            >
              {isDone ? <Check className="h-3.5 w-3.5" /> : idx + 1}
            </span>
            <span
              className={cn(
                'whitespace-nowrap text-sm',
                isCurrent
                  ? 'font-semibold text-foreground'
                  : 'text-muted-foreground',
              )}
            >
              {step.title}
            </span>
            {idx < steps.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  'mx-1 h-px w-8 shrink-0 sm:w-12',
                  isDone ? 'bg-emerald-500' : 'bg-muted',
                )}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}
