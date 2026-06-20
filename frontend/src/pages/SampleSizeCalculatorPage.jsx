import { useTranslation } from 'react-i18next'

import SampleSizeCalculator from '../components/wizard/SampleSizeCalculator'
import { PageHeader } from '../components/PageContainer'

export default function SampleSizeCalculatorPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader
        title={t('sampleSize.title')}
        description={t('sampleSize.subtitle')}
      />
      <SampleSizeCalculator />
    </>
  )
}
