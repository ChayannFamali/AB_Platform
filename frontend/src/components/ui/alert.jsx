import * as React from 'react'

import { cn } from '../../lib/utils'

const alertVariants = {
  default: 'bg-background text-foreground',
  destructive:
    'border-destructive/50 text-destructive dark:border-destructive [&>svg]:text-destructive',
  warning:
    'border-amber-500/50 text-amber-700 dark:text-amber-400 [&>svg]:text-amber-500',
  success:
    'border-emerald-500/50 text-emerald-700 dark:text-emerald-400 [&>svg]:text-emerald-500',
  info:
    'border-sky-500/50 text-sky-700 dark:text-sky-400 [&>svg]:text-sky-500',
}

const Alert = React.forwardRef(({ className, variant = 'default', ...props }, ref) => (
  <div
    ref={ref}
    role="alert"
    className={cn(
      'relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground',
      alertVariants[variant],
      className
    )}
    {...props}
  />
))
Alert.displayName = 'Alert'

const AlertTitle = React.forwardRef(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn('mb-1 font-medium leading-none tracking-tight', className)}
    {...props}
  />
))
AlertTitle.displayName = 'AlertTitle'

const AlertDescription = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('text-sm [&_p]:leading-relaxed', className)}
    {...props}
  />
))
AlertDescription.displayName = 'AlertDescription'

export { Alert, AlertTitle, AlertDescription }
