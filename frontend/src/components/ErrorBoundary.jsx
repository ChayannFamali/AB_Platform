import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from './ui/alert'
import { Button } from './ui/button'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleReset)
      }
      return (
        <div className="flex min-h-[400px] items-center justify-center p-6">
          <Alert variant="destructive" className="max-w-xl">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>
              <p className="mb-3">
                {this.state.error?.message || 'Unexpected error'}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={this.handleReset}
              >
                Try again
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      )
    }
    return this.props.children
  }
}