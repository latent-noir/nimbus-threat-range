"""
Cloud Simulator — Streamlit Dashboard

Live monitoring dashboard connected to the simulation engine API.
Auto-refreshes every 2 seconds to display real-time data.

Run:
    streamlit run dashboard/app.py

Requires the Core Engine to be running on http://localhost:8000.
"""

import time
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

API_BASE = "http://localhost:8000/simulation"
REFRESH_INTERVAL = 2  # seconds

st.set_page_config(
    page_title="Cloud Simulator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API Client
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def api_get(endpoint: str, params: dict = None):
    """Fetch data from the simulation API."""
    try:
        r = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_post(endpoint: str, params: dict = None):
    """POST to the simulation API."""
    try:
        r = requests.post(f"{API_BASE}{endpoint}", params=params, timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Custom CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("""
<style>
    /* Dark professional theme overrides */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .alert-critical { border-left: 4px solid #ef4444; padding-left: 12px; }
    .alert-high     { border-left: 4px solid #f97316; padding-left: 12px; }
    .alert-medium   { border-left: 4px solid #eab308; padding-left: 12px; }
    .alert-low      { border-left: 4px solid #22c55e; padding-left: 12px; }
    .status-running    { color: #22c55e; font-weight: 600; }
    .status-crashed    { color: #ef4444; font-weight: 600; }
    .status-stopped    { color: #94a3b8; font-weight: 600; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Sidebar
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with st.sidebar:
    st.markdown("## 🛡️ Cloud Simulator")
    st.markdown("---")

    # Connection status
    state = api_get("/state")
    if state:
        st.success("● Engine Connected")
        st.caption(f"Tick: **{state.get('tick', '—')}**")
    else:
        st.error("● Engine Offline")
        st.caption("Start the engine: `python core/main.py`")

    st.markdown("---")

    # Attack controls
    st.markdown("### ⚡ Attack Controls")
    if state and state.get("containers"):
        container_ids = [c["id"] for c in state["containers"]]
        target = st.selectbox("Target", container_ids, key="attack_target")
        attack_type = st.selectbox("Type", ["ddos", "brute_force", "ransomware", "sql_injection"], key="attack_type")
        severity = st.slider("Severity", 1, 100, 80, key="attack_severity")
        if st.button("🚀 Launch Attack", type="primary", use_container_width=True):
            result = api_post("/inject", params={
                "target_id": target,
                "attack_type": attack_type,
                "severity": severity,
                "duration_ms": 5000,
            })
            if result:
                st.toast(f"Attack injected on {target}!", icon="💥")
            else:
                st.error("Failed to inject attack")

    st.markdown("---")
    auto_refresh = st.toggle("Auto-refresh", value=True, key="auto_refresh")
    refresh_rate = st.slider("Refresh rate (s)", 1, 10, REFRESH_INTERVAL, key="refresh_rate")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Content
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if not state:
    st.warning("⚠️ Cannot connect to the simulation engine. Make sure it's running on `localhost:8000`.")
    st.stop()


# ── Header Metrics ────────────────────────────────────────────

st.markdown("# 🌐 Cloud Infrastructure Monitor")
st.markdown("---")

metrics = state.get("metrics", {})
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total VMs", metrics.get("total_vms", 0))
col2.metric("Total Containers", metrics.get("total_containers", 0))
col3.metric("Global CPU Load", f"{metrics.get('global_cpu_load', 0):.1f}%")
col4.metric("Simulation Tick", state.get("tick", 0))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Row 1: CPU Chart + Active Attacks
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

containers = state.get("containers", [])

chart_col, attacks_col = st.columns([3, 2])

# ── Live CPU Usage Graph ──────────────────────────────────────

with chart_col:
    st.markdown("### 📊 Live CPU Usage")
    if containers:
        fig = go.Figure()

        for c in containers:
            color = "#ef4444" if c["cpu_usage"] > 90 else (
                "#f97316" if c["cpu_usage"] > 70 else "#22c55e"
            )
            fig.add_trace(go.Bar(
                x=[c["name"]],
                y=[c["cpu_usage"]],
                name=c["name"],
                marker_color=color,
                text=f"{c['cpu_usage']:.1f}%",
                textposition="outside",
            ))

        fig.update_layout(
            yaxis_title="CPU (%)",
            yaxis_range=[0, 110],
            showlegend=False,
            height=350,
            margin=dict(t=10, b=40, l=50, r=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0",
            yaxis=dict(gridcolor="#334155"),
        )
        # Danger threshold line
        fig.add_hline(y=90, line_dash="dash", line_color="#ef4444",
                      annotation_text="Critical", annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No containers running.")

# ── Active Attacks Panel ──────────────────────────────────────

with attacks_col:
    st.markdown("### ⚔️ Active Attacks")

    events = api_get("/events", params={"count": 30}) or []
    attack_events = [e for e in events if str(e.get("event_type", "")).startswith("attack.")]

    if attack_events:
        for atk in attack_events[-8:]:  # show last 8
            severity = atk.get("severity", 50)
            icon = "🔴" if severity >= 80 else ("🟠" if severity >= 50 else "🟡")
            target = atk.get("target_id", "unknown")
            atype = atk.get("attack_type", atk.get("event_type", "unknown"))
            st.markdown(
                f"{icon} **{atype}** → `{target}` "
                f"<small>(sev: {severity}, tick: {atk.get('tick', '?')})</small>",
                unsafe_allow_html=True,
            )
    else:
        st.success("No active attacks detected.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Row 2: IDS Alerts + Network Topology
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ids_col, net_col = st.columns([3, 2])

# ── IDS Alerts Panel ──────────────────────────────────────────

with ids_col:
    st.markdown("### 🚨 IDS Alerts")

    alerts = api_get("/ids/alerts", params={"count": 20}) or []
    ids_stats = api_get("/ids/stats") or {}

    # Stats bar
    s1, s2, s3 = st.columns(3)
    s1.metric("Events Analyzed", ids_stats.get("events_analyzed", 0))
    s2.metric("Alerts Generated", ids_stats.get("alerts_generated", 0))
    s3.metric("Rules Matched", ids_stats.get("rules_matched", 0))

    if alerts:
        for alert in reversed(alerts[-10:]):  # newest first
            level = alert.get("threat_level", "info")
            icon_map = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}
            icon = icon_map.get(level, "⚪")
            css_class = f"alert-{level}"

            st.markdown(
                f'<div class="{css_class}">'
                f'{icon} <strong>[{level.upper()}]</strong> '
                f'{alert.get("description", "No description")} '
                f'<br><small>Rule: {alert.get("rule_id", "—")} '
                f'| Tick: {alert.get("tick", "—")}</small></div><br>',
                unsafe_allow_html=True,
            )
    else:
        st.success("No IDS alerts — system is clean.")

# ── Network Topology ──────────────────────────────────────────

with net_col:
    st.markdown("### 🌐 Network Topology")

    networks = state.get("networks", {})
    vms = state.get("vms", [])

    G = nx.Graph()

    # Add nodes
    for net_id, net_data in networks.items():
        G.add_node(net_data.get("name", net_id), type="network", color="#3b82f6", size=30)
        for sub_id, sub_data in net_data.get("subnets", {}).items():
            subnet_label = sub_data.get("cidr", sub_id)
            G.add_node(subnet_label, type="subnet", color="#8b5cf6", size=20)
            G.add_edge(net_data.get("name", net_id), subnet_label)

    for vm in vms:
        vm_label = vm.get("name", vm["id"])
        vm_status = vm.get("status", "RUNNING")
        color = "#22c55e" if vm_status == "RUNNING" else (
            "#ef4444" if vm_status == "COMPROMISED" else "#94a3b8"
        )
        G.add_node(vm_label, type="vm", color=color, size=15)
        # Connect VM to its subnet
        vm_subnet_id = vm.get("subnet_id", "")
        for net_data in networks.values():
            sub_data = net_data.get("subnets", {}).get(vm_subnet_id)
            if sub_data:
                subnet_cidr = sub_data.get("cidr")
                if subnet_cidr and subnet_cidr in G:
                    G.add_edge(subnet_cidr, vm_label)
                break

    for c in containers:
        c_label = c.get("name", c["id"])
        c_status = c.get("status", "RUNNING")
        color = "#22c55e" if c_status == "RUNNING" else "#ef4444"
        G.add_node(c_label, type="container", color=color, size=8)
        # Connect to parent VM
        vm_id = c.get("vm_id", "")
        vm_match = next((v.get("name", v["id"]) for v in vms if v["id"] == vm_id), None)
        if vm_match and vm_match in G:
            G.add_edge(vm_match, c_label)

    if G.number_of_nodes() > 0:
        pos = nx.spring_layout(G, seed=42, k=2)

        edge_x, edge_y = [], []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        node_x = [pos[n][0] for n in G.nodes()]
        node_y = [pos[n][1] for n in G.nodes()]
        node_colors = [G.nodes[n].get("color", "#64748b") for n in G.nodes()]
        node_sizes = [G.nodes[n].get("size", 10) for n in G.nodes()]
        node_labels = list(G.nodes())
        node_types = [G.nodes[n].get("type", "unknown") for n in G.nodes()]
        hover_text = [f"{label}\nType: {ntype}" for label, ntype in zip(node_labels, node_types)]

        fig_net = go.Figure()

        fig_net.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            mode="lines",
            line=dict(width=1, color="#475569"),
            hoverinfo="none",
        ))

        fig_net.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            marker=dict(size=node_sizes, color=node_colors, line=dict(width=1, color="#1e293b")),
            text=node_labels,
            textposition="top center",
            textfont=dict(size=9, color="#cbd5e1"),
            hovertext=hover_text,
            hoverinfo="text",
        ))

        fig_net.update_layout(
            showlegend=False,
            height=400,
            margin=dict(t=10, b=10, l=10, r=10),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        st.plotly_chart(fig_net, use_container_width=True)

        # Legend
        st.caption("🔵 Network  🟣 Subnet  🟢 VM/Container (healthy)  🔴 Crashed/Compromised")
    else:
        st.info("No network data available.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Row 3: Log Viewer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("---")
st.markdown("### 📜 Event Log Viewer")

log_filter = st.selectbox(
    "Filter by domain",
    ["All Events", "Infrastructure (infra.*)", "Attacks (attack.*)", "Security (security.*)"],
    key="log_filter",
)

all_events = api_get("/events", params={"count": 100}) or []

# Apply filter
filter_map = {
    "Infrastructure (infra.*)": "infra.",
    "Attacks (attack.*)": "attack.",
    "Security (security.*)": "security.",
}
prefix = filter_map.get(log_filter, "")
if prefix:
    all_events = [e for e in all_events if str(e.get("event_type", "")).startswith(prefix)]

if all_events:
    log_df = pd.DataFrame([
        {
            "Tick": e.get("tick", "—"),
            "Event Type": e.get("event_type", "unknown"),
            "Source": e.get("source", "—"),
            "Resource": e.get("resource_id") or e.get("target_id") or e.get("container_id") or "—",
            "Severity": e.get("severity", e.get("priority", "—")),
            "Timestamp": e.get("timestamp", "—"),
        }
        for e in reversed(all_events)  # newest first
    ])

    st.dataframe(
        log_df,
        use_container_width=True,
        height=300,
        column_config={
            "Tick": st.column_config.NumberColumn("Tick", width="small"),
            "Event Type": st.column_config.TextColumn("Event Type", width="medium"),
            "Severity": st.column_config.TextColumn("Severity", width="small"),
        },
    )
else:
    st.info("No events to display.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Container Detail Table
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("---")
st.markdown("### 📦 Container Status")

if containers:
    container_df = pd.DataFrame([
        {
            "ID": c["id"],
            "Name": c["name"],
            "CPU (%)": round(c["cpu_usage"], 1),
            "Memory (MB)": round(c["memory_usage"] / (1024 * 1024), 1),
            "Mem Limit (MB)": round(c["memory_limit"] / (1024 * 1024), 0),
            "Status": c["status"],
            "VM": c.get("vm_id", "—"),
        }
        for c in containers
    ])

    st.dataframe(
        container_df,
        use_container_width=True,
        column_config={
            "CPU (%)": st.column_config.ProgressColumn(
                "CPU (%)", min_value=0, max_value=100, format="%.1f%%",
            ),
            "Status": st.column_config.TextColumn("Status"),
        },
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Auto-Refresh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
