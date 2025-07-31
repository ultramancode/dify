import type { FC } from 'react'
import React from 'react'
import { useTranslation } from 'react-i18next'
import Field from '@/app/components/workflow/nodes/_base/components/field'
import Tooltip from '@/app/components/base/tooltip'
import { RiQuestionLine } from '@remixicon/react'
import Switch from '@/app/components/base/switch'

type ReasoningModeConfigProps = {
  value?: 'tagged' | 'stripped'
  onChange: (value: 'tagged' | 'stripped') => void
  readonly?: boolean
}

const ReasoningModeConfig: FC<ReasoningModeConfigProps> = ({
  value = 'tagged',
  onChange,
  readonly = false,
}) => {
  const { t } = useTranslation()

  return (
    <Field
      title={
        <div className='flex items-center space-x-1'>
          <div className='text-xs font-semibold uppercase text-text-secondary'>
            {t('workflow.nodes.llm.reasoningMode.title')}
          </div>
          <Tooltip popupContent={t('workflow.nodes.llm.reasoningMode.tooltip')}>
            <div>
              <RiQuestionLine className='size-3.5 text-text-quaternary' />
            </div>
          </Tooltip>
        </div>
      }
    >
      <div className='flex items-center justify-between'>
        <div className='flex items-center space-x-1'>
          <div className='text-xs font-semibold uppercase text-text-secondary'>
            {value === 'tagged'
              ? t('workflow.nodes.llm.reasoningMode.tagged')
              : t('workflow.nodes.llm.reasoningMode.stripped')
            }
          </div>
        </div>
        <Switch
          className='ml-2'
          defaultValue={value === 'stripped'} // ON = stripped (제거), OFF = tagged (유지)
          onChange={enabled => onChange(enabled ? 'stripped' : 'tagged')}
          size='md'
          disabled={readonly}
          key={value}
        />
      </div>
    </Field>
  )
}

export default ReasoningModeConfig
