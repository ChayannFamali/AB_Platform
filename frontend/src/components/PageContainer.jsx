import { cn } from '../lib/utils'

export default function PageContainer({ className, children }) {
  return (
    <div
      className={cn(
        'mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8',
        className
      )}
    >
      {children}
    </div>
  )
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}