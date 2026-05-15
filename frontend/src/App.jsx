import { useState, useEffect } from "react";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from "recharts";
import axios from "axios";

const API = "https://passionate-nourishment-production-4a4b.up.railway.app/";

const SEVERITY_COLOR = {
  critical: "#E24B4A",
  high:     "#EF9F27",
  medium:   "#378ADD",
  low:      "#639922",
};

const STATUS_META = {
  pr_open:  { label: "PR Open",  bg: "#E6F1FB", color: "#185FA5" },
  pending:  { label: "Pending",  bg: "#FAEEDA", color: "#854F0B" },
  approved: { label: "Approved", bg: "#EAF3DE", color: "#3B6D11" },
  merged:   { label: "Merged",   bg: "#E1F5EE", color: "#0F6E56" },
};

const MONTHLY_TREND = [
  { month: "Oct", aws: 84200, azure: 31400, optimized: 84200 },
  { month: "Nov", aws: 91500, azure: 33800, optimized: 91500 },
  { month: "Dec", aws: 88300, azure: 35100, optimized: 88300 },
  { month: "Jan", aws: 95600, azure: 36700, optimized: 82100 },
  { month: "Feb", aws: 98200, azure: 37900, optimized: 71400 },
  { month: "Mar", aws: 102400, azure: 39200, optimized: 66100 },
];

const WASTE_BY_TYPE = [
  { type: "Idle EC2/VMs",        value: 41200 },
  { type: "Over-provisioned RDS", value: 28900 },
  { type: "Unused Elastic IPs",  value: 15600 },
  { type: "Orphaned Volumes",    value: 12300 },
  { type: "Idle Load Balancers", value: 10800 },
];

function fmt(n) {
  return n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n}`;
}

function MetricCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: "#1e1e2e",
      borderRadius: 10,
      padding: "14px 16px",
      borderLeft: `3px solid ${accent}`,
    }}>
      <p style={{ fontSize: 11, color: "#888", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </p>
      <p style={{ fontSize: 24, fontWeight: 500, margin: "0 0 4px", color: "#fff" }}>
        {value}
      </p>
      <p style={{ fontSize: 11, color: "#666", margin: 0 }}>{sub}</p>
    </div>
  );
}

function SeverityBadge({ level }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600,
      padding: "2px 7px", borderRadius: 4,
      background: SEVERITY_COLOR[level] + "22",
      color: SEVERITY_COLOR[level],
      textTransform: "uppercase",
    }}>{level}</span>
  );
}

function CloudBadge({ cloud }) {
  const isAws = cloud === "AWS";
  return (
    <span style={{
      fontSize: 10, fontWeight: 600,
      padding: "2px 7px", borderRadius: 4,
      background: isAws ? "#FF990022" : "#0089D622",
      color: isAws ? "#c47000" : "#005fa3",
    }}>{cloud}</span>
  );
}

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.pending;
  return (
    <span style={{
      fontSize: 10, fontWeight: 600,
      padding: "2px 7px", borderRadius: 4,
      background: m.bg, color: m.color,
    }}>{m.label}</span>
  );
}

const TABS = ["Overview", "Findings", "Pull Requests"];

export default function App() {
  const [tab, setTab]           = useState("Overview");
  const [findings, setFindings] = useState([]);
  const [summary, setSummary]   = useState(null);
  const [scanning, setScanning] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [filter, setFilter]     = useState("all");

  useEffect(() => {
    axios.get(`${API}/api/v1/scan/summary`)
      .then(r => setSummary(r.data))
      .catch(() => setSummary({
        total_monthly_spend_usd: 141600,
        total_monthly_waste_usd: 49560,
        waste_percentage: 35.0,
        resources_scanned: 847,
        open_prs: 3,
        last_scan: "2 minutes ago",
      }));
  }, []);

  const runScan = async () => {
    setScanning(true);
    try {
      const res = await axios.post(`${API}/api/v1/scan`);
      setFindings(res.data.findings || []);
      setSummary(prev => ({
        ...prev,
        total_monthly_waste_usd: res.data.total_monthly_waste_usd,
        waste_percentage: res.data.waste_percentage,
        last_scan: "just now",
      }));
      setTab("Findings");
    } catch (e) {
      alert("Scan failed — API chal rahi hai?");
    } finally {
      setScanning(false);
    }
  };

  const filteredFindings = filter === "all"
    ? findings
    : findings.filter(f => f.cloud === filter);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#13131f",
      color: "#fff",
      fontFamily: "Inter, system-ui, sans-serif",
      padding: "24px 20px",
    }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 600, margin: "0 0 4px" }}>
              FinOps Cloud Cost Optimizer
            </h1>
            <p style={{ fontSize: 13, color: "#888", margin: 0 }}>
              AWS + Azure · Waste detection · Terraform auto-fix
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 11, color: "#666" }}>
              Last scan: {summary?.last_scan || "..."}
            </span>
            <button
              onClick={runScan}
              disabled={scanning}
              style={{
                padding: "7px 16px", fontSize: 13,
                borderRadius: 8, border: "1px solid #333",
                background: scanning ? "#222" : "#1a1a2e",
                color: scanning ? "#666" : "#fff",
                cursor: scanning ? "not-allowed" : "pointer",
              }}
            >
              {scanning ? "⟳ Scanning..." : "⟳ Run Scan"}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, borderBottom: "1px solid #222", marginBottom: 24 }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: "8px 16px", fontSize: 13,
              background: "none", border: "none",
              cursor: "pointer",
              color: tab === t ? "#fff" : "#666",
              borderBottom: tab === t ? "2px solid #378ADD" : "2px solid transparent",
              marginBottom: -1,
            }}>{t}</button>
          ))}
        </div>

        {/* Overview Tab */}
        {tab === "Overview" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
              <MetricCard
                label="Monthly Spend"
                value={fmt(summary?.total_monthly_spend_usd || 141600)}
                sub="AWS + Azure combined"
                accent="#378ADD"
              />
              <MetricCard
                label="Detected Waste"
                value={fmt(summary?.total_monthly_waste_usd || 49560)}
                sub={`${summary?.waste_percentage || 35}% of total spend`}
                accent="#E24B4A"
              />
              <MetricCard
                label="Annual Waste"
                value={fmt((summary?.total_monthly_waste_usd || 49560) * 12)}
                sub="If nothing fixed"
                accent="#EF9F27"
              />
              <MetricCard
                label="Resources Scanned"
                value={summary?.resources_scanned || 847}
                sub="Across AWS + Azure"
                accent="#1D9E75"
              />
            </div>

            {/* Charts */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: "#1e1e2e", borderRadius: 10, padding: 16 }}>
                <p style={{ fontSize: 13, color: "#888", margin: "0 0 14px" }}>
                  Monthly cost vs optimized
                </p>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={MONTHLY_TREND}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                    <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#666" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "#666" }} tickFormatter={v => `$${v/1000}k`} axisLine={false} tickLine={false} width={42} />
                    <Tooltip formatter={v => [`$${(v/1000).toFixed(1)}k`]} contentStyle={{ background: "#1e1e2e", border: "1px solid #333" }} />
                    <Line type="monotone" dataKey="aws" stroke="#FF9900" strokeWidth={2} dot={false} name="AWS" />
                    <Line type="monotone" dataKey="azure" stroke="#0089D6" strokeWidth={2} dot={false} name="Azure" />
                    <Line type="monotone" dataKey="optimized" stroke="#1D9E75" strokeWidth={2} strokeDasharray="5 3" dot={false} name="Optimized" />
                  </LineChart>
                </ResponsiveContainer>
                <div style={{ display: "flex", gap: 14, marginTop: 8 }}>
                  {[["AWS","#FF9900"],["Azure","#0089D6"],["Optimized","#1D9E75"]].map(([n,c]) => (
                    <span key={n} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "#666" }}>
                      <span style={{ width: 10, height: 2, background: c, display: "inline-block" }} />{n}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ background: "#1e1e2e", borderRadius: 10, padding: 16 }}>
                <p style={{ fontSize: 13, color: "#888", margin: "0 0 14px" }}>
                  Waste by category
                </p>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={WASTE_BY_TYPE} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#222" />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#666" }} tickFormatter={v => `$${v/1000}k`} axisLine={false} tickLine={false} />
                    <YAxis dataKey="type" type="category" tick={{ fontSize: 10, fill: "#666" }} width={130} axisLine={false} tickLine={false} />
                    <Tooltip formatter={v => [`$${(v/1000).toFixed(1)}k`]} contentStyle={{ background: "#1e1e2e", border: "1px solid #333" }} />
                    <Bar dataKey="value" fill="#E24B4A" radius={[0,3,3,0]} name="Waste $" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div style={{ marginTop: 16, background: "#1e1e2e", borderRadius: 10, padding: 16, textAlign: "center" }}>
              <p style={{ color: "#666", fontSize: 13, margin: "0 0 12px" }}>
                Scan nahi chala abhi tak — findings dekhne ke liye scan run karo
              </p>
              <button onClick={runScan} disabled={scanning} style={{
                padding: "10px 24px", fontSize: 14, borderRadius: 8,
                border: "none", background: "#378ADD",
                color: "#fff", cursor: "pointer", fontWeight: 500,
              }}>
                {scanning ? "Scanning..." : "Run First Scan"}
              </button>
            </div>
          </div>
        )}

        {/* Findings Tab */}
        {tab === "Findings" && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 6 }}>
                {["all","AWS","Azure"].map(f => (
                  <button key={f} onClick={() => setFilter(f)} style={{
                    padding: "5px 12px", fontSize: 12,
                    borderRadius: 20, border: "1px solid #333",
                    background: filter === f ? "#378ADD22" : "none",
                    color: filter === f ? "#378ADD" : "#666",
                    cursor: "pointer",
                  }}>
                    {f === "all" ? "All clouds" : f}
                  </button>
                ))}
              </div>
              <span style={{ fontSize: 12, color: "#666" }}>
                {filteredFindings.length} findings
              </span>
            </div>

            {filteredFindings.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: "#666" }}>
                <p>Koi findings nahi — pehle scan run karo</p>
                <button onClick={runScan} style={{
                  padding: "8px 20px", fontSize: 13,
                  borderRadius: 8, border: "none",
                  background: "#378ADD", color: "#fff", cursor: "pointer",
                }}>Run Scan</button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {filteredFindings.map(f => (
                  <div key={f.id} style={{
                    background: "#1e1e2e", borderRadius: 8,
                    borderLeft: `3px solid ${SEVERITY_COLOR[f.severity]}`,
                    overflow: "hidden",
                  }}>
                    <div
                      onClick={() => setExpanded(expanded === f.id ? null : f.id)}
                      style={{ padding: "12px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 10 }}
                    >
                      <SeverityBadge level={f.severity} />
                      <CloudBadge cloud={f.cloud} />
                      <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>{f.resource_id}</span>
                      <span style={{ fontSize: 12, color: "#666" }}>{f.resource_type}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "#1D9E75" }}>
                        +{fmt(f.monthly_savings_usd)}/mo
                      </span>
                      <span style={{ color: "#666", fontSize: 12 }}>{expanded === f.id ? "▲" : "▼"}</span>
                    </div>

                    {expanded === f.id && (
                      <div style={{ padding: "0 16px 14px", borderTop: "1px solid #2a2a3e" }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, paddingTop: 12 }}>
                          <div>
                            <p style={{ fontSize: 11, color: "#666", margin: "0 0 3px" }}>REGION</p>
                            <p style={{ fontSize: 13, margin: 0 }}>{f.region}</p>
                          </div>
                          <div>
                            <p style={{ fontSize: 11, color: "#666", margin: "0 0 3px" }}>ANNUAL SAVINGS</p>
                            <p style={{ fontSize: 13, margin: 0, color: "#1D9E75" }}>{fmt(f.annual_savings_usd)}</p>
                          </div>
                          <div>
                            <p style={{ fontSize: 11, color: "#666", margin: "0 0 3px" }}>ISSUE</p>
                            <p style={{ fontSize: 13, margin: 0 }}>{f.issue}</p>
                          </div>
                        </div>
                        <div style={{ marginTop: 10 }}>
                          <p style={{ fontSize: 11, color: "#666", margin: "0 0 4px" }}>TERRAFORM FIX</p>
                          <pre style={{
                            background: "#0d0d1a", padding: "10px 12px",
                            borderRadius: 6, fontSize: 11, color: "#a0a0c0",
                            margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all",
                          }}>{f.terraform_fix}</pre>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Pull Requests Tab */}
        {tab === "Pull Requests" && (
          <div>
            <div style={{ background: "#1e1e2e", borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
              <p style={{ fontSize: 13, color: "#888", margin: 0 }}>
                Terraform PRs automatically GitHub pe raise honge. Human approve karega — ArgoCD apply karega.
              </p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { id: "#47", title: "Rightsize 3 idle EC2 instances", savings: 4200, status: "pr_open", age: "2h" },
                { id: "#44", title: "Delete orphaned Elastic IPs (4)", savings: 720, status: "merged", age: "1d" },
                { id: "#41", title: "Remove unused RDS replica", savings: 2800, status: "approved", age: "3d" },
                { id: "#38", title: "Downsize Azure VMs in staging", savings: 5400, status: "merged", age: "5d" },
              ].map(pr => (
                <div key={pr.id} style={{
                  background: "#1e1e2e", borderRadius: 8,
                  padding: "12px 16px", display: "flex",
                  alignItems: "center", gap: 12,
                }}>
                  <span style={{ fontFamily: "monospace", fontSize: 12, color: "#666", minWidth: 36 }}>{pr.id}</span>
                  <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>{pr.title}</span>
                  <span style={{ fontSize: 12, color: "#666" }}>{pr.age} ago</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#1D9E75" }}>+{fmt(pr.savings)}/mo</span>
                  <StatusBadge status={pr.status} />
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}