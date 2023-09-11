'use client'
import React from 'react'
import { useTranslation } from 'react-i18next'
import cn from 'classnames'
import { XMarkIcon } from '@heroicons/react/20/solid'
import s from './index.module.css'

type IProps = {
  previewContent: string
  previewTitle: string
  hidePreview: () => void
}

const LarkPreview = ({
  previewContent,
  previewTitle,
  hidePreview,
}: IProps) => {
  const { t } = useTranslation()
  return (
    <div className={cn(s.filePreview)}>
      <div className={cn(s.previewHeader)}>
        <div className={cn(s.title)}>
          <span>{t('datasetCreation.stepOne.filePreview')}</span>
          <div className='flex items-center justify-center w-6 h-6 cursor-pointer' onClick={hidePreview}>
            <XMarkIcon className='h-4 w-4'></XMarkIcon>
          </div>
        </div>
        <div className={cn(s.fileName)}>
          <span>{previewTitle}</span><span className={cn(s.filetype)}></span>
        </div>
      </div>
      <div className={cn(s.previewContent)}>
        <div className={cn(s.fileContent)}>{previewContent}</div>
      </div>
    </div>
  )
}

export default LarkPreview
