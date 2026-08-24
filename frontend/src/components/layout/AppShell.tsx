import type { ReactNode } from 'react'

type AppShellProps = {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-border bg-panel">
        <div className="mx-auto flex w-full max-w-[1300px] items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">TrustSignal</p>
            <h1 className="text-lg font-semibold text-ink">SOC 2 Analyzer</h1>
          </div>
          <div id="header-actions" className="flex items-center" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1300px] px-6 py-10">{children}</main>
    </div>
  )
}
