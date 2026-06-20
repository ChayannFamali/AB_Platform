import { Inbox } from 'lucide-react'

import { cn } from '../lib/utils'

export default function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}) {
  const IconComponent = icon || Inbox
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed bg-card p-10 text-center',
        className
      )}
    >
      <IconComponent className="mb-3 h-10 w-10 text-muted-foreground" />
      {title && (
        <h3 className="mb-1 text-lg font-semibold">{title}</h3>
      )}
      {description && (
        <p className="mb-4 max-w-sm text-sm text-muted-foreground">
          {description}
        </p>
      )}
      {action}
    </div>
  )
}