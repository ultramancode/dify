'use client'
import type { FC } from 'react'
import React, { useEffect, useRef, useState } from 'react'
import {
  RiDeleteBinLine,
  RiUploadCloud2Line,
} from '@remixicon/react'
import { useTranslation } from 'react-i18next'
import { useContext } from 'use-context-selector'
import { formatFileSize } from '@/utils/format'
import cn from '@/utils/classnames'
import { Yaml as YamlIcon } from '@/app/components/base/icons/src/public/files'
import { ToastContext } from '@/app/components/base/toast'
import ActionButton from '@/app/components/base/action-button'

export type Props = {
  file: File | undefined
  updateFile: (file?: File) => void
  className?: string
}

const Uploader: FC<Props> = ({
  file,
  updateFile,
  className,
}) => {
  const { t } = useTranslation()
  const { notify } = useContext(ToastContext)
  const [dragging, setDragging] = useState(false)
  const dropRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<HTMLDivElement>(null)
  const fileUploader = useRef<HTMLInputElement>(null)

  const handleDragEnter = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    e.target !== dragRef.current && setDragging(true)
  }
  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }
  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    e.target === dragRef.current && setDragging(false)
  }
  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)
    if (!e.dataTransfer)
      return
    const files = [...e.dataTransfer.files]
    if (files.length > 1) {
      notify({ type: 'error', message: t('datasetCreation.stepOne.uploader.validation.count') })
      return
    }
    updateFile(files[0])
  }
  const selectHandle = () => {
    const originalFile = file
    if (fileUploader.current) {
      fileUploader.current.value = ''
      fileUploader.current.click()
      // If no file is selected, restore the original file
      fileUploader.current.oncancel = () => updateFile(originalFile)
    }
  }
  const removeFile = () => {
    if (fileUploader.current)
      fileUploader.current.value = ''
    updateFile()
  }
  const fileChangeHandle = (e: React.ChangeEvent<HTMLInputElement>) => {
    const currentFile = e.target.files?.[0]
    updateFile(currentFile)
  }

  useEffect(() => {
    dropRef.current?.addEventListener('dragenter', handleDragEnter)
    dropRef.current?.addEventListener('dragover', handleDragOver)
    dropRef.current?.addEventListener('dragleave', handleDragLeave)
    dropRef.current?.addEventListener('drop', handleDrop)
    return () => {
      dropRef.current?.removeEventListener('dragenter', handleDragEnter)
      dropRef.current?.removeEventListener('dragover', handleDragOver)
      dropRef.current?.removeEventListener('dragleave', handleDragLeave)
      dropRef.current?.removeEventListener('drop', handleDrop)
    }
  }, [])

  return (
    <div className={cn('mt-6', className)}>
      <input
        ref={fileUploader}
        style={{ display: 'none' }}
        type="file"
        id="fileUploader"
        accept='.yaml,.yml'
        onChange={fileChangeHandle}
      />
      <div ref={dropRef}>
        {!file && (
          <div className={cn('flex h-12 items-center rounded-[10px] border border-dashed border-components-dropzone-border bg-components-dropzone-bg text-sm font-normal', dragging && 'border-components-dropzone-border-accent bg-components-dropzone-bg-accent')}>
            <div className='flex w-full items-center justify-center space-x-2'>
              <RiUploadCloud2Line className='h-6 w-6 text-text-tertiary' />
              <div className='text-text-tertiary'>
                {t('datasetCreation.stepOne.uploader.button')}
                <span className='cursor-pointer pl-1 text-text-accent' onClick={selectHandle}>{t('datasetDocuments.list.batchModal.browse')}</span>
              </div>
            </div>
            {dragging && <div ref={dragRef} className='absolute left-0 top-0 h-full w-full' />}
          </div>
        )}
        {file && (
          <div className={cn('group flex items-center rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-on-panel-item-bg shadow-xs', ' hover:bg-components-panel-on-panel-item-bg-hover')}>
            <div className='flex items-center justify-center p-3'>
              <YamlIcon className="h-6 w-6 shrink-0" />
            </div>
            <div className='flex grow flex-col items-start gap-0.5 py-1 pr-2'>
              <span className='font-inter max-w-[calc(100%_-_30px)] overflow-hidden text-ellipsis whitespace-nowrap text-[12px] font-medium leading-4 text-text-secondary'>{file.name}</span>
              <div className='font-inter flex h-3 items-center gap-1 self-stretch text-[10px] font-medium uppercase leading-3 text-text-tertiary'>
                <span>YAML</span>
                <span className='text-text-quaternary'>·</span>
                <span>{formatFileSize(file.size)}</span>
              </div>
            </div>
            <div className='hidden items-center pr-3 group-hover:flex'>
              <ActionButton onClick={removeFile}>
                <RiDeleteBinLine className='h-4 w-4 text-text-tertiary' />
              </ActionButton>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default React.memo(Uploader)
