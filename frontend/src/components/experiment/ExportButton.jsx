import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Download } from 'lucide-react'

import { exportResults } from '../../api/client'
import { Button } from '../ui/button'
import { toast } from '../../hooks/use-toast'

/**
 * Triggers a CSV download for the experiment's saved results.
 *
 * Backend returns text/csv with a Content-Disposition header naming
 * `experiment_{id}_results.csv`. We unwrap the Blob and save it via a
 * temporary <a> click so the browser handles the download.
 */
export default function ExportButton({ experimentId }) {
  const { t } = useTranslation()
  const [downloadUrl, setDownloadUrl] = useState(null)

  const exportMutation = useMutation({
    mutationFn: () => exportResults(experimentId),
    onSuccess: (response) => {
      const blob = response.data
      const url = window.URL.createObjectURL(blob)
      setDownloadUrl(url)
      toast({ description: t('export.success') })
    },
    onError: (err) =>
      toast({
        variant: 'destructive',
        description:
          err.response?.data?.detail || t('export.failed'),
      }),
  })

  const handleClick = () => {
    // If we already have a blob URL from a prior click, revoke it before
    // requesting a new one so we don't leak object URLs.
    if (downloadUrl) {
      window.URL.revokeObjectURL(downloadUrl)
      setDownloadUrl(null)
    }
    exportMutation.mutate()
  }

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={handleClick}
        disabled={exportMutation.isLoading}
      >
        <Download className="mr-1 h-4 w-4" />
        {exportMutation.isLoading ? t('common.loading') : t('export.csv')}
      </Button>
      {downloadUrl && (
        <a
          href={downloadUrl}
          download={`experiment_${experimentId}_results.csv`}
          style={{ display: 'none' }}
          ref={(el) => {
            if (el) el.click()
          }}
        />
      )}
    </>
  )
}
