'use client'

import { useContext, useContextSelector } from 'use-context-selector'
import { useRouter } from 'next/navigation'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import cn from 'classnames'
import { Form, Input, Modal, Select, message } from 'antd'
import style from '../list.module.css'
import AppModeLabel from './AppModeLabel'
import s from './style.module.css'
import SettingsModal from '@/app/components/app/overview/settings'
import type { ConfigParams } from '@/app/components/app/overview/settings'
import type { App } from '@/types/app'
import Confirm from '@/app/components/base/confirm'
import { ToastContext } from '@/app/components/base/toast'
import { deleteApp, fetchAppDetail, insertExploreAppList, updateAppSiteConfig } from '@/service/apps'
import AppIcon from '@/app/components/base/app-icon'
import AppsContext, { useAppContext } from '@/context/app-context'
import type { HtmlContentProps } from '@/app/components/base/popover'
import CustomPopover from '@/app/components/base/popover'
import Divider from '@/app/components/base/divider'
import { asyncRunSafe } from '@/utils'

export type AppCardProps = {
  app: App
  onRefresh?: () => void
}

const AppCard = ({ app, onRefresh }: AppCardProps) => {
  const { t } = useTranslation()
  const { notify } = useContext(ToastContext)
  const { isCurrentWorkspaceManager } = useAppContext()
  const { push } = useRouter()

  const mutateApps = useContextSelector(
    AppsContext,
    state => state.mutateApps,
  )

  const [showConfirmDelete, setShowConfirmDelete] = useState(false)
  const [showExploreModal, setShowExploreModal] = useState(false)
  const [form] = Form.useForm()
  const [messageApi, contextHolder] = message.useMessage()
  const [showSettingsModal, setShowSettingsModal] = useState(false)
  const [detailState, setDetailState] = useState<{
    loading: boolean
    detail?: App
  }>({ loading: false })

  const onConfirmDelete = useCallback(async () => {
    try {
      await deleteApp(app.id)
      notify({ type: 'success', message: t('app.appDeleted') })
      if (onRefresh)
        onRefresh()
      mutateApps()
    }
    catch (e: any) {
      notify({
        type: 'error',
        message: `${t('app.appDeleteFailed')}${'message' in e ? `: ${e.message}` : ''
        }`,
      })
    }
    setShowConfirmDelete(false)
  }, [app.id])

  const onConfirmExplore = () => {
    form.validateFields().then((data) => {
      insertExploreAppList({
        app_id: app.id,
        ...data,
      }).then((data) => {
        console.log(data)
        messageApi.success('添加成功')
        setShowExploreModal(false)
      }).catch((err) => {
        messageApi.error('添加失败')
        console.log(err)
      })
    })
  }

  const getAppDetail = async () => {
    setDetailState({ loading: true })
    const [err, res] = await asyncRunSafe(
      fetchAppDetail({ url: '/apps', id: app.id }),
    )
    if (!err) {
      setDetailState({ loading: false, detail: res })
      setShowSettingsModal(true)
    }
    else { setDetailState({ loading: false }) }
  }

  const onSaveSiteConfig = useCallback(
    async (params: ConfigParams) => {
      const [err] = await asyncRunSafe(
        updateAppSiteConfig({
          url: `/apps/${app.id}/site`,
          body: params,
        }),
      )
      if (!err) {
        notify({
          type: 'success',
          message: t('common.actionMsg.modifiedSuccessfully'),
        })
        if (onRefresh)
          onRefresh()
        mutateApps()
      }
      else {
        notify({
          type: 'error',
          message: t('common.actionMsg.modifiedUnsuccessfully'),
        })
      }
    },
    [app.id],
  )

  const Operations = (props: HtmlContentProps) => {
    const onClickSettings = async (e: React.MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation()
      props.onClick?.()
      e.preventDefault()
      await getAppDetail()
    }
    const onClickExplore = async (e: React.MouseEvent<HTMLButtonElement>) => {
      props.onClick?.()
      e.preventDefault()
      setShowExploreModal(true)
    }
    const onClickDelete = async (e: React.MouseEvent<HTMLDivElement>) => {
      e.stopPropagation()
      props.onClick?.()
      e.preventDefault()
      setShowConfirmDelete(true)
    }
    return (
      <div className="w-full py-1">
        <button className={s.actionItem} onClick={onClickSettings} disabled={detailState.loading}>
          <span className={s.actionName}>{t('common.operation.settings')}</span>
        </button>

        <Divider className="!my-1" />
        <button className={s.actionItem} onClick={onClickExplore} disabled={detailState.loading}>
          <span className={s.actionName}>{'添加到探索'}</span>
        </button>

        <Divider className="!my-1" />
        <div
          className={cn(s.actionItem, s.deleteActionItem, 'group')}
          onClick={onClickDelete}
        >
          <span className={cn(s.actionName, 'group-hover:text-red-500')}>
            {t('common.operation.delete')}
          </span>
        </div>
      </div>
    )
  }

  return (
    <>
      <div
        onClick={(e) => {
          e.preventDefault()
          push(`/app/${app.id}/overview`)
        }}
        className={style.listItem}
      >
        <div className={style.listItemTitle}>
          <AppIcon
            size="small"
            icon={app.icon}
            background={app.icon_background}
          />
          <div className={style.listItemHeading}>
            <div className={style.listItemHeadingContent}>{app.name}</div>
          </div>
          {isCurrentWorkspaceManager && <CustomPopover
            htmlContent={<Operations />}
            position="br"
            trigger="click"
            btnElement={<div className={cn(s.actionIcon, s.commonIcon)} />}
            btnClassName={open =>
              cn(
                open ? '!bg-gray-100 !shadow-none' : '!bg-transparent',
                style.actionIconWrapper,
              )
            }
            className={'!w-[128px] h-fit !z-20'}
            manualClose
          />}
        </div>
        <div className={style.listItemDescription}>
          {app.model_config?.pre_prompt}
        </div>
        <div className={style.listItemFooter}>
          <AppModeLabel mode={app.mode} />
        </div>

        {showConfirmDelete && (
          <Confirm
            title={t('app.deleteAppConfirmTitle')}
            content={t('app.deleteAppConfirmContent')}
            isShow={showConfirmDelete}
            onClose={() => setShowConfirmDelete(false)}
            onConfirm={onConfirmDelete}
            onCancel={() => setShowConfirmDelete(false)}
          />
        )}

        {showSettingsModal && detailState.detail && (
          <SettingsModal
            appInfo={detailState.detail}
            isShow={showSettingsModal}
            onClose={() => setShowSettingsModal(false)}
            onSave={onSaveSiteConfig}
          />
        )}
      </div>
      {showExploreModal && (
        <Modal
          open={showExploreModal}
          onOk={onConfirmExplore}
          onCancel={() => setShowExploreModal(false)}
        >
          <Form
            name="basic"
            form={form}
            labelCol={{ span: 6 }}
            wrapperCol={{ span: 16 }}
            autoComplete="off"
            initialValues={{
              token: 'libai666',
              language: 'zh-Hans',
              category: '未分类',
              position: 1,
              desc: '',
              copyright: '',
              privacy_policy: '',
            }}
          >
            <Form.Item
              label="app_id"
              name="app_id"
              initialValue={app.id}
            >
              <Input disabled />
            </Form.Item>
            <Form.Item
              label="token"
              name="token"
              rules={[{ required: true, message: 'Please input your token!' }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="语言"
              name="language"
              rules={[{ required: true, message: 'Please input your language!' }]}
            >
              <Select options={[
                { value: 'zh-Hans', label: '简体中文' },
                { value: 'en-US', label: 'English(United States)' },
              ]} />
            </Form.Item>
            <Form.Item
              label="分类"
              name="category"
              rules={[{ required: true, message: 'Please input your category!' }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="position"
              name="position"
              rules={[{ required: true, message: 'Please input your position!' }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="desc"
              name="desc"
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="copyright"
              name="copyright"
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="privacy_policy"
              name="privacy_policy"
            >
              <Input />
            </Form.Item>

          </Form>

        </Modal >
      )}
    </>
  )
}

export default AppCard
