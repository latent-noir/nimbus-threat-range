/**
 * API client for the Cloud Simulator backend.
 *
 * Types are aligned with the actual backend response from
 * SimulationEngine.get_state() in core/engine/engine.py
 */

const API_BASE = "http://localhost:8000/simulation";
const TIMEOUT_MS = 5000;

// ── Fetch Utility ────────────────────────────────────────────

async function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
        const res = await fetch(url, { ...options, signal: controller.signal, cache: "no-store" });
        return res;
    } finally {
        clearTimeout(id);
    }
}

// ── Domain Models ────────────────────────────────────────────

export interface Service {
    name: string;
    port: number;
    protocol: string;
    healthy: boolean;
}

export interface Container {
    id: string;
    name: string;
    cpu_usage: number;
    memory_usage: number;
    memory_limit: number;
    status: "RUNNING" | "STOPPED" | "CRASHED" | "CREATING";
    services: Service[];
    vm_id: string;
}

export interface VM {
    id: string;
    name: string;
    cpu_cores: number;
    cpu_usage: number;
    memory_total: number;
    memory_used: number;
    status: "RUNNING" | "STOPPED" | "COMPROMISED";
    subnet_id: string;
    container_ids: string[];
}

export interface Subnet {
    id: string;
    cidr: string;
    gateway: string;
    is_healthy: boolean;
}

export interface NetworkData {
    id: string;
    name: string;
    subnets: Record<string, Subnet>;
}

export interface SimulationEvent {
    id: string;
    timestamp: number;
    tick: number;
    source: string;
    event_type: string;
    priority: number;
    payload: Record<string, unknown>;
    resource_id?: string;
    severity?: string;
    target_id?: string;
    attack_type?: string;
    threat_level?: string;
    description?: string;
    rule_id?: string;
}

export interface SystemState {
    tick: number;
    timestamp: number;
    vms: VM[];
    containers: Container[];
    networks: Record<string, NetworkData>;
    metrics: {
        total_vms: number;
        total_containers: number;
        global_cpu_load: number;
    };
    recent_events: SimulationEvent[];
}

export interface IDSStats {
    events_analyzed: number;
    alerts_generated: number;
    rules_matched: number;
}

export interface NetworkTopology {
    nodes: Array<{
        id: string;
        label: string;
        type: "vm" | "container" | "subnet" | "gateway";
        status: string;
        x?: number;
        y?: number;
    }>;
    edges: Array<{
        from: string;
        to: string;
    }>;
}

// ── API Functions ────────────────────────────────────────────

export async function fetchSystemState(): Promise<SystemState> {
    const res = await fetchWithTimeout(`${API_BASE}/state`);
    if (!res.ok) {
        throw new Error(`Failed to fetch state: ${res.status}`);
    }
    return res.json();
}

export async function injectAttack(
    targetId: string,
    attackType: string = "ddos",
    severity: number = 80,
    durationMs: number = 5000
): Promise<{ status: string; target: string; type: string }> {
    const params = new URLSearchParams({
        target_id: targetId,
        attack_type: attackType,
        severity: severity.toString(),
        duration_ms: durationMs.toString(),
    });
    const res = await fetchWithTimeout(`${API_BASE}/inject?${params}`, {
        method: "POST",
    });
    if (!res.ok) {
        throw new Error(`Failed to inject attack: ${res.status}`);
    }
    return res.json();
}

export async function fetchEvents(count: number = 50): Promise<SimulationEvent[]> {
    try {
        const res = await fetchWithTimeout(`${API_BASE}/events?count=${count}`);
        if (!res.ok) return [];
        return res.json();
    } catch {
        return [];
    }
}

export async function fetchIDSAlerts(count: number = 50): Promise<SimulationEvent[]> {
    try {
        const res = await fetchWithTimeout(`${API_BASE}/ids/alerts?count=${count}`);
        if (!res.ok) return [];
        return res.json();
    } catch {
        return [];
    }
}

export async function fetchIDSStats(): Promise<IDSStats> {
    try {
        const res = await fetchWithTimeout(`${API_BASE}/ids/stats`);
        if (!res.ok) return { events_analyzed: 0, alerts_generated: 0, rules_matched: 0 };
        return res.json();
    } catch {
        return { events_analyzed: 0, alerts_generated: 0, rules_matched: 0 };
    }
}

export async function fetchAuditTrail(count: number = 100): Promise<SimulationEvent[]> {
    try {
        const res = await fetchWithTimeout(`${API_BASE}/audit?count=${count}`);
        if (!res.ok) return [];
        return res.json();
    } catch {
        return [];
    }
}

/**
 * Derive a NetworkTopology from the current SystemState by
 * synthesising subnet, VM, and container relationships.
 */
export function deriveNetworkTopology(state: SystemState): NetworkTopology {
    const nodes: NetworkTopology["nodes"] = [];
    const edges: NetworkTopology["edges"] = [];

    // Add subnets from all networks
    Object.values(state.networks).forEach((net) => {
        Object.values(net.subnets).forEach((subnet) => {
            nodes.push({
                id: subnet.id,
                label: subnet.cidr,
                type: "subnet",
                status: subnet.is_healthy ? "RUNNING" : "STOPPED",
            });
        });
    });

    // Add VMs and link to subnets
    state.vms.forEach((vm) => {
        nodes.push({
            id: vm.id,
            label: vm.name,
            type: "vm",
            status: vm.status,
        });
        // Link VM to its subnet
        if (vm.subnet_id) {
            edges.push({ from: vm.subnet_id, to: vm.id });
        }
        // Add containers and link to VM
        vm.container_ids.forEach((cid) => {
            const container = state.containers.find((c) => c.id === cid);
            if (container) {
                nodes.push({
                    id: container.id,
                    label: container.name,
                    type: "container",
                    status: container.status,
                });
                edges.push({ from: vm.id, to: container.id });
            }
        });
    });

    return { nodes, edges };
}
