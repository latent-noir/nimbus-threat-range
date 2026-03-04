"use client"

import { useEffect, useState, useCallback, useMemo } from "react"
import {
  fetchSystemState, injectAttack, fetchIDSAlerts, fetchIDSStats,
  fetchAuditTrail, deriveNetworkTopology,
  type SystemState, type SimulationEvent, type IDSStats, type NetworkTopology,
} from "@/lib/api"
import { formatBytes, cpuColor, timeAgo } from "@/lib/utils"
import {
  Activity, Server, Cpu, AlertTriangle, Shield, ShieldAlert, Zap, Network,
  BarChart3, Terminal, Crosshair, RefreshCw, Flame, Eye, Clock,
  FileWarning, Wifi, WifiOff, ChevronRight, Lock, Search, Filter,
} from "lucide-react"
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar, Cell,
} from "recharts"

// ── Types ─────────────────────────────────────────────────────
type TabType = "overview" | "events" | "ids" | "audit" | "network"

const TABS: { key: TabType; label: string; icon: React.ElementType }[] = [
  { key: "overview", label: "Overview", icon: BarChart3 },
  { key: "events", label: "Events", icon: Terminal },
  { key: "ids", label: "IDS", icon: ShieldAlert },
  { key: "audit", label: "Audit", icon: FileWarning },
  { key: "network", label: "Network", icon: Network },
]

// ── Helpers ───────────────────────────────────────────────────
function statusClass(s: string) {
  const map: Record<string, string> = {
    RUNNING: "status-running", STOPPED: "status-stopped",
    CRASHED: "status-crashed", COMPROMISED: "status-compromised", CREATING: "status-creating",
  }
  return map[s] ?? "status-stopped"
}

function severityIcon(l: string) {
  return { critical: "🔴", high: "🟠", medium: "🟡", low: "🟢", info: "⚪" }[l] ?? "⚪"
}

function severityColor(l: string) {
  return { critical: "#ef4444", high: "#f97316", medium: "#eab308", low: "#22c55e", info: "#3b82f6" }[l] ?? "#94a3b8"
}

function eventColor(type: string) {
  if (type?.startsWith("attack.")) return "#f87171"
  if (type?.startsWith("security.")) return "#fbbf24"
  if (type?.startsWith("infra.")) return "#38bdf8"
  return "#94a3b8"
}

// ── Sub-components ────────────────────────────────────────────

function ParticleField() {
  const [particles, setParticles] = useState<Array<{
    id: number; left: string; top: string; delay: string;
    size: number; opacity: number; duration: string;
  }>>([])

  useEffect(() => {
    setParticles(Array.from({ length: 25 }, (_, i) => ({
      id: i, left: `${Math.random() * 100}%`, top: `${Math.random() * 100}%`,
      delay: `${Math.random() * 8}s`, size: Math.random() * 2 + 1,
      opacity: Math.random() * 0.14 + 0.04, duration: `${6 + Math.random() * 6}s`,
    })))
  }, [])

  return (
    <div className="particles-bg">
      {particles.map(p => (
        <div key={p.id} className="particle" style={{
          left: p.left, top: p.top, width: p.size, height: p.size,
          opacity: p.opacity, animationDelay: p.delay, animationDuration: p.duration,
        }} />
      ))}
    </div>
  )
}

function MetricCard({ icon, label, value, color, delay = 0 }: {
  icon: React.ReactNode; label: string; value: string | number; color: string; delay?: number
}) {
  return (
    <div className="metric-card animate-slide-up" style={{ animationDelay: `${delay}s` }}>
      <div className="flex items-center gap-2 mb-3">
        <div style={{ color }}>{icon}</div>
        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#4a5568" }}>{label}</span>
      </div>
      <p className="text-2xl font-bold animate-count-in" style={{ color, animationDelay: `${delay + 0.1}s` }}>{value}</p>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="metric-card">
      <div className="skeleton h-3 w-16 mb-3 rounded" />
      <div className="skeleton h-7 w-12 rounded" />
    </div>
  )
}

function CpuBarRow({ label, value, extra }: { label: string; value: number; extra?: string }) {
  const color = cpuColor(value)
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] w-28 truncate font-mono" style={{ color: "#94a3b8" }}>{label}</span>
      <div className="flex-1 cpu-bar">
        <div className="cpu-bar-fill" style={{
          width: `${Math.min(100, value)}%`,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
        }} />
      </div>
      <span className="text-[11px] font-mono w-10 text-right" style={{ color }}>{value.toFixed(1)}%</span>
      {extra && <span className="text-[10px] w-24 text-right hidden xl:block" style={{ color: "#4a5568" }}>{extra}</span>}
    </div>
  )
}

// ── Network Topology SVG ──────────────────────────────────────
function TopologyView({ topology }: { topology: NetworkTopology }) {
  const [hovered, setHovered] = useState<string | null>(null)

  const { nodes, edges } = topology
  const W = 900, H = 420

  // Layout: subnets in row 1, VMs in row 2, containers in row 3
  const subnets = nodes.filter(n => n.type === "subnet")
  const vms = nodes.filter(n => n.type === "vm")
  const containers = nodes.filter(n => n.type === "container")

  function assign(arr: typeof nodes, y: number) {
    const xStep = arr.length > 1 ? (W - 120) / (arr.length - 1) : 0
    arr.forEach((n, i) => {
      n.x = arr.length === 1 ? W / 2 : 60 + i * xStep
      n.y = y
    })
  }
  assign(subnets, 60)
  assign(vms, 190)
  assign(containers, 340)

  const posMap: Record<string, { x: number; y: number }> = {}
  nodes.forEach(n => { if (n.x !== undefined && n.y !== undefined) posMap[n.id] = { x: n.x, y: n.y } })

  const nodeColor = (type: string, status: string) => {
    if (status === "CRASHED" || status === "COMPROMISED") return "#ef4444"
    if (type === "subnet") return "#8b5cf6"
    if (type === "vm") return "#3b82f6"
    if (type === "container") return "#06b6d4"
    return "#94a3b8"
  }

  if (nodes.length === 0) {
    return (
      <div className="text-center py-16">
        <Network className="h-12 w-12 mx-auto mb-3" style={{ color: "#2a2f45" }} />
        <p className="text-sm" style={{ color: "#4a5568" }}>No network data available</p>
        <p className="text-xs mt-1" style={{ color: "#2a2f45" }}>Start the simulation engine to see topology</p>
      </div>
    )
  }

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="topology-svg" style={{ height: 420 }}>
        {/* Grid lines */}
        {[60, 190, 340].map(y => (
          <line key={y} x1={0} y1={y} x2={W} y2={y} stroke="rgba(26,31,53,0.25)" strokeWidth={1} strokeDasharray="4 6" />
        ))}
        {/* Layer labels */}
        {[{ y: 60, label: "SUBNETS", color: "#8b5cf6" }, { y: 190, label: "VMs", color: "#3b82f6" }, { y: 340, label: "CONTAINERS", color: "#06b6d4" }].map(l => (
          <text key={l.y} x={8} y={l.y - 14} fontSize={9} fill={l.color} fontWeight={700} letterSpacing="0.1em" opacity={0.7}>{l.label}</text>
        ))}
        {/* Edges */}
        {edges.map((e, i) => {
          const from = posMap[e.from]; const to = posMap[e.to]
          if (!from || !to) return null
          const isHovered = hovered === e.from || hovered === e.to
          return (
            <path key={i}
              d={`M${from.x},${from.y} C${from.x},${(from.y + to.y) / 2} ${to.x},${(from.y + to.y) / 2} ${to.x},${to.y}`}
              className={isHovered ? "topo-edge topo-edge-active" : "topo-edge"}
              style={{ opacity: isHovered ? 0.9 : 0.5 }}
            />
          )
        })}
        {/* Nodes */}
        {nodes.map(n => {
          if (n.x === undefined || n.y === undefined) return null
          const color = nodeColor(n.type, n.status)
          const isH = hovered === n.id
          const r = n.type === "subnet" ? 22 : n.type === "vm" ? 18 : 14
          return (
            <g key={n.id} className="topo-node" onMouseEnter={() => setHovered(n.id)} onMouseLeave={() => setHovered(null)}>
              {isH && <circle cx={n.x} cy={n.y} r={r + 8} fill={color} opacity={0.1} />}
              <circle cx={n.x} cy={n.y} r={r} fill={`${color}22`} stroke={color} strokeWidth={isH ? 2 : 1.5} />
              <text x={n.x} y={n.y + 4} textAnchor="middle" fontSize={n.type === "container" ? 8 : 9} fill={color} fontWeight={700}>
                {n.type === "subnet" ? "NET" : n.type === "vm" ? "VM" : "CTR"}
              </text>
              <text x={n.x} y={n.y + r + 14} textAnchor="middle" fontSize={8} fill="#94a3b8">
                {n.label.length > 12 ? n.label.slice(0, 12) + "…" : n.label}
              </text>
              {(n.status === "CRASHED" || n.status === "COMPROMISED") && (
                <circle cx={n.x + r - 4} cy={n.y - r + 4} r={5} fill="#ef4444" stroke="#060611" strokeWidth={1.5} />
              )}
            </g>
          )
        })}
      </svg>
      {/* Legend */}
      <div className="flex gap-4 mt-3 flex-wrap">
        {[
          { color: "#8b5cf6", label: "Subnet" }, { color: "#3b82f6", label: "VM" },
          { color: "#06b6d4", label: "Container" }, { color: "#ef4444", label: "Compromised/Crashed" },
        ].map(l => (
          <div key={l.label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: l.color }} />
            <span className="text-[10px]" style={{ color: "#4a5568" }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────
export default function Dashboard() {
  const [state, setState] = useState<SystemState | null>(null)
  const [cpuHistory, setCpuHistory] = useState<{ tick: number; load: number }[]>([])
  const [alerts, setAlerts] = useState<SimulationEvent[]>([])
  const [auditTrail, setAuditTrail] = useState<SimulationEvent[]>([])
  const [idsStats, setIdsStats] = useState<IDSStats>({ events_analyzed: 0, alerts_generated: 0, rules_matched: 0 })
  const [topology, setTopology] = useState<NetworkTopology>({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attackTarget, setAttackTarget] = useState("")
  const [attackType, setAttackType] = useState("ddos")
  const [attackSeverity, setAttackSeverity] = useState(80)
  const [attacking, setAttacking] = useState(false)
  const [attackFlash, setAttackFlash] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>("overview")
  const [eventFilter, setEventFilter] = useState("all")
  const [eventSearch, setEventSearch] = useState("")
  const [idsFilter, setIdsFilter] = useState("all")

  const refresh = useCallback(async () => {
    try {
      const [data, alertData, stats, audit] = await Promise.all([
        fetchSystemState(),
        fetchIDSAlerts(50),
        fetchIDSStats(),
        fetchAuditTrail(100),
      ])
      setState(data)
      setAlerts(alertData)
      setIdsStats(stats)
      setAuditTrail(audit)
      setTopology(deriveNetworkTopology(data))
      setError(null)
      setLoading(false)
      setCpuHistory(prev => [...prev.slice(-50), { tick: data.tick, load: data.metrics.global_cpu_load }])
      if (!attackTarget && data.containers.length > 0) setAttackTarget(data.containers[0].id)
    } catch {
      setError("Cannot connect to simulation engine")
      setLoading(false)
    }
  }, [attackTarget])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 1500)
    return () => clearInterval(id)
  }, [refresh])

  const handleAttack = async () => {
    if (!attackTarget) return
    setAttacking(true); setAttackFlash(true)
    try { await injectAttack(attackTarget, attackType, attackSeverity) }
    catch (e) { console.error("Attack failed:", e) }
    finally {
      setTimeout(() => setAttacking(false), 1000)
      setTimeout(() => setAttackFlash(false), 500)
    }
  }

  // ── Loading State ──────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#060611" }}>
        <ParticleField />
        <div className="text-center relative z-10 animate-slide-up">
          <div className="relative mb-8">
            <div className="w-20 h-20 mx-auto rounded-full flex items-center justify-center"
              style={{ background: "radial-gradient(circle, rgba(6,182,212,0.15) 0%, transparent 70%)" }}>
              <Shield className="h-10 w-10 animate-pulse-glow" style={{ color: "#06b6d4" }} />
            </div>
            <div className="absolute inset-0 w-20 h-20 mx-auto rounded-full animate-glow-pulse" />
          </div>
          <h2 className="text-2xl font-bold mb-3 gradient-text">CyberSim Monitor</h2>
          <p className="text-sm mb-6" style={{ color: "#4a5568" }}>Initializing secure connection…</p>
          <div className="flex gap-1.5 justify-center">
            {[0, 1, 2, 3, 4].map(i => (
              <div key={i} className="w-1.5 h-6 rounded-full" style={{
                background: "#06b6d4", opacity: 0.2 + i * 0.15,
                animation: "pulse-glow 1.5s ease-in-out infinite", animationDelay: `${i * 0.15}s`,
              }} />
            ))}
          </div>
          <div className="mt-8 grid grid-cols-4 gap-3 max-w-sm mx-auto">
            {[0, 1, 2, 3].map(i => <SkeletonCard key={i} />)}
          </div>
        </div>
      </div>
    )
  }

  // ── Error State ────────────────────────────────────────────
  if (error && !state) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#060611" }}>
        <ParticleField />
        <div className="text-center glass-card p-10 max-w-lg relative z-10 animate-slide-up">
          <div className="w-16 h-16 mx-auto mb-6 rounded-full flex items-center justify-center"
            style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}>
            <WifiOff className="h-7 w-7" style={{ color: "#ef4444" }} />
          </div>
          <h2 className="text-xl font-bold mb-2" style={{ color: "#e2e8f0" }}>Engine Offline</h2>
          <p className="mb-4 text-sm" style={{ color: "#64748b" }}>{error}</p>
          <div className="p-3 rounded-xl mb-6 text-left" style={{ background: "#0b0e1c", border: "1px solid #1a1f35" }}>
            <p className="text-xs font-mono" style={{ color: "#94a3b8" }}>
              <span style={{ color: "#22c55e" }}>$</span>{" "}
              <span style={{ color: "#06b6d4" }}>cd</span> core &amp;&amp;{" "}
              <span style={{ color: "#8b5cf6" }}>python</span> main.py
            </p>
          </div>
          <button onClick={refresh} className="attack-btn" style={{ background: "linear-gradient(135deg,#3b82f6,#2563eb)" }}>
            <RefreshCw className="h-4 w-4" /> Retry Connection
          </button>
        </div>
      </div>
    )
  }

  if (!state) return null

  const { metrics, containers, vms } = state
  const activeContainers = containers.filter(c => c.status === "RUNNING").length
  const crashedContainers = containers.filter(c => c.status === "CRASHED").length
  const compromisedVMs = vms.filter(v => v.status === "COMPROMISED").length
  const attackEvents = state.recent_events.filter(e => e.event_type?.startsWith("attack."))

  const filteredEvents = state.recent_events
    .filter(e => eventFilter === "all" || e.event_type?.startsWith(eventFilter + "."))
    .filter(e => !eventSearch || e.event_type?.toLowerCase().includes(eventSearch.toLowerCase()) ||
      e.source?.toLowerCase().includes(eventSearch.toLowerCase()) ||
      e.target_id?.toLowerCase().includes(eventSearch.toLowerCase()))

  const filteredAlerts = alerts.filter(a => idsFilter === "all" || a.threat_level === idsFilter)

  return (
    <div className="min-h-screen relative" style={{ background: "#060611" }}>
      <ParticleField />

      {attackFlash && (
        <div className="fixed inset-0 z-50 pointer-events-none"
          style={{ background: "radial-gradient(circle at center, rgba(239,68,68,0.09), transparent 70%)", animation: "fade-in 0.3s" }} />
      )}

      {/* ── Header ── */}
      <header className="border-b px-6 py-3 flex items-center justify-between relative"
        style={{ borderColor: "#1a1f35", background: "rgba(6,6,17,0.94)", backdropFilter: "blur(24px)", position: "sticky", top: 0, zIndex: 40 }}>
        <div className="header-glow" />

        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center animate-glow-pulse"
            style={{ background: "linear-gradient(135deg,rgba(6,182,212,0.15),rgba(139,92,246,0.15))", border: "1px solid rgba(6,182,212,0.2)" }}>
            <Shield className="h-5 w-5" style={{ color: "#06b6d4" }} />
          </div>
          <div>
            <h1 className="text-base font-bold gradient-text">CyberSim Monitor</h1>
            <div className="flex items-center gap-2">
              <p className="text-[10px] font-mono" style={{ color: "#4a5568" }}>TICK #{state.tick}</p>
              <span style={{ color: "#2a2f45" }}>•</span>
              <p className="text-[10px] font-mono animate-flicker" style={{ color: "#22c55e" }}>LIVE</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <nav className="flex gap-0.5 p-1 rounded-xl" style={{ background: "#0b0e1c", border: "1px solid #1a1f35" }}>
            {TABS.map(({ key, label, icon: Icon }) => (
              <button key={key} id={`tab-${key}`} onClick={() => setActiveTab(key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${activeTab === key ? "tab-active" : "tab-inactive"}`}>
                <Icon className="h-3.5 w-3.5" />{label}
              </button>
            ))}
          </nav>

          {error && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold animate-pulse-glow"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#ef4444" }}>
              <WifiOff className="h-3 w-3" /> Stale data
            </div>
          )}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold"
            style={{ background: "rgba(34,197,94,0.07)", border: "1px solid rgba(34,197,94,0.18)", color: "#22c55e" }}>
            <div className="ring-indicator" style={{ background: "#22c55e", color: "#22c55e" }} /> Online
          </div>
        </div>
      </header>

      <main className="p-5 max-w-[1720px] mx-auto space-y-4 relative z-10">

        {/* ── KPI Metric Cards ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          <MetricCard icon={<Server className="h-4 w-4" />} label="VMs" value={metrics.total_vms} color="#3b82f6" delay={0} />
          <MetricCard icon={<Cpu className="h-4 w-4" />} label="Containers" value={metrics.total_containers} color="#8b5cf6" delay={0.05} />
          <MetricCard icon={<Activity className="h-4 w-4" />} label="Active" value={activeContainers} color="#22c55e" delay={0.1} />
          <MetricCard icon={<Flame className="h-4 w-4" />} label="Crashed" value={crashedContainers} color={crashedContainers > 0 ? "#ef4444" : "#22c55e"} delay={0.15} />
          <MetricCard icon={<AlertTriangle className="h-4 w-4" />} label="Compromised" value={compromisedVMs} color={compromisedVMs > 0 ? "#f97316" : "#22c55e"} delay={0.2} />
          <MetricCard icon={<ShieldAlert className="h-4 w-4" />} label="IDS Alerts" value={idsStats.alerts_generated} color={idsStats.alerts_generated > 0 ? "#f97316" : "#22c55e"} delay={0.25} />
          <MetricCard icon={<Zap className="h-4 w-4" />} label="CPU Load" value={`${metrics.global_cpu_load.toFixed(1)}%`} color={cpuColor(metrics.global_cpu_load)} delay={0.3} />
        </div>

        {/* ══════════ OVERVIEW TAB ══════════ */}
        {activeTab === "overview" && (
          <>
            <div className="grid gap-4 lg:grid-cols-5">
              {/* CPU Chart */}
              <div className="lg:col-span-3 glass-card p-5 animate-slide-up">
                <div className="section-header">
                  <BarChart3 className="h-4 w-4" style={{ color: "#06b6d4" }} />
                  Global CPU Load — Live
                  <div className="ml-auto info-badge" style={{ background: "rgba(6,182,212,0.08)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.15)" }}>
                    <Clock className="h-3 w-3" /> {cpuHistory.length} ticks
                  </div>
                </div>
                <div style={{ height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={cpuHistory}>
                      <defs>
                        <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.28} />
                          <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="tick" stroke="#2a2f45" fontSize={10} tickLine={false} axisLine={false} tick={{ fill: "#4a5568" }} />
                      <YAxis stroke="#2a2f45" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} tick={{ fill: "#4a5568" }} />
                      <Tooltip contentStyle={{ background: "#0b0e1c", border: "1px solid #1a1f35", borderRadius: 12, color: "#e2e8f0", fontSize: 12 }}
                        labelFormatter={(v: string | number) => `Tick ${v}`}
                        formatter={(v: number) => [`${v.toFixed(1)}%`, "CPU"]} />
                      <Area type="monotone" dataKey="load" stroke="#06b6d4" strokeWidth={2} fill="url(#cpuGrad)"
                        dot={false} activeDot={{ r: 5, fill: "#06b6d4", stroke: "#060611", strokeWidth: 2 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Attack Panel */}
              <div className="lg:col-span-2 glass-card p-5 animate-slide-up" style={{ animationDelay: "0.1s" }}>
                <div className="section-header">
                  <Crosshair className="h-4 w-4" style={{ color: "#ef4444" }} />
                  <span className="gradient-text-red">Attack Injection</span>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="block text-[10px] font-bold mb-1.5 uppercase tracking-widest" style={{ color: "#4a5568" }}>Target Container</label>
                    <select id="attack-target" value={attackTarget} onChange={e => setAttackTarget(e.target.value)}
                      className="w-full rounded-xl px-3 py-2.5 text-sm transition-all"
                      style={{ background: "#07091a", border: "1px solid #1a1f35", color: "#e2e8f0" }}>
                      {containers.map(c => <option key={c.id} value={c.id}>{c.name} ({c.status})</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold mb-1.5 uppercase tracking-widest" style={{ color: "#4a5568" }}>Attack Vector</label>
                    <select id="attack-type" value={attackType} onChange={e => setAttackType(e.target.value)}
                      className="w-full rounded-xl px-3 py-2.5 text-sm transition-all"
                      style={{ background: "#07091a", border: "1px solid #1a1f35", color: "#e2e8f0" }}>
                      {[
                        { value: "ddos", label: "🌊 DDoS Flood" },
                        { value: "brute_force", label: "🔑 Brute Force" },
                        { value: "ransomware", label: "💀 Ransomware" },
                        { value: "sql_injection", label: "💉 SQL Injection" },
                        { value: "privilege_escalation", label: "⬆️ Privilege Escalation" },
                      ].map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold mb-1.5 uppercase tracking-widest" style={{ color: "#4a5568" }}>
                      Severity:{" "}
                      <span style={{ color: cpuColor(attackSeverity), fontFamily: "var(--font-mono)" }}>{attackSeverity}</span>
                    </label>
                    <input id="attack-severity" type="range" min={1} max={100} value={attackSeverity}
                      onChange={e => setAttackSeverity(Number(e.target.value))} className="w-full" />
                    <div className="flex justify-between text-[9px] mt-1" style={{ color: "#2a2f45" }}>
                      <span>LOW</span><span>MED</span><span>HIGH</span><span>CRIT</span>
                    </div>
                  </div>
                  <button id="launch-attack" onClick={handleAttack} disabled={attacking} className="attack-btn w-full justify-center">
                    <Zap className="h-4 w-4" />
                    {attacking ? "Injecting Payload…" : "🚀 Launch Attack"}
                  </button>
                </div>
                {/* Live attack feed */}
                <div className="mt-4 pt-3" style={{ borderTop: "1px solid #1a1f35" }}>
                  <p className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "#4a5568" }}>Live Attack Feed</p>
                  <div className="space-y-1.5 max-h-28 overflow-y-auto">
                    {attackEvents.length > 0 ? attackEvents.slice(-5).reverse().map((e, i) => (
                      <div key={e.id || i} className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-2 animate-slide-in-right"
                        style={{ background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.1)", animationDelay: `${i * 0.05}s` }}>
                        <Flame className="h-3 w-3 flex-shrink-0" style={{ color: "#ef4444" }} />
                        <span style={{ color: "#f87171" }}>{e.event_type?.replace("attack.", "")}</span>
                        <ChevronRight className="h-3 w-3" style={{ color: "#2a2f45" }} />
                        <span className="font-mono text-[10px]" style={{ color: "#64748b" }}>{e.target_id || "—"}</span>
                        <span className="ml-auto text-[9px] font-mono" style={{ color: "#2a2f45" }}>T{e.tick}</span>
                      </div>
                    )) : (
                      <p className="text-xs py-2 text-center" style={{ color: "#2a2f45" }}>No attacks recorded yet</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Container CPU Bar Chart */}
            <div className="glass-card p-5 animate-slide-up" style={{ animationDelay: "0.15s" }}>
              <div className="section-header">
                <Cpu className="h-4 w-4" style={{ color: "#8b5cf6" }} /> Container CPU Usage
              </div>
              <div style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={containers.map(c => ({ name: c.name, cpu: c.cpu_usage }))}>
                    <XAxis dataKey="name" stroke="#2a2f45" fontSize={10} tickLine={false} axisLine={false} tick={{ fill: "#4a5568" }} />
                    <YAxis stroke="#2a2f45" fontSize={10} tickLine={false} axisLine={false} domain={[0, 110]} tickFormatter={(v: number) => `${v}%`} tick={{ fill: "#4a5568" }} />
                    <Tooltip contentStyle={{ background: "#0b0e1c", border: "1px solid #1a1f35", borderRadius: 12, color: "#e2e8f0", fontSize: 12 }}
                      formatter={(v: number) => [`${v.toFixed(1)}%`, "CPU"]} />
                    <Bar dataKey="cpu" radius={[6, 6, 0, 0]} maxBarSize={48}>
                      {containers.map((c, i) => <Cell key={i} fill={cpuColor(c.cpu_usage)} fillOpacity={0.9} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Containers + VMs */}
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="glass-card p-5 animate-slide-up" style={{ animationDelay: "0.2s" }}>
                <div className="section-header">
                  <Cpu className="h-4 w-4" style={{ color: "#8b5cf6" }} /> Containers
                  <span className="info-badge ml-2" style={{ background: "rgba(139,92,246,0.08)", color: "#8b5cf6", border: "1px solid rgba(139,92,246,0.18)" }}>{containers.length}</span>
                </div>
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {containers.map(c => (
                    <div key={c.id} className="resource-row">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>{c.name}</p>
                          <span className={statusClass(c.status)}>{c.status}</span>
                        </div>
                        <span className="text-xs font-mono" style={{ color: cpuColor(c.cpu_usage) }}>{c.cpu_usage.toFixed(1)}%</span>
                      </div>
                      <p className="text-[10px] mb-2 font-mono" style={{ color: "#2a2f45" }}>{c.id} · VM: {c.vm_id}</p>
                      <CpuBarRow label="" value={c.cpu_usage} extra={`${formatBytes(c.memory_usage)} / ${formatBytes(c.memory_limit)}`} />
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass-card p-5 animate-slide-up" style={{ animationDelay: "0.25s" }}>
                <div className="section-header">
                  <Server className="h-4 w-4" style={{ color: "#3b82f6" }} /> Virtual Machines
                  <span className="info-badge ml-2" style={{ background: "rgba(59,130,246,0.08)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.18)" }}>{vms.length}</span>
                </div>
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {vms.map(vm => (
                    <div key={vm.id} className="resource-row">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>{vm.name}</p>
                          <span className={statusClass(vm.status)}>{vm.status}</span>
                        </div>
                        <span className="text-[10px]" style={{ color: "#4a5568" }}>{vm.cpu_cores} cores</span>
                      </div>
                      <p className="text-[10px] mb-2 font-mono" style={{ color: "#2a2f45" }}>{vm.id} · {vm.container_ids.length} containers</p>
                      <CpuBarRow label="" value={vm.cpu_usage} extra={`${formatBytes(vm.memory_used)} / ${formatBytes(vm.memory_total)}`} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ══════════ EVENTS TAB ══════════ */}
        {activeTab === "events" && (
          <div className="glass-card p-5 animate-slide-up">
            <div className="section-header">
              <Terminal className="h-4 w-4" style={{ color: "#06b6d4" }} /> Event Log
              <span className="info-badge ml-2" style={{ background: "rgba(6,182,212,0.08)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.15)" }}>{filteredEvents.length}</span>
              <div className="ml-auto flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3" style={{ color: "#4a5568" }} />
                  <input id="event-search" type="text" placeholder="Search…" value={eventSearch}
                    onChange={e => setEventSearch(e.target.value)} className="search-input pl-7 w-40" />
                </div>
              </div>
            </div>
            {/* Filter pills */}
            <div className="flex gap-2 mb-4 flex-wrap">
              {[
                { key: "all", label: "All" }, { key: "attack", label: "🔥 Attacks" },
                { key: "security", label: "🛡 Security" }, { key: "infra", label: "⚙️ Infra" },
              ].map(f => (
                <button key={f.key} onClick={() => setEventFilter(f.key)} id={`event-filter-${f.key}`}
                  className={`filter-pill ${eventFilter === f.key ? "filter-pill-active" : "filter-pill-inactive"}`}>
                  {f.label}
                </button>
              ))}
            </div>
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1a1f35" }}>
              <div className="grid grid-cols-12 gap-2 px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest"
                style={{ background: "#07091a", color: "#4a5568", borderBottom: "1px solid #1a1f35" }}>
                <div className="col-span-1">Tick</div>
                <div className="col-span-4">Event Type</div>
                <div className="col-span-2">Source</div>
                <div className="col-span-3">Target / Resource</div>
                <div className="col-span-1">Sev.</div>
                <div className="col-span-1">Pri.</div>
              </div>
              <div className="max-h-[520px] overflow-y-auto">
                {filteredEvents.length === 0 ? (
                  <div className="text-center py-12">
                    <Filter className="h-8 w-8 mx-auto mb-3" style={{ color: "#2a2f45" }} />
                    <p className="text-sm" style={{ color: "#4a5568" }}>No events match the current filter</p>
                  </div>
                ) : (
                  [...filteredEvents].reverse().map((e, i) => (
                    <div key={e.id || i} className="log-row grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-1 font-mono text-[11px]" style={{ color: "#4a5568" }}>{e.tick}</div>
                      <div className="col-span-4 text-xs font-semibold flex items-center gap-1.5" style={{ color: eventColor(e.event_type) }}>
                        {e.event_type?.startsWith("attack.") && <Flame className="h-3 w-3 flex-shrink-0" />}
                        {e.event_type?.startsWith("security.") && <Shield className="h-3 w-3 flex-shrink-0" />}
                        {e.event_type?.startsWith("infra.") && <Server className="h-3 w-3 flex-shrink-0" />}
                        <span className="truncate">{e.event_type}</span>
                      </div>
                      <div className="col-span-2 text-xs truncate" style={{ color: "#4a5568" }}>{e.source}</div>
                      <div className="col-span-3 text-[11px] font-mono truncate" style={{ color: "#64748b" }}>{e.target_id || e.resource_id || "—"}</div>
                      <div className="col-span-1">
                        {e.severity && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{
                            background: `${severityColor(e.severity)}15`, color: severityColor(e.severity),
                            border: `1px solid ${severityColor(e.severity)}30`,
                          }}>{e.severity?.slice(0, 4).toUpperCase()}</span>
                        )}
                      </div>
                      <div className="col-span-1 text-xs font-mono" style={{ color: "#2a2f45" }}>{e.priority}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* ══════════ IDS TAB ══════════ */}
        {activeTab === "ids" && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "Events Analyzed", value: idsStats.events_analyzed.toLocaleString(), color: "#06b6d4", icon: Eye },
                { label: "Alerts Generated", value: idsStats.alerts_generated, color: idsStats.alerts_generated > 0 ? "#f97316" : "#22c55e", icon: AlertTriangle },
                { label: "Rules Matched", value: idsStats.rules_matched, color: "#8b5cf6", icon: Lock },
              ].map((s, i) => (
                <div key={i} className="metric-card animate-slide-up" style={{ animationDelay: `${i * 0.05}s` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <s.icon className="h-4 w-4" style={{ color: s.color }} />
                    <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#4a5568" }}>{s.label}</p>
                  </div>
                  <p className="text-3xl font-bold" style={{ color: s.color }}>{s.value}</p>
                </div>
              ))}
            </div>

            <div className="glass-card p-5 animate-slide-up" style={{ animationDelay: "0.15s" }}>
              <div className="section-header">
                <ShieldAlert className="h-4 w-4" style={{ color: "#f97316" }} /> IDS Alert History
                <span className="info-badge ml-2" style={{ background: "rgba(249,115,22,0.08)", color: "#f97316", border: "1px solid rgba(249,115,22,0.18)" }}>{filteredAlerts.length}</span>
                <div className="ml-auto flex gap-2">
                  {["all", "critical", "high", "medium", "low"].map(f => (
                    <button key={f} onClick={() => setIdsFilter(f)}
                      className={`filter-pill ${idsFilter === f ? "filter-pill-active" : "filter-pill-inactive"}`}>
                      {f === "all" ? "All" : severityIcon(f) + " " + f}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {filteredAlerts.length === 0 ? (
                  <div className="text-center py-12">
                    <Shield className="h-12 w-12 mx-auto mb-3" style={{ color: "#22c55e" }} />
                    <p className="text-sm font-semibold" style={{ color: "#22c55e" }}>All Clear</p>
                    <p className="text-xs mt-1" style={{ color: "#4a5568" }}>No intrusion attempts detected</p>
                  </div>
                ) : (
                  [...filteredAlerts].reverse().map((alert, i) => {
                    const level = alert.threat_level || "info"
                    return (
                      <div key={alert.id || i} className={`p-4 rounded-xl severity-${level} animate-slide-up`}
                        style={{ background: "rgba(11,14,28,0.7)", border: "1px solid #1a1f35", animationDelay: `${i * 0.03}s` }}>
                        <div className="flex items-start gap-3">
                          <span className="text-lg">{severityIcon(level)}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-bold" style={{ color: severityColor(level) }}>[{level.toUpperCase()}]</span>
                              {alert.rule_id && (
                                <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{ background: "#07091a", color: "#4a5568" }}>
                                  Rule: {alert.rule_id}
                                </span>
                              )}
                              {alert.attack_type && (
                                <span className="text-[10px] px-2 py-0.5 rounded font-mono" style={{ background: "rgba(239,68,68,0.08)", color: "#f87171" }}>
                                  {alert.attack_type}
                                </span>
                              )}
                              <span className="text-[10px] font-mono ml-auto" style={{ color: "#2a2f45" }}>Tick {alert.tick}</span>
                            </div>
                            <p className="text-sm mt-1.5" style={{ color: "#cbd5e1" }}>{alert.description || "Security anomaly detected"}</p>
                            {alert.target_id && (
                              <p className="text-[10px] mt-1 font-mono" style={{ color: "#4a5568" }}>Target: {alert.target_id}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </div>
        )}

        {/* ══════════ AUDIT TAB ══════════ */}
        {activeTab === "audit" && (
          <div className="glass-card p-5 animate-slide-up">
            <div className="section-header">
              <FileWarning className="h-4 w-4" style={{ color: "#eab308" }} /> Security Audit Trail
              <span className="info-badge ml-2" style={{ background: "rgba(234,179,8,0.08)", color: "#eab308", border: "1px solid rgba(234,179,8,0.18)" }}>{auditTrail.length} entries</span>
            </div>
            <div className="rounded-xl overflow-hidden" style={{ border: "1px solid #1a1f35" }}>
              <div className="grid grid-cols-12 gap-2 px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest"
                style={{ background: "#07091a", color: "#4a5568", borderBottom: "1px solid #1a1f35" }}>
                <div className="col-span-1">Tick</div>
                <div className="col-span-4">Event</div>
                <div className="col-span-2">Severity</div>
                <div className="col-span-3">Description</div>
                <div className="col-span-2">Time</div>
              </div>
              <div className="max-h-[520px] overflow-y-auto">
                {auditTrail.length === 0 ? (
                  <div className="text-center py-12">
                    <Lock className="h-10 w-10 mx-auto mb-3" style={{ color: "#22c55e" }} />
                    <p className="text-sm" style={{ color: "#22c55e" }}>No security events recorded</p>
                  </div>
                ) : (
                  [...auditTrail].reverse().map((entry, i) => (
                    <div key={entry.id || i} className="log-row grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-1 font-mono text-[11px]" style={{ color: "#4a5568" }}>{entry.tick}</div>
                      <div className="col-span-4 text-xs font-semibold truncate" style={{ color: entry.event_type?.includes("attack") ? "#f87171" : "#fbbf24" }}>
                        {entry.event_type}
                      </div>
                      <div className="col-span-2">
                        {entry.threat_level && (
                          <span className="text-[9px] px-2 py-0.5 rounded-full font-bold" style={{
                            background: `${severityColor(entry.threat_level)}15`,
                            color: severityColor(entry.threat_level),
                            border: `1px solid ${severityColor(entry.threat_level)}30`,
                          }}>{entry.threat_level?.toUpperCase()}</span>
                        )}
                      </div>
                      <div className="col-span-3 text-[11px] truncate" style={{ color: "#94a3b8" }}>{entry.description || "—"}</div>
                      <div className="col-span-2 text-[10px] font-mono" style={{ color: "#2a2f45" }}>
                        {entry.timestamp ? timeAgo(entry.timestamp) : `T${entry.tick}`}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* ══════════ NETWORK TAB ══════════ */}
        {activeTab === "network" && (
          <div className="space-y-4">
            <div className="glass-card p-5 animate-slide-up">
              <div className="section-header">
                <Network className="h-4 w-4" style={{ color: "#06b6d4" }} /> Network Topology
                <span className="info-badge ml-2" style={{ background: "rgba(6,182,212,0.08)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.15)" }}>
                  {topology.nodes.length} nodes · {topology.edges.length} links
                </span>
              </div>
              <TopologyView topology={topology} />
            </div>

            {/* Subnet details */}
            <div className="grid gap-4 lg:grid-cols-2">
              {Object.values(state.networks).map(net => (
                <div key={net.id} className="glass-card p-5 animate-slide-up">
                  <div className="section-header">
                    <Network className="h-4 w-4" style={{ color: "#8b5cf6" }} /> {net.name}
                    <span className="info-badge ml-2" style={{ background: "rgba(139,92,246,0.08)", color: "#8b5cf6", border: "1px solid rgba(139,92,246,0.18)" }}>
                      {Object.keys(net.subnets).length} subnets
                    </span>
                  </div>
                  <div className="space-y-2">
                    {Object.values(net.subnets).map(subnet => (
                      <div key={subnet.id} className="resource-row">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="ring-indicator" style={{ background: subnet.is_healthy ? "#22c55e" : "#ef4444", color: subnet.is_healthy ? "#22c55e" : "#ef4444" }} />
                            <span className="text-sm font-semibold font-mono" style={{ color: "#e2e8f0" }}>{subnet.cidr}</span>
                          </div>
                          <span className={subnet.is_healthy ? "status-running" : "status-crashed"}>
                            {subnet.is_healthy ? "HEALTHY" : "DEGRADED"}
                          </span>
                        </div>
                        <p className="text-[10px] mt-1.5 font-mono" style={{ color: "#2a2f45" }}>
                          Gateway: {subnet.gateway} · ID: {subnet.id}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* VM ↔ subnet mapping */}
            <div className="glass-card p-5 animate-slide-up" style={{ animationDelay: "0.1s" }}>
              <div className="section-header">
                <Server className="h-4 w-4" style={{ color: "#3b82f6" }} /> VM — Subnet Mapping
              </div>
              <div className="space-y-2">
                {vms.map(vm => (
                  <div key={vm.id} className="resource-row flex items-center gap-4">
                    <Server className="h-4 w-4 flex-shrink-0" style={{ color: "#3b82f6" }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold" style={{ color: "#e2e8f0" }}>{vm.name}</p>
                      <p className="text-[10px] font-mono" style={{ color: "#2a2f45" }}>{vm.id}</p>
                    </div>
                    <ChevronRight className="h-4 w-4" style={{ color: "#2a2f45" }} />
                    <div className="text-right">
                      <p className="text-xs font-mono" style={{ color: "#8b5cf6" }}>{vm.subnet_id}</p>
                      <p className="text-[10px]" style={{ color: "#4a5568" }}>{vm.container_ids.length} containers</p>
                    </div>
                    <span className={statusClass(vm.status)}>{vm.status}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t px-6 py-3 flex items-center justify-between relative z-10"
        style={{ borderColor: "#1a1f35", background: "rgba(6,6,17,0.85)" }}>
        <p className="text-[10px] font-mono" style={{ color: "#2a2f45" }}>
          CyberSim v2.1 · Event-driven Cloud Security Simulator
        </p>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-[10px]" style={{ color: "#2a2f45" }}>
            <Wifi className="h-3 w-3" style={{ color: "#22c55e" }} /> Connected · 1.5s refresh
          </div>
          <span className="text-[10px] font-mono" style={{ color: "#2a2f45" }}>{new Date().toLocaleTimeString()}</span>
        </div>
      </footer>
    </div>
  )
}
