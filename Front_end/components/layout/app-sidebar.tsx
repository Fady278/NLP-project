'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  MessageCircleQuestion,
  FileUp,
  Search,
  Users,
  ChevronRight,
  Zap,
  Sun,
  Moon,
} from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from '@/components/ui/sidebar'
import { useTheme } from '@/components/theme-provider'
import { useMockMode } from '@/lib/hooks/use-api-mode'

const userNavItems = [
  {
    title: 'Ask AI',
    href: '/ask',
    icon: MessageCircleQuestion,
    description: 'Query your knowledge base',
  },
  {
    title: 'Team',
    href: '/team',
    icon: Users,
    description: 'Meet our members',
  },
]

const adminNavItems = [
  {
    title: 'Overview',
    href: '/',
    icon: LayoutDashboard,
    description: 'System health & metrics',
  },
  {
    title: 'Ingest',
    href: '/ingest',
    icon: FileUp,
    description: 'Upload documents',
  },
  {
    title: 'Retrieval',
    href: '/retrieval',
    icon: Search,
    description: 'Inspect chunks',
  },
]

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <button
        className="group flex w-full items-center justify-between rounded-lg bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
        aria-label="Toggle theme"
      >
        <div className="flex items-center gap-2.5">
          <div className="relative h-4 w-4 overflow-hidden" />
          <span className="text-xs font-medium">Theme</span>
        </div>
        <div className="flex h-5 w-9 items-center rounded-full bg-border/60 p-0.5 transition-colors">
          <div className="h-4 w-4 rounded-full bg-primary/50 shadow-sm" />
        </div>
      </button>
    )
  }

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="group flex w-full items-center justify-between rounded-lg bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
      aria-label="Toggle theme"
    >
      <div className="flex items-center gap-2.5">
        <div className="relative h-4 w-4 overflow-hidden">
          <Sun className="absolute inset-0 h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute inset-0 h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </div>
        <span className="text-xs font-medium">
          {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
        </span>
      </div>
      <div className="flex h-5 w-9 items-center rounded-full bg-border/60 p-0.5 transition-colors">
        <div className={`h-4 w-4 rounded-full bg-primary shadow-sm transition-transform ${theme === 'dark' ? 'translate-x-4' : 'translate-x-0'}`} />
      </div>
    </button>
  )
}

export function AppSidebar() {
  const pathname = usePathname()
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const { mockMode, setMockMode } = useMockMode()

  useEffect(() => {
    setMounted(true)
  }, [])

  const detectiveIcon =
    mounted && resolvedTheme === 'dark'
      ? '/detective-icon-dark.png'
      : '/detective-icon-light.png'

  return (
    <Sidebar className="border-r-0">
      <SidebarHeader className="px-4 py-5">
        <Link href="/" className="group flex items-center gap-3">
          <div className="relative flex h-11 w-11 items-center justify-center">
            <div className="absolute inset-0 rounded-2xl bg-primary/15 blur-md transition-all group-hover:bg-primary/25" />
            <div className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/80 p-0.5 shadow-[0_10px_24px_rgba(11,58,114,0.18)] ring-1 ring-white/6">
              <Image
                src={detectiveIcon}
                alt="RAG Console detective mark"
                width={44}
                height={44}
                className="h-10 w-10 object-cover"
                priority
              />
            </div>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold tracking-tight text-foreground">
              RAG Console
            </span>
            <span className="label-caps mt-0.5">
              Knowledge AI
            </span>
          </div>
        </Link>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <SidebarGroup>
          <SidebarGroupLabel className="px-3 label-caps">
            Explore
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {userNavItems.map((item) => {
                const isActive = pathname === item.href
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className="group/item relative h-12 gap-3 rounded-lg px-3 transition-all hover:bg-sidebar-accent data-[active=true]:bg-sidebar-accent"
                    >
                      <Link href={item.href}>
                        <div
                          className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                            isActive
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground group-hover/item:bg-primary/10 group-hover/item:text-primary'
                          }`}
                        >
                          <item.icon className="h-4 w-4" />
                        </div>
                        <div className="flex flex-1 flex-col">
                          <span className="text-sm font-medium">{item.title}</span>
                          <span className="text-[11px] text-muted-foreground">
                            {item.description}
                          </span>
                        </div>
                        <ChevronRight
                          className={`h-4 w-4 text-muted-foreground/40 transition-all ${
                            isActive ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1 group-hover/item:opacity-100 group-hover/item:translate-x-0'
                          }`}
                        />
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="mt-4">
          <SidebarGroupLabel className="px-3 label-caps">
            Admin
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {adminNavItems.map((item) => {
                const isActive = pathname === item.href
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className="group/item relative h-12 gap-3 rounded-lg px-3 transition-all hover:bg-sidebar-accent data-[active=true]:bg-sidebar-accent"
                    >
                      <Link href={item.href}>
                        <div
                          className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                            isActive
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground group-hover/item:bg-primary/10 group-hover/item:text-primary'
                          }`}
                        >
                          <item.icon className="h-4 w-4" />
                        </div>
                        <div className="flex flex-1 flex-col">
                          <span className="text-sm font-medium">{item.title}</span>
                          <span className="text-[11px] text-muted-foreground">
                            {item.description}
                          </span>
                        </div>
                        <ChevronRight
                          className={`h-4 w-4 text-muted-foreground/40 transition-all ${
                            isActive ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1 group-hover/item:opacity-100 group-hover/item:translate-x-0'
                          }`}
                        />
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4 space-y-2">
        <ThemeToggle />

        <button
          type="button"
          onClick={() => setMockMode(!mockMode)}
          className="flex w-full items-center justify-between rounded-lg bg-muted/40 px-3 py-2.5 text-left transition-colors hover:bg-sidebar-accent"
        >
          <div className="flex items-center gap-2.5">
            <span className={`status-dot ${mockMode ? 'status-dot--warn' : 'status-dot--ok'}`} style={{ width: 7, height: 7 }} />
            <span className="text-xs font-medium text-muted-foreground">
              {mockMode ? 'Mock Mode' : 'Live Backend'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground">
              {mockMode ? 'Blend/fallback' : 'Real only'}
            </span>
            <Zap className={`h-3.5 w-3.5 ${mockMode ? 'text-warning' : 'text-success'}`} />
          </div>
        </button>
      </SidebarFooter>
    </Sidebar>
  )
}
