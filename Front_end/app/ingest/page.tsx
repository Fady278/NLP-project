'use client'

import { useState } from 'react'
import { FileUp, RefreshCw, AlertCircle, Upload, CheckCircle2, Loader2, FolderOpen, Database, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { UploadZone } from '@/components/rag/upload-zone'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useIngestionJobs, useUploadDocument, useIngestDirectory, useFormatFileSize, useRelativeTime, useDeleteIngestionJob } from '@/lib/hooks/use-rag'
import { API_CONFIG } from '@/lib/config/api'
import type { IngestionJob } from '@/lib/models/types'

export default function IngestPage() {
  const { data: jobs, isLoading, refetch } = useIngestionJobs()
  const uploadMutation = useUploadDocument()
  const directoryMutation = useIngestDirectory()
  const deleteMutation = useDeleteIngestionJob()
  const formatFileSize = useFormatFileSize()
  const formatRelativeTime = useRelativeTime()

  const [inputDir, setInputDir] = useState('data/raw')
  const [projectId, setProjectId] = useState(API_CONFIG.defaultProjectId)
  const [jobPendingDelete, setJobPendingDelete] = useState<IngestionJob | null>(null)

  const handleUpload = async (files: File[]) => {
    for (const file of files) {
      try {
        await uploadMutation.mutateAsync(file)
        toast.success(`Indexed file: ${file.name}`)
      } catch (error) {
        const message = error instanceof Error ? error.message : `Failed to upload: ${file.name}`
        toast.error(message)
      }
    }
    refetch()
  }

  const handleDirectoryIngestion = async () => {
    try {
      await directoryMutation.mutateAsync({
        inputDir,
        projectId,
        indexToVectorDb: true,
      })
      toast.success(`Directory ingested: ${inputDir}`)
      refetch()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Directory ingestion failed'
      toast.error(message)
    }
  }

  const handleDelete = async (jobId: string, fileName: string) => {
    try {
      const result = await deleteMutation.mutateAsync(jobId)
      toast.success(result.message || `Deleted ${fileName}`)
      setJobPendingDelete(null)
      refetch()
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to delete: ${fileName}`
      toast.error(message)
    }
  }

  const activeJobs = jobs?.filter((j) => j.status === 'processing' || j.status === 'queued').length ?? 0
  const completedJobs = jobs?.filter((j) => j.status === 'indexed').length ?? 0
  const failedJobs = jobs?.filter((j) => j.status === 'failed').length ?? 0
  const isBusy = uploadMutation.isPending || directoryMutation.isPending || deleteMutation.isPending

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'indexed':
        return <Badge className="bg-success/10 text-success border-0">Indexed</Badge>
      case 'processing':
        return <Badge className="bg-primary/10 text-primary border-0">Processing</Badge>
      case 'queued':
        return <Badge className="bg-warning/10 text-warning border-0">Queued</Badge>
      case 'failed':
        return <Badge className="bg-destructive/10 text-destructive border-0">Failed</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const getJobSubtitle = (job: IngestionJob) => {
    if (job.fileType === 'directory') {
      const documentsProcessed = Number(job.metadata?.documents_processed ?? 0)
      const inputPath = typeof job.metadata?.input_path === 'string' ? job.metadata.input_path : job.fileName
      return {
        primary: inputPath,
        secondary: documentsProcessed > 0 ? `${documentsProcessed} document${documentsProcessed !== 1 ? 's' : ''}` : 'Directory source',
      }
    }

    return {
      primary: formatFileSize(job.fileSize),
      secondary: null,
    }
  }

  return (
    <div className="flex h-full flex-col min-h-0">
      <div className="shrink-0 border-b border-border/40 bg-card/20 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent via-accent/90 to-chart-4/60">
              <Upload className="h-5 w-5 text-accent-foreground" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">Ingest Documents</h1>
              <p className="text-xs text-muted-foreground">Drag and drop files, or ingest a backend-accessible folder.</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2 rounded-xl border-border/50 bg-background/50">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-6 py-6">
        <div className="mx-auto grid w-full max-w-6xl gap-6 xl:grid-cols-2">
          <div className="flex flex-col gap-5">
            <div className="surface p-6">
              <h2 className="mb-4 label-caps">Upload Files</h2>
              <UploadZone onUpload={handleUpload} isUploading={uploadMutation.isPending} />
            </div>

            <div className="surface p-6">
              <h2 className="mb-4 label-caps">Ingest Existing Directory</h2>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="project-id">Project ID</Label>
                  <Input id="project-id" value={projectId} onChange={(e) => setProjectId(e.target.value)} disabled={isBusy} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="input-dir">Input directory</Label>
                  <Input id="input-dir" value={inputDir} onChange={(e) => setInputDir(e.target.value)} placeholder="data/raw or absolute path" disabled={isBusy} />
                </div>
                <div className="rounded-xl border border-border/40 bg-muted/20 p-4 text-sm text-muted-foreground">
                  Use this when the files already exist on the backend machine and you want to ingest the folder directly.
                  Identical files are skipped by default to avoid duplicate indexing.
                </div>
                <Button onClick={handleDirectoryIngestion} disabled={!inputDir.trim() || !projectId.trim() || isBusy} className="btn-glow gap-2 rounded-xl">
                  {directoryMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running ingestion...
                    </>
                  ) : (
                    <>
                      <FolderOpen className="h-4 w-4" />
                      Start Directory Ingestion
                    </>
                  )}
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="surface-raised p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                  <Loader2 className="h-4 w-4 text-primary" />
                </div>
                <p className="mt-3 text-2xl font-bold stat-number">{activeJobs}</p>
                <p className="text-xs text-muted-foreground">Processing</p>
              </div>
              <div className="surface-raised p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                </div>
                <p className="mt-3 text-2xl font-bold stat-number">{completedJobs}</p>
                <p className="text-xs text-muted-foreground">Indexed</p>
              </div>
              <div className="surface-raised p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-destructive/10">
                  <AlertCircle className="h-4 w-4 text-destructive" />
                </div>
                <p className="mt-3 text-2xl font-bold stat-number">{failedJobs}</p>
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
            </div>
          </div>

          <div className="flex flex-col surface xl:min-h-0 lg:min-h-[500px]">
            <div className="flex items-center justify-between border-b border-border/40 px-5 py-4">
              <h2 className="label-caps">Ingestion History</h2>
              <span className="text-xs text-muted-foreground">{jobs?.length ?? 0} total</span>
            </div>

            <ScrollArea className="flex-1 xl:min-h-0 h-[400px] xl:h-auto">
              {!jobs || jobs.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/30">
                    <Database className="h-8 w-8 text-muted-foreground/40" />
                  </div>
                  <h3 className="mt-4 font-semibold">No ingestion history yet</h3>
                  <p className="mt-1 max-w-[260px] text-sm text-muted-foreground">
                    Upload files or ingest a directory to start building real backend history.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 p-4">
                  {jobs.map((job) => {
                    const subtitle = getJobSubtitle(job)
                    return (
                    <div key={job.id} className="group surface-raised p-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted/40 text-xs font-bold uppercase text-muted-foreground">
                          {job.fileType === 'directory' ? 'DIR' : job.fileType}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate font-medium">{job.fileName}</p>
                              <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{subtitle.primary}</span>
                                {subtitle.secondary && (
                                  <>
                                    <span className="text-border">|</span>
                                    <span>{subtitle.secondary}</span>
                                  </>
                                )}
                                <span className="text-border">|</span>
                                <span>{formatRelativeTime(job.updatedAt)}</span>
                              </div>
                            </div>
                            {getStatusBadge(job.status)}
                          </div>

                          {job.chunksCreated !== undefined && (
                            <p className="mt-2 flex items-center gap-1 text-xs text-success">
                              <CheckCircle2 className="h-3 w-3" />
                              {job.chunksCreated} chunks created
                            </p>
                          )}

                          {job.status === 'failed' && job.errorMessage && (
                            <div className="mt-2 flex items-start gap-2 rounded-lg bg-destructive/10 px-2 py-1.5">
                              <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-destructive" />
                              <p className="text-xs text-destructive">{job.errorMessage}</p>
                            </div>
                          )}

                          {job.status === 'indexed' && (
                            <div className="mt-3 flex justify-end">
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-8 gap-1.5 rounded-lg text-destructive hover:bg-destructive/10 hover:text-destructive"
                                disabled={deleteMutation.isPending}
                                onClick={() => setJobPendingDelete(job)}
                              >
                                {deleteMutation.isPending ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Trash2 className="h-3.5 w-3.5" />
                                )}
                                Delete
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    )
                  })}
                </div>
              )}
            </ScrollArea>
          </div>
        </div>
      </div>

      <AlertDialog open={!!jobPendingDelete} onOpenChange={(open) => !open && setJobPendingDelete(null)}>
        <AlertDialogContent className="surface border-border/50 sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-left">Delete ingestion data?</AlertDialogTitle>
            <AlertDialogDescription className="text-left leading-relaxed">
              {jobPendingDelete?.fileType === 'directory'
                ? `This will remove files inside "${jobPendingDelete.fileName}", delete their processed chunks, remove matching index entries, and clean up nested upload jobs under this folder.`
                : `This will permanently delete "${jobPendingDelete?.fileName}" from uploaded files, processed outputs, and the vector index.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="rounded-xl border border-border/40 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
            This action cannot be undone.
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-xl">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (jobPendingDelete) {
                  void handleDelete(jobPendingDelete.id, jobPendingDelete.fileName)
                }
              }}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
