import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ShieldAlert, Activity, AlertCircle, CheckCircle2,
  Server, RefreshCw, Zap, Loader2, ChevronDown, ChevronUp,
  Box, Clock, Calendar, AlertTriangle, Check, XCircle,
  GitBranch, Brain, Wrench, Rocket, FileText, Bell,
  Radio
} from 'lucide-react';
import './index.css';

const API_URL = 'http://localhost:8001';
const WS_URL = 'ws://localhost:8001/ws';

// Pipeline steps configuration
const PIPELINE_STEPS = [
  { key: 'webhook_ingress',    label: 'Webhook Ingress',    icon: Radio,    topic: 'incidents.new'    },
  { key: 'triage_worker',      label: 'Triage',             icon: AlertCircle, topic: 'triage.done'   },
  { key: 'diagnostics_worker', label: 'Diagnostics',        icon: Activity, topic: 'diagnostics.done' },
  { key: 'rca_worker',         label: 'Root Cause Analysis',icon: Brain,    topic: 'rca.done'         },
  { key: 'remediation_worker', label: 'Remediation',        icon: Wrench,   topic: 'fix.done'         },
  { key: 'deployment_worker',  label: 'Deployment',         icon: Rocket,   topic: 'deployment.done'  },
  { key: 'postmortem_worker',  label: 'Postmortem',         icon: FileText, topic: 'postmortem.done'  },
];

const TOPIC_ORDER = PIPELINE_STEPS.map(s => s.topic);

function getStepStatus(agentRuns, topic, incidentStatus) {
  if (topic === 'incidents.new') {
    return agentRuns.length > 0 || incidentStatus ? 'done' : 'pending';
  }
  // find the agent run matching this stage's output topic
  const stepConfig = PIPELINE_STEPS.find(s => s.topic === topic);
  if (!stepConfig) return 'pending';

  const run = agentRuns.find(r => r.agent_name === stepConfig.key);
  if (!run) {
    // Check if any later step has started (means this one is done)
    const topicIdx = TOPIC_ORDER.indexOf(topic);
    const laterTopics = TOPIC_ORDER.slice(topicIdx + 1);
    const hasLaterRun = agentRuns.some(r => {
      const laterStep = PIPELINE_STEPS.find(s => s.topic === r.topic || s.key === r.agent_name);
      return laterStep && laterTopics.includes(laterStep.topic);
    });
    if (hasLaterRun) return 'done';
    // Check if previous step is done
    const prevTopicIdx = topicIdx - 1;
    if (prevTopicIdx >= 0) {
      const prevTopic = TOPIC_ORDER[prevTopicIdx];
      const prevStatus = getStepStatus(agentRuns, prevTopic, incidentStatus);
      if (prevStatus === 'done') return 'running';
    }
    return 'pending';
  }
  if (run.status === 'completed') return 'done';
  if (run.status === 'failed') return 'failed';
  if (run.status === 'running') return 'running';
  return 'pending';
}

function getStepDetail(agentRuns, stepKey) {
  const run = agentRuns.find(r => r.agent_name === stepKey);
  if (!run) return '';
  if (run.status === 'failed') return run.output?.error || 'Failed';
  if (run.status === 'completed') {
    if (stepKey === 'triage_worker') return `Severity: ${run.output?.severity || '?'}`;
    if (stepKey === 'diagnostics_worker') return `Error rate: ${run.output?.metrics?.error_rate ?? '?'}`;
    if (stepKey === 'rca_worker') return run.output?.root_cause?.slice(0, 60) + (run.output?.root_cause?.length > 60 ? '…' : '') || '';
    if (stepKey === 'remediation_worker') return run.output?.branch ? `Branch: ${run.output.branch}` : '';
    if (stepKey === 'deployment_worker') return run.output?.success ? 'Deployed & stable' : 'Deployment attempted';
    if (stepKey === 'postmortem_worker') return run.output?.commit?.url ? 'Report committed to GitHub' : 'Report generated';
  }
  return run.status;
}

function getDuration(run) {
  if (!run?.started_at) return '';
  const start = new Date(run.started_at);
  const end = run.ended_at ? new Date(run.ended_at) : new Date();
  const secs = Math.round((end - start) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function formatAgo(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function StepIcon({ status, IconComponent }) {
  if (status === 'done') return (
    <div className="step-icon done"><Check size={12} /></div>
  );
  if (status === 'running') return (
    <div className="step-icon running"><Loader2 size={11} className="spin" /></div>
  );
  if (status === 'failed') return (
    <div className="step-icon failed"><XCircle size={12} /></div>
  );
  return <div className="step-icon pending"><IconComponent size={10} /></div>;
}

function PipelineVisualizer({ agentRuns, incidentStatus }) {
  return (
    <div className="pipeline-section">
      <div className="pipeline-title">Pipeline Execution</div>
      <div className="pipeline-steps">
        {PIPELINE_STEPS.map((step, i) => {
          const status = getStepStatus(agentRuns, step.topic, incidentStatus);
          const detail = getStepDetail(agentRuns, step.key);
          const run = agentRuns.find(r => r.agent_name === step.key);
          const duration = run ? getDuration(run) : '';
          return (
            <div key={step.key} className={`pipeline-step step-${status}`}>
              <StepIcon status={status} IconComponent={step.icon} />
              <div className="step-info">
                <div className="step-name">{step.label}</div>
                {detail && <div className="step-detail">{detail}</div>}
              </div>
              {duration && <div className="step-time">{duration}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IncidentCard({ incident, detail, onExpand, expanded }) {
  const status = incident.status;
  const service = incident.alert_payload?.service || incident.alert_payload?.raw_payload?.service || 'unknown';
  const message = incident.alert_payload?.message || 'No description';
  const agentRuns = detail?.agent_runs || [];

  return (
    <div className={`incident-card ${expanded ? 'expanded' : ''}`} onClick={onExpand}>
      <div className="card-header">
        <span className="card-id">{incident.id.split('-')[0]}</span>
        <StatusBadge status={status} />
      </div>
      <div className="card-body">
        <div className="card-message">{message}</div>
        <div className="card-service"><Box size={13} /> {service}</div>
      </div>

      {expanded && (
        <PipelineVisualizer agentRuns={agentRuns} incidentStatus={status} />
      )}

      <div className="card-footer">
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Calendar size={12} /> {formatAgo(incident.created_at)}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {status === 'resolved'
            ? <><Check size={12} style={{ color: 'var(--success)' }} /> Resolved {formatAgo(incident.resolved_at)}</>
            : <><div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--warning)', animation: 'pulse-dot 1.5s infinite', flexShrink: 0 }} /> Active</>
          }
          <span style={{ marginLeft: 8, color: 'var(--accent)', display: 'flex', alignItems: 'center' }}>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </span>
        </span>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  if (status === 'resolved') return <span className="badge badge-resolved"><Check size={10} /> Resolved</span>;
  if (status === 'open' || status === 'new') return <span className="badge badge-open"><AlertCircle size={10} /> Open</span>;
  return <span className="badge badge-running"><div className="pulse-dot" /> {status}</span>;
}

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [details, setDetails] = useState({});
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const wsRef = useRef(null);

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchIncidents = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const res = await fetch(`${API_URL}/api/incidents?limit=50`);
      if (!res.ok) throw new Error();
      setIncidents(await res.json());
      setError(null);
    } catch {
      setError('Cannot reach Dashboard API (localhost:8001). Is Docker running?');
    } finally {
      setLoading(false);
      if (isRefresh) setTimeout(() => setRefreshing(false), 600);
    }
  }, []);

  const fetchDetail = useCallback(async (id) => {
    try {
      const res = await fetch(`${API_URL}/api/incidents/${id}`);
      if (!res.ok) return;
      const data = await res.json();
      setDetails(prev => ({ ...prev, [id]: data }));
    } catch {}
  }, []);

  // Poll all open incidents every 4 seconds for their pipeline details
  useEffect(() => {
    const openIds = incidents.filter(i => i.status !== 'resolved').map(i => i.id);
    if (expandedId) openIds.push(expandedId);
    const unique = [...new Set(openIds)];
    unique.forEach(id => fetchDetail(id));
  }, [incidents, expandedId, fetchDetail]);

  // Initial load + polling
  useEffect(() => {
    fetchIncidents();
    const iv = setInterval(() => fetchIncidents(), 4000);
    return () => clearInterval(iv);
  }, [fetchIncidents]);

  // WebSocket for real-time events
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connect, 3000);
      };
      ws.onmessage = () => {
        // Refresh data on any pipeline event
        fetchIncidents();
        if (expandedId) fetchDetail(expandedId);
      };
    }
    connect();
    return () => wsRef.current?.close();
  }, [fetchIncidents, fetchDetail, expandedId]);

  const triggerIncident = async () => {
    try {
      const res = await fetch(`${API_URL}/api/incidents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'sentinel-ui',
          message: 'High error rate detected on /checkout endpoint — 25% error rate in last 5 minutes',
          severity: 'P1',
          service: 'target-app',
          environment: 'production',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast('✅ Incident triggered — pipeline starting!', 'success');
      setTimeout(() => fetchIncidents(true), 800);
    } catch (e) {
      showToast(`Failed to trigger incident: ${e.message}`);
    }
  };

  const handleExpand = (id) => {
    const next = expandedId === id ? null : id;
    setExpandedId(next);
    if (next) fetchDetail(next);
  };

  const filtered = filter === 'all' ? incidents
    : filter === 'open' ? incidents.filter(i => i.status !== 'resolved')
    : incidents.filter(i => i.status === filter);

  const openCount = incidents.filter(i => i.status !== 'resolved').length;
  const resolvedCount = incidents.filter(i => i.status === 'resolved').length;

  return (
    <>
      <nav className="navbar">
        <div className="logo"><ShieldAlert size={22} /> Sentinel AI</div>
        <div className="nav-status">
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: wsConnected ? 'var(--success)' : 'var(--danger)', boxShadow: wsConnected ? '0 0 6px var(--success)' : 'none' }} />
          {wsConnected ? 'Live' : 'Reconnecting…'}
        </div>
      </nav>

      <div className="page">
        {/* Stats */}
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-label"><Activity size={13} /> Total Incidents</div>
            <div className="stat-value">{incidents.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label"><AlertCircle size={13} /> Open</div>
            <div className="stat-value" style={{ color: openCount > 0 ? 'var(--danger)' : 'var(--text)' }}>{openCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label"><CheckCircle2 size={13} /> Resolved</div>
            <div className="stat-value" style={{ color: 'var(--success)' }}>{resolvedCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">
              <span style={{ 
                background: 'linear-gradient(135deg, #8b5cf6, #38bdf8)', 
                WebkitBackgroundClip: 'text', 
                WebkitTextFillColor: 'transparent', 
                fontWeight: 'bold',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                <Brain size={13} color="#8b5cf6" /> Omium AI Score
              </span>
            </div>
            <div className="stat-value" style={{ color: 'var(--accent)' }}>
              {incidents.length > 0 ? Math.round((resolvedCount / incidents.length) * 100) : 100}%
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label"><Server size={13} /> API</div>
            <div className="stat-value" style={{ fontSize: '1rem', paddingTop: '0.5rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              {error
                ? <><XCircle size={20} style={{ color: 'var(--danger)' }} /><span style={{ color: 'var(--danger)' }}>Offline</span></>
                : <><Check size={20} style={{ color: 'var(--success)' }} /><span style={{ color: 'var(--success)' }}>Online</span></>}
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="controls">
          <button className="btn btn-primary" onClick={() => fetchIncidents(true)}>
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} /> Refresh
          </button>
          <div className="controls-sep" />
          {['all', 'open', 'resolved'].map(f => (
            <button key={f} className={`btn ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
          <div className="spacer" />
          <button className="btn btn-danger" onClick={triggerIncident}>
            <Zap size={14} /> Trigger Incident
          </button>
        </div>

        {/* Toasts */}
        {toast && (
          <div className={`toast toast-${toast.type}`}>
            {toast.type === 'error' ? <AlertTriangle size={16} /> : <Check size={16} />}
            {toast.msg}
          </div>
        )}
        {error && (
          <div className="toast toast-error">
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* Incidents Grid */}
        <div className="incidents-grid">
          {loading ? (
            <div className="empty-state">
              <Loader2 size={48} className="spin empty-state-icon" />
              <h3>Connecting to Sentinel…</h3>
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <CheckCircle2 size={56} className="empty-state-icon" style={{ color: 'var(--success)' }} />
              <h3>All Clear</h3>
              <p>{filter === 'all' ? 'No incidents yet. Trigger one to see the pipeline in action.' : `No ${filter} incidents.`}</p>
            </div>
          ) : filtered.map(inc => (
            <IncidentCard
              key={inc.id}
              incident={inc}
              detail={details[inc.id]}
              expanded={expandedId === inc.id}
              onExpand={() => handleExpand(inc.id)}
            />
          ))}
        </div>
      </div>
    </>
  );
}
