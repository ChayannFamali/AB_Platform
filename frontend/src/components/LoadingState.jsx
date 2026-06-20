import { Loader2 } from 'lucide-react'

import { cn } from '../lib/utils'

function Spinner({ label }) {
  return (
    <div className="flex items-center justify-center gap-2 p-6 text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="flex animate-pulse gap-3 border-b p-4 last:border-0">
      <div className="h-4 w-1/4 rounded bg-muted" />
      <div className="h-4 w-1/6 rounded bg-muted" />
      <div className="h-4 w-1/5 rounded bg-muted" />
      <div className="ml-auto h-4 w-16 rounded bg-muted" />
    </div>
  )
}

export default function LoadingState({ variant = 'spinner', count = 5, label, className }) {
  if (variant === 'skeleton') {
    return (
      <div className={cn('rounded-lg border bg-card', className)}>
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    )
  }
  return (
    <div className={cn('flex items-center justify-center p-10', className)}>
      <Spinner label={label} />
    </div>
  )
}

export { Spinner }