import { HealthCheck } from '@/components/health-check'

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-white mb-1">
          AI Agent Observatory
        </h1>
        <p className="text-zinc-500 text-sm">
          Multi-tenant agent testing and observability platform
        </p>
      </div>

      <HealthCheck />

      <p className="text-zinc-600 text-xs">
        M1 — Project skeleton ✓
      </p>
    </main>
  )
}
