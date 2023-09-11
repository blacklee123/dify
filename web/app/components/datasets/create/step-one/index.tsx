'use client'
import React, { useMemo, useState } from 'react'
import { Input, Space, Spin, Typography, message } from 'antd'
import useSWR from 'swr'
import { useTranslation } from 'react-i18next'
import cn from 'classnames'
import FilePreview from '../file-preview'
import FileUploader from '../file-uploader'
import LarkPagePreview from '../lark-page-preview'
import NotionPagePreview from '../notion-page-preview'
import EmptyDatasetCreationModal from '../empty-dataset-creation-modal'
import s from './index.module.css'
import type { FileItem } from '@/models/datasets'
import type { NotionPage } from '@/models/common'
import { DataSourceType } from '@/models/datasets'
import Button from '@/app/components/base/button'
import { NotionPageSelector } from '@/app/components/base/notion-page-selector'
import { useDatasetDetailContext } from '@/context/dataset-detail'
import { fetchDocumentsLimit, fetchLarkPreview } from '@/service/common'

type IStepOneProps = {
  datasetId?: string
  dataSourceType?: DataSourceType
  dataSourceTypeDisable: Boolean
  hasConnection: boolean
  onSetting: () => void
  files: FileItem[]
  updateFileList: (files: FileItem[]) => void
  updateFile: (fileItem: FileItem, progress: number, list: FileItem[]) => void
  notionPages?: NotionPage[]
  larkPages?: string
  updateNotionPages: (value: NotionPage[]) => void
  updateLarkPages: (value: string) => void
  onStepChange: () => void
  changeType: (type: DataSourceType) => void
}

type NotionConnectorProps = {
  onSetting: () => void
}
export const NotionConnector = ({ onSetting }: NotionConnectorProps) => {
  const { t } = useTranslation()

  return (
    <div className={s.notionConnectionTip}>
      <span className={s.notionIcon} />
      <div className={s.title}>{t('datasetCreation.stepOne.notionSyncTitle')}</div>
      <div className={s.tip}>{t('datasetCreation.stepOne.notionSyncTip')}</div>
      <Button className='h-8' type='primary' onClick={onSetting}>{t('datasetCreation.stepOne.connect')}</Button>
    </div>
  )
}

const StepOne = ({
  datasetId,
  dataSourceType,
  dataSourceTypeDisable,
  changeType,
  hasConnection,
  onSetting,
  onStepChange,
  files,
  updateFileList,
  updateFile,
  notionPages = [],
  larkPages = '',
  updateNotionPages,
  updateLarkPages,
}: IStepOneProps) => {
  const { data: limitsData } = useSWR('/datasets/limit', fetchDocumentsLimit)
  const { dataset } = useDatasetDetailContext()
  const [showModal, setShowModal] = useState(false)
  const [currentFile, setCurrentFile] = useState<File | undefined>()
  const [currentNotionPage, setCurrentNotionPage] = useState<Page | undefined>()
  const [currentLarkPage, setCurrentLarkPage] = useState<string | undefined>()
  const { t } = useTranslation()

  const [larkInput, setLarkInput] = useState('')
  const [previewContent, setPreviewContent] = useState('')
  const [previewTitle, setPreviewTitle] = useState('')
  const [loading, setLoading] = useState(false)

  const modalShowHandle = () => setShowModal(true)
  const modalCloseHandle = () => setShowModal(false)

  const updateCurrentFile = (file: File) => {
    setCurrentFile(file)
  }
  const hideFilePreview = () => {
    setCurrentFile(undefined)
  }

  const updateCurrentPage = (page: Page) => {
    setCurrentNotionPage(page)
  }

  const hideNotionPagePreview = () => {
    setCurrentNotionPage(undefined)
  }

  const hideLarkPagePreview = () => {
    setCurrentLarkPage(undefined)
  }

  const shouldShowDataSourceTypeList = !datasetId || (datasetId && !dataset?.data_source_type)

  const nextDisabled = useMemo(() => {
    if (!files.length)
      return true
    if (files.some(file => !file.file.id))
      return true
    return false
  }, [files])
  return (
    <div className='flex w-full h-full'>
      <div className='grow overflow-y-auto relative'>
        {
          shouldShowDataSourceTypeList && (
            <div className={s.stepHeader}>{t('datasetCreation.steps.one')}</div>
          )
        }
        <div className={s.form}>
          {
            shouldShowDataSourceTypeList && (
              <div className={s.dataSourceTypeList}>
                <div
                  className={cn(
                    s.dataSourceItem,
                    dataSourceType === DataSourceType.LARK && s.active,
                    dataSourceTypeDisable && dataSourceType !== DataSourceType.LARK && s.disabled,
                  )}
                  onClick={() => {
                    if (dataSourceTypeDisable)
                      return
                    changeType(DataSourceType.LARK)
                    hideFilePreview()
                    hideNotionPagePreview()
                    hideLarkPagePreview()
                  }}
                >
                  <span className={cn(s.datasetIcon, s.lark)} />
                  {t('datasetCreation.stepOne.dataSourceType.lark')}
                </div>
                <div
                  className={cn(
                    s.dataSourceItem,
                    dataSourceType === DataSourceType.FILE && s.active,
                    dataSourceTypeDisable && dataSourceType !== DataSourceType.FILE && s.disabled,
                  )}
                  onClick={() => {
                    if (dataSourceTypeDisable)
                      return
                    changeType(DataSourceType.FILE)
                    hideFilePreview()
                    hideNotionPagePreview()
                    hideLarkPagePreview()
                  }}
                >
                  <span className={cn(s.datasetIcon)} />
                  {t('datasetCreation.stepOne.dataSourceType.file')}
                </div>
                <div
                  className={cn(
                    s.dataSourceItem,
                    dataSourceType === DataSourceType.NOTION && s.active,
                    dataSourceTypeDisable && dataSourceType !== DataSourceType.NOTION && s.disabled,
                  )}
                  onClick={() => {
                    if (dataSourceTypeDisable)
                      return
                    changeType(DataSourceType.NOTION)
                    hideFilePreview()
                    hideNotionPagePreview()
                    hideLarkPagePreview()
                  }}
                >
                  <span className={cn(s.datasetIcon, s.notion)} />
                  {t('datasetCreation.stepOne.dataSourceType.notion')}
                </div>
                <div
                  className={cn(s.dataSourceItem, s.disabled, dataSourceType === DataSourceType.WEB && s.active)}
                // onClick={() => changeType(DataSourceType.WEB)}
                >
                  <span className={s.comingTag}>Coming soon</span>
                  <span className={cn(s.datasetIcon, s.web)} />
                  {t('datasetCreation.stepOne.dataSourceType.web')}
                </div>
              </div>
            )
          }
          {dataSourceType === DataSourceType.FILE && limitsData && (
            <>
              <FileUploader
                fileList={files}
                titleClassName={!shouldShowDataSourceTypeList ? 'mt-[30px] !mb-[44px] !text-lg !font-semibold !text-gray-900' : undefined}
                prepareFileList={updateFileList}
                onFileListUpdate={updateFileList}
                onFileUpdate={updateFile}
                onPreview={updateCurrentFile}
                countLimit={limitsData.documents_limit}
                countUsed={limitsData.documents_count}
              />
              <Button disabled={nextDisabled} className={s.submitButton} type='primary' onClick={onStepChange}>{t('datasetCreation.stepOne.button')}</Button>
            </>
          )}
          {dataSourceType === DataSourceType.LARK && limitsData && (
            <Spin spinning={loading}>
              <Space direction='vertical' className='w-full'>
                <Typography.Title level={5} >导入飞书文档</Typography.Title>
                <Input.Search
                  value={larkInput}
                  allowClear
                  placeholder="请输入飞书文档链接，输入完成后按回车键确定"
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setLarkInput(e.target.value) }}
                  onPressEnter={async () => {
                    if (larkInput === '')
                      return
                    setLoading(true)
                    try {
                      const res = await fetchLarkPreview({ fileID: larkInput })
                      setLoading(false)
                      setPreviewContent(res.content)
                      setPreviewTitle(res.title)
                      updateLarkPages(larkInput)
                      setCurrentLarkPage(larkInput)
                    }
                    catch (error) {
                      setLoading(false)
                      message.error('获取文档失败，请检查链接有效性')
                    }
                  }}
                  onSearch={async () => {
                    if (larkInput === '')
                      return
                    setLoading(true)
                    try {
                      const res = await fetchLarkPreview({ fileID: larkInput })
                      setLoading(false)
                      setPreviewContent(res.content)
                      setPreviewTitle(res.title)
                      updateLarkPages(larkInput)
                      setCurrentLarkPage(larkInput)
                    }
                    catch (error) {
                      setLoading(false)
                      message.error('获取文档失败，请检查链接有效性')
                    }
                  }}
                />
                {currentLarkPage && <Typography.Link href={larkInput} target='_blank' className='underline text-blue-800'>{previewTitle}</Typography.Link>}
                <Button disabled={!larkPages.length} className={s.submitButton} type='primary' onClick={onStepChange}>{t('datasetCreation.stepOne.button')}</Button>
              </Space>
            </Spin>
          )}
          {dataSourceType === DataSourceType.NOTION && (
            <>
              {!hasConnection && <NotionConnector onSetting={onSetting} />}
              {hasConnection && limitsData && (
                <>
                  <div className='mb-8 w-[640px]'>
                    <NotionPageSelector
                      value={notionPages.map(page => page.page_id)}
                      onSelect={updateNotionPages}
                      onPreview={updateCurrentPage}
                      countLimit={limitsData.documents_limit}
                      countUsed={limitsData.documents_count}
                    />
                  </div>
                  <Button disabled={!notionPages.length} className={s.submitButton} type='primary' onClick={onStepChange}>{t('datasetCreation.stepOne.button')}</Button>
                </>
              )}
            </>
          )}
          {!datasetId && (
            <>
              <div className={s.dividerLine} />
              <div onClick={modalShowHandle} className={s.OtherCreationOption}>{t('datasetCreation.stepOne.emptyDatasetCreation')}</div>
            </>
          )}
        </div>
        <EmptyDatasetCreationModal show={showModal} onHide={modalCloseHandle} />
      </div>
      {currentFile && <FilePreview file={currentFile} hidePreview={hideFilePreview} />}
      {currentLarkPage && <LarkPagePreview previewContent={previewContent} previewTitle={previewTitle} hidePreview={hideLarkPagePreview} />}
      {currentNotionPage && <NotionPagePreview currentPage={currentNotionPage} hidePreview={hideNotionPagePreview} />}
    </div>
  )
}

export default StepOne
