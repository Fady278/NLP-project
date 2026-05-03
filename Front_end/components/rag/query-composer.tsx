'use client'

import { useState, useCallback, type KeyboardEvent, useRef, useEffect } from 'react'
import { Send, BrainCircuit } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/kbd'

interface QueryComposerProps {
  onSubmit: (question: string) => void | Promise<unknown>
  isLoading?: boolean
  placeholder?: string
}

export function QueryComposer({
  onSubmit,
  isLoading,
  placeholder = 'Ask anything about your knowledge base...',
}: QueryComposerProps) {
  const [question, setQuestion] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [question])

  const handleSubmit = useCallback(() => {
    const trimmed = question.trim()
    if (trimmed && !isLoading) {
      void onSubmit(trimmed)
      setQuestion('')
    }
  }, [question, isLoading, onSubmit])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
      // Also submit on plain Enter if not shift
      if (e.key === 'Enter' && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit]
  )

  return (
    <div className="relative">
      <div className="group relative rounded-2xl surface transition-all focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/15">
        <div className="relative flex items-end gap-2 p-3">
          {/* Input */}
          <textarea
            ref={textareaRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isLoading}
            rows={1}
            className="max-h-[200px] min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm leading-relaxed placeholder:text-muted-foreground/50 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          />

          {/* Submit button */}
          <Button
            onClick={handleSubmit}
            disabled={!question.trim() || isLoading}
            size="icon"
            className="btn-glow h-10 w-10 shrink-0 rounded-xl disabled:shadow-none"
          >
            {isLoading ? (
              <BrainCircuit className="h-4 w-4 animate-pulse" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Hint text */}
      <div className="mt-2 flex items-center justify-center gap-2 text-xs text-muted-foreground/50">
        <span>Press</span>
        <Kbd className="border-border/40 bg-muted/20">Enter</Kbd>
        <span>to send, or</span>
        <Kbd className="border-border/40 bg-muted/20">Shift</Kbd>
        <span>+</span>
        <Kbd className="border-border/40 bg-muted/20">Enter</Kbd>
        <span>for new line</span>
      </div>
    </div>
  )
}
