'use client'

import { useEffect, useState } from 'react'

type HealthStatus = 'checking' | 'ok' | 'error'

interface HealthData {
  status: string
  version: string
  env: string
}

export function HealthCheck() {
  const [status, setStatus] = useState<HealthStatus>('checking')
  const [data, setData] = useState<HealthData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/health`
        )
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        setData(json)
        setStatus('ok')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Connection failed')
        setStatus('error')
      }
    }

    check()
  }, [])

  return (
    <div className="flex items-center gap-2 text-sm font-mono">
      {status === 'checking' && (
        <>
          <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
          <span className="text-zinc-400">Connecting to backend...</span>
        </>
      )}
      {status === 'ok' && (
        <>
          <span className="h-2 w-2 rounded-full bg-green-400" />
          <span className="text-green-400">
            Backend {data?.status} — v{data?.version} ({data?.env})
          </span>
        </>
      )}
      {status === 'error' && (
        <>
          <span className="h-2 w-2 rounded-full bg-red-400" />
          <span className="text-red-400">Backend unreachable: {error}</span>
        </>
      )}
    </div>
  )
}
