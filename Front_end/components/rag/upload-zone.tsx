'use client'

import { useState, useCallback, useRef, type DragEvent } from 'react'
import { Upload, X, CloudUpload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const ACCEPTED_TYPES = ['.pdf', '.md', '.txt', '.docx', '.html']
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

interface UploadZoneProps {
  onUpload: (files: File[]) => void
  isUploading?: boolean
}

export function UploadZone({ onUpload, isUploading }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) {
      return `File type ${ext} not supported`
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File exceeds 50MB limit'
    }
    return null
  }, [])

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const fileArray = Array.from(files)
      const validFiles = fileArray.filter((f) => !validateFile(f))
      setPendingFiles((prev) => [...prev, ...validFiles])
    },
    [validateFile]
  )

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files)
      }
    },
    [handleFiles]
  )

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files?.length) {
        handleFiles(e.target.files)
      }
    },
    [handleFiles]
  )

  const removeFile = useCallback((index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const handleUpload = useCallback(() => {
    if (pendingFiles.length > 0) {
      onUpload(pendingFiles)
      setPendingFiles([])
    }
  }, [pendingFiles, onUpload])

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        className={cn(
          'group relative cursor-pointer overflow-hidden rounded-xl border-2 border-dashed p-8 text-center transition-all',
          isDragging
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-border/40 hover:border-primary/40 hover:bg-primary/[0.02]',
          isUploading && 'pointer-events-none opacity-50'
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(',')}
          onChange={handleInputChange}
          className="hidden"
        />

        <div className="relative flex flex-col items-center gap-4">
          <div className={cn(
            'flex h-14 w-14 items-center justify-center rounded-2xl transition-all',
            isDragging 
              ? 'bg-primary text-primary-foreground scale-110' 
              : 'bg-primary/10 text-primary group-hover:bg-primary/15'
          )}>
            <CloudUpload className={cn(
              'h-7 w-7 transition-transform',
              isDragging && 'animate-bounce'
            )} />
          </div>
          <div>
            <p className="text-base font-semibold">
              {isDragging ? 'Drop files here' : 'Drag & drop files'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              or click to browse your computer
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {ACCEPTED_TYPES.map((type) => (
              <span key={type} className="chip">
                {type}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted-foreground/50">
            Maximum file size: 50MB
          </p>
        </div>
      </div>

      {/* Pending Files */}
      {pendingFiles.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-muted-foreground">
              {pendingFiles.length} file{pendingFiles.length !== 1 ? 's' : ''} ready
            </p>
            <Button 
              onClick={handleUpload} 
              disabled={isUploading}
              className="btn-glow gap-2 rounded-xl"
            >
              {isUploading ? (
                <>
                  <Upload className="h-4 w-4 animate-pulse" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  Upload All
                </>
              )}
            </Button>
          </div>
          <div className="space-y-2">
            {pendingFiles.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="group flex items-center justify-between surface-raised p-3"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold uppercase text-primary">
                    {file.name.split('.').pop()}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatSize(file.size)}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(index)
                  }}
                >
                  <X className="h-4 w-4" />
                  <span className="sr-only">Remove file</span>
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
