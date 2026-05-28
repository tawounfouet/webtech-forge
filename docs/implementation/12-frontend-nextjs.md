# 12 — Frontend Next.js

> **ADR de référence :** ADR-003
> **Dépendances :** 05-api-drf.md, 21-websocket-auth.md

---

## Structure App Router

```
frontend/app/
├── (auth)/
│   ├── login/page.tsx
│   └── mfa/page.tsx
└── (dashboard)/
    ├── layout.tsx                  # Layout principal avec sidebar
    ├── workspaces/
    │   ├── page.tsx                # Liste des workspaces
    │   └── [slug]/
    │       ├── page.tsx            # Dashboard workspace
    │       └── settings/page.tsx
    ├── projects/[id]/
    │   ├── page.tsx
    │   └── environments/[envId]/
    │       ├── page.tsx
    │       └── services/
    │           ├── page.tsx
    │           ├── new/page.tsx
    │           └── [serviceId]/
    │               ├── page.tsx
    │               └── deployments/
    │                   └── [deployId]/page.tsx
    ├── monitor/
    │   ├── page.tsx                # Monitor Hub — activité
    │   ├── capacity/page.tsx
    │   └── alerts/page.tsx
    ├── catalog/
    │   ├── page.tsx                # Liste des templates
    │   └── [id]/page.tsx
    └── activator/
        ├── page.tsx                # Liste des règles
        └── new/page.tsx
```

---

## Client API typé

```typescript
// frontend/lib/api-client.ts
// Types générés depuis openapi.yaml via openapi-typescript
import type { paths } from "./api.d.ts"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1"

class ForgeAPIClient {
  private token: string | null = null

  setToken(token: string) {
    this.token = token
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    }
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`
    }
    const workspaceSlug = this.getWorkspaceFromPath()
    if (workspaceSlug) {
      headers["X-Workspace-Slug"] = workspaceSlug
    }

    const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })
    if (!res.ok) {
      const error = await res.json().catch(() => ({}))
      throw new APIError(res.status, error)
    }
    return res.json()
  }

  private getWorkspaceFromPath(): string | null {
    if (typeof window === "undefined") return null
    const match = window.location.pathname.match(/\/workspaces\/([^/]+)/)
    return match?.[1] ?? null
  }

  // Services
  async getServices(environmentId: number) {
    return this.request<{ results: Service[] }>(`/environments/${environmentId}/services/`)
  }

  async deployService(serviceId: number) {
    return this.request<{ deployment_id: number }>(`/services/${serviceId}/deploy/`, {
      method: "POST",
    })
  }

  async rollbackDeployment(deploymentId: number) {
    return this.request<{ deployment_id: number }>(`/deployments/${deploymentId}/rollback/`, {
      method: "POST",
    })
  }

  // Monitor Hub
  async getActivity(params: { since_hours?: number; kind?: string } = {}) {
    const qs = new URLSearchParams(params as any).toString()
    return this.request<{ events: ActivityEvent[] }>(`/monitor/activity/?${qs}`)
  }

  async getCapacity() {
    return this.request<{ workspaces: WorkspaceCapacity[] }>("/monitor/capacity/")
  }

  // Templates
  async getTemplates() {
    return this.request<{ results: ServiceTemplate[] }>("/catalog/templates/")
  }

  async endorseTemplate(templateId: number, level: "promoted" | "certified") {
    return this.request(`/catalog/templates/${templateId}/endorse/`, {
      method: "POST",
      body: JSON.stringify({ level }),
    })
  }

  // Activator
  async getActivatorRules(workspaceSlug: string) {
    return this.request<{ results: ActivatorRule[] }>(
      `/workspaces/${workspaceSlug}/activator/rules/`
    )
  }
}

export const api = new ForgeAPIClient()

class APIError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API Error ${status}`)
  }
}
```

---

## Hook WebSocket pour streaming de logs

```typescript
// frontend/lib/hooks/useDeploymentLogs.ts
"use client"
import { useEffect, useRef, useState } from "react"

interface LogLine {
  phase: string
  message: string
  level: "info" | "warn" | "error"
  emitted_at: string
}

export function useDeploymentLogs(deploymentId: number) {
  const [logs, setLogs] = useState<LogLine[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const token = localStorage.getItem("forge_token")
    if (!token) return

    const ws = new WebSocket(
      `${process.env.NEXT_PUBLIC_WS_URL}/ws/logs/${deploymentId}/`
    )
    wsRef.current = ws

    ws.onopen = () => {
      // Auth par premier frame
      ws.send(JSON.stringify({ type: "auth", token }))
      setConnected(true)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === "log.message") {
        setLogs((prev) => [
          ...prev,
          {
            phase: data.phase,
            message: data.message,
            level: data.level ?? "info",
            emitted_at: new Date().toISOString(),
          },
        ])
      }
    }

    ws.onclose = () => setConnected(false)

    return () => ws.close()
  }, [deploymentId])

  return { logs, connected }
}
```

---

## Composant DeploymentLogs

```tsx
// frontend/components/deployments/DeploymentLogs.tsx
"use client"
import { useDeploymentLogs } from "@/lib/hooks/useDeploymentLogs"
import { useEffect, useRef } from "react"

const LEVEL_COLORS = {
  info: "text-gray-300",
  warn: "text-yellow-400",
  error: "text-red-400",
}

const PHASE_BADGES = {
  bronze: "bg-amber-800 text-amber-100",
  silver: "bg-gray-600 text-gray-100",
  gold: "bg-yellow-600 text-yellow-100",
}

export function DeploymentLogs({ deploymentId }: { deploymentId: number }) {
  const { logs, connected } = useDeploymentLogs(deploymentId)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  return (
    <div className="bg-black rounded-lg p-4 font-mono text-sm h-96 overflow-y-auto">
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-gray-500"}`} />
        <span className="text-gray-400 text-xs">{connected ? "Live" : "Disconnected"}</span>
      </div>
      {logs.map((log, i) => (
        <div key={i} className="flex gap-3 mb-1">
          <span className={`text-xs px-1 rounded ${PHASE_BADGES[log.phase as keyof typeof PHASE_BADGES] ?? ""}`}>
            {log.phase}
          </span>
          <span className={LEVEL_COLORS[log.level]}>{log.message}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
```

---

## Page Monitor Hub

```tsx
// frontend/app/(dashboard)/monitor/page.tsx
import { api } from "@/lib/api-client"

export default async function MonitorPage() {
  const [activity, capacity, alerts] = await Promise.all([
    api.getActivity({ since_hours: 24 }),
    api.getCapacity(),
    api.request<{ alerts: Alert[] }>("/monitor/alerts/?since_hours=48"),
  ])

  return (
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2">
        <h2 className="text-lg font-semibold mb-4">Activité récente</h2>
        <ActivityFeed events={activity.events} />
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-4">Capacité</h2>
        <CapacityCards workspaces={capacity.workspaces} />
        <h2 className="text-lg font-semibold mt-6 mb-4">Alertes Activator</h2>
        <AlertsList alerts={alerts.alerts} />
      </div>
    </div>
  )
}
```

---

## Variables d'environnement Next.js

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=https://forge.internal/api/v1
NEXT_PUBLIC_WS_URL=wss://forge.internal
```
