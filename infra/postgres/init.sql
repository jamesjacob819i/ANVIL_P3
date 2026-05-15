CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(64) PRIMARY KEY,
    alert_payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(64) PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL REFERENCES incidents(id),
    parent_event_id VARCHAR(64),
    topic VARCHAR(64) NOT NULL,
    payload_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id VARCHAR(64) PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL REFERENCES incidents(id),
    agent_name VARCHAR(64) NOT NULL,
    input_json JSONB NOT NULL,
    output_json JSONB,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE INDEX idx_events_incident_id ON events(incident_id);
CREATE INDEX idx_events_topic ON events(topic);
CREATE INDEX idx_agent_runs_incident_id ON agent_runs(incident_id);
CREATE INDEX idx_incidents_status ON incidents(status);
