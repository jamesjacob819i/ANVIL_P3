import { useState, useEffect, useCallback } from 'react';
import { 
  ShieldAlert, Activity, AlertCircle, CheckCircle2, 
  Server, RefreshCw, Zap, Loader2, ShieldCheck, 
  CheckCircle, Clock, Box, Calendar, AlertTriangle, XCircle, Check
} from 'lucide-react';
import './index.css';

const API_URL = 'http://localhost:8001';

function App() {
  const [incidents, setIncidents] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [apiConnected, setApiConnected] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchIncidents = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const response = await fetch(`${API_URL}/api/incidents?limit=100`);
      if (!response.ok) throw new Error('Failed to fetch incidents');
      const data = await response.json();
      setIncidents(data);
      setApiConnected(true);
      setError(null);
    } catch (err) {
      console.error(err);
      setApiConnected(false);
      if (!error) {
        setError('Failed to connect to Dashboard API. Is it running?');
        setTimeout(() => setError(null), 5000);
      }
    } finally {
      setLoading(false);
      if (isRefresh) setTimeout(() => setRefreshing(false), 500);
    }
  }, [error]);

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(() => fetchIncidents(), 3000);
    return () => clearInterval(interval);
  }, [fetchIncidents]);

  const triggerTestIncident = async () => {
    try {
      const response = await fetch(`${API_URL}/api/incidents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service: 'target-app',
          message: 'High error rate detected on /checkout endpoint - Simulated Test',
          severity: 'high'
        })
      });
      if (!response.ok) {
        setError('Test incident API not available. Use: ./demo/seed_incident.sh');
        setTimeout(() => setError(null), 5000);
        return;
      }
      setTimeout(() => fetchIncidents(true), 1000);
    } catch (err) {
      setError('Could not trigger test incident. Try running: ./demo/seed_incident.sh manually.');
      setTimeout(() => setError(null), 5000);
    }
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  const filteredIncidents = filter === 'all' 
    ? incidents 
    : incidents.filter(i => {
        if (filter === 'in_progress') return i.status === 'in_progress' || i.status === 'open';
        return i.status === filter;
      });

  const activeCount = incidents.filter(i => i.status === 'in_progress' || i.status === 'open').length;
  const resolvedCount = incidents.filter(i => i.status === 'resolved').length;

  return (
    <>
      <nav className="navbar">
        <div className="logo">
          <ShieldAlert />
          Sentinel AI
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          {apiConnected ? <div className="pulse"></div> : <div style={{width: 8, height: 8, borderRadius: '50%', background: 'var(--status-new)'}}></div>}
          System {apiConnected ? 'Online' : 'Offline'}
        </div>
      </nav>

      <div className="container">
        <div className="stats-grid">
          <div className="glass stat-card">
            <div className="stat-title"><Activity size={16} /> Total Incidents</div>
            <div className="stat-value">{incidents.length}</div>
          </div>
          <div className="glass stat-card">
            <div className="stat-title"><AlertCircle size={16} /> Active</div>
            <div className="stat-value" style={{ color: 'var(--status-new)' }}>{activeCount}</div>
          </div>
          <div className="glass stat-card">
            <div className="stat-title"><CheckCircle2 size={16} /> Resolved</div>
            <div className="stat-value" style={{ color: 'var(--status-resolved)' }}>{resolvedCount}</div>
          </div>
          <div className="glass stat-card">
            <div className="stat-title"><Server size={16} /> API Status</div>
            <div className="stat-value" style={{ color: apiConnected ? 'var(--status-resolved)' : 'var(--status-new)', fontSize: '1.5rem', display: 'flex', alignItems: 'center', height: '100%', gap: '8px' }}>
              {apiConnected ? <><Check size={32} /> Connected</> : <><XCircle size={32} /> Disconnected</>}
            </div>
          </div>
        </div>

        <div className="controls glass" style={{ padding: '1rem' }}>
          <button className="btn btn-primary" onClick={() => fetchIncidents(true)}>
            <RefreshCw size={18} className={refreshing ? "spinner" : ""} /> Refresh Data
          </button>
          <div style={{ width: '1px', height: '24px', background: 'var(--border-color)', margin: '0 10px' }}></div>
          <button className={`btn ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>All</button>
          <button className={`btn ${filter === 'new' ? 'active' : ''}`} onClick={() => setFilter('new')}>New</button>
          <button className={`btn ${filter === 'in_progress' ? 'active' : ''}`} onClick={() => setFilter('in_progress')}>In Progress</button>
          <button className={`btn ${filter === 'resolved' ? 'active' : ''}`} onClick={() => setFilter('resolved')}>Resolved</button>
          
          <div style={{ flex: 1 }}></div>
          <button className="btn" onClick={triggerTestIncident} style={{ borderColor: 'rgba(244, 63, 94, 0.3)', color: '#f43f5e' }}>
            <Zap size={18} /> Trigger Test Incident
          </button>
        </div>

        {error && (
          <div className="error-toast">
            <AlertTriangle />
            {error}
          </div>
        )}

        <div className="incidents-grid">
          {loading ? (
            <div className="loading-state glass">
              <Loader2 size={48} className="spinner" />
              <p>Initializing Sentinel Pipeline...</p>
            </div>
          ) : filteredIncidents.length === 0 ? (
            <div className="loading-state glass">
              <ShieldCheck size={48} style={{ color: 'var(--status-resolved)', marginBottom: '1rem' }} />
              <p style={{ fontSize: '1.2rem', fontWeight: 500 }}>All Clear</p>
              <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>No incidents matching the current filter.</p>
            </div>
          ) : (
            filteredIncidents.map(incident => {
              const statusLabel = incident.status.replace('_', ' ').toUpperCase();
              const service = incident.alert_payload?.service || 'unknown-service';
              const message = incident.alert_payload?.message || 'No description provided';
              const createdTime = formatTimeAgo(incident.created_at);
              
              return (
                <div key={incident.id} className="glass incident-card">
                  <div className="incident-header">
                    <span className="incident-id">{incident.id.split('-')[0]}</span>
                    <span className={`badge status-${incident.status}`}>{statusLabel}</span>
                  </div>
                  <div className="incident-body">
                    <strong>Alert:</strong> {message}
                  </div>
                  <div className="service-tag">
                    <Box size={16} />
                    {service}
                  </div>
                  <div className="time-meta">
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Calendar size={14} /> {createdTime}
                    </span>
                    {incident.resolved_at ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle size={14} /> Resolved {formatTimeAgo(incident.resolved_at)}
                      </span>
                    ) : (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={14} /> Active
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}

export default App;
