'use client'

import { ReactNode } from 'react'

interface FadeInProps {
  children: ReactNode
  delay?: number
  direction?: 'up' | 'down' | 'left' | 'right' | 'none'
  className?: string
  duration?: number
}

export function FadeIn({ children, delay = 0, direction = 'up', className = '', duration = 0.5 }: FadeInProps) {
  void delay
  void direction
  void duration

  return (
    <div className={className}>
      {children}
    </div>
  )
}

export function StaggerContainer({ children, className = '' }: { children: ReactNode, className?: string }) {
  return <div className={className}>{children}</div>
}

export function StaggerItem({ children, className = '' }: { children: ReactNode, className?: string }) {
  return <div className={className}>{children}</div>
}
