import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { Providers } from './providers'
import { AppSidebar } from '@/components/layout/app-sidebar'
import { TopBarBrand } from '@/components/layout/top-bar-brand'
import { TopThemeToggle } from '@/components/layout/top-theme-toggle'
import { SidebarProvider, SidebarInset, SidebarTrigger } from '@/components/ui/sidebar'
import './globals.css'

export const metadata: Metadata = {
  title: 'RAG Console — Knowledge AI',
  description: 'Knowledge management and retrieval-augmented generation console',
}

export const viewport: Viewport = {
  themeColor: '#d89a3f',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning className="bg-background font-sans antialiased">
        <Providers>
          <SidebarProvider>
            <AppSidebar />
            <SidebarInset className="noise-texture gradient-bg flex flex-col h-screen overflow-hidden">
              <header className="sticky shrink-0 top-0 z-10 flex h-14 items-center gap-3 border-b border-border/40 bg-background/80 px-6 backdrop-blur-xl">
                <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground transition-colors" />
                <div className="h-4 w-px bg-border/60" />
                <TopBarBrand />
                <div className="ml-auto">
                  <TopThemeToggle />
                </div>
              </header>
              <main className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden">{children}</main>
            </SidebarInset>
          </SidebarProvider>
        </Providers>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
