# SENTINEL — Autonomous Production Incident Commander

An open-source, event-driven, multi-agent pipeline that autonomously detects, diagnoses, fixes, deploys, and documents production incidents end-to-end.

## Architecture

```
Alert/GitHub Webhook → Webhook Ingress → Redis Streams → Triage Agent → Diagnostics Agent → RCA Agent → Remediation Agent → Deployment Agent → Postmortem Agent → Notifier
                                                                                                                              ↕
                                                                                                                     Dashboard API + WebSocket
                                                                                                                              ↕
                                                                                                                     Next.js Frontend
```

Each agent is an independent worker subscribing to Redis Streams topics. Workers communicate ONLY via events — no direct calls between agents.

## Quickstart

### Prerequisites

- Docker & Docker Compose
- API keys (see .env.example):
  - `GROQ_API_KEY` or `GEMINI_API_KEY` (LLM)
  - `GITHUB_TOKEN` (PRs, code reading)
  - `TAVILY_API_KEY` (web search for RCA, optional)
  - `SLACK_WEBHOOK_URL` (notifications, optional)
  - `LINEAR_API_KEY` (post-mortem tickets, optional)

### Run

```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up -d --build
```

This starts: Postgres, Redis, Webhook Ingress (port 8000), Dashboard API (port 8001), Target Demo App (port 5000), and all worker agents.

### Trigger a Demo Incident

```bash
chmod +x demo/seed_incident.sh
./demo/seed_incident.sh
```

### View the Dashboard

To view the frontend dashboard, you can start the React app locally:

```bash
cd dashboard-ui
npm install
npm run dev
```

The UI will typically be available at **http://localhost:5173**. 
Alternatively, open **http://localhost:8001** for the API directly, or check each service's logs:

```bash
docker compose logs -f triage_worker
docker compose logs -f diagnostics_worker
docker compose logs -f rca_worker
docker compose logs -f remediation_worker
```

## Services

| Service | Topic Subscribed | Topic Published | Description |
|---------|-----------------|-----------------|-------------|
| webhook_ingress | — | incidents.new, github.pr_merged | Receives alerts and GitHub webhooks |
| triage_worker | incidents.new | triage.done | Classifies severity, checks duplicates |
| diagnostics_worker | triage.done | diagnostics.done | Parallel log/metric/commit analysis |
| rca_worker | diagnostics.done | rca.done | Root cause analysis with web search |
| remediation_worker | rca.done | fix.done | Generates patch, creates PR |
| deployment_worker | fix.done, github.pr_merged | deployment.done | Deploys and monitors metrics |
| postmortem_worker | deployment.done | postmortem.done | Generates postmortem document |
| notifier_worker | ALL topics | — | Slack notifications |
| dashboard_api | ALL topics | — | WebSocket + REST API |

## Event Topics

- `incidents.new` — New incident alert
- `triage.done` — Triage classification result
- `diagnostics.done` — Diagnostics evidence package
- `rca.done` — Root cause analysis result
- `fix.done` — Remediation PR created
- `github.pr_merged` — GitHub PR merged webhook
- `deployment.done` — Deployment result with metrics
- `postmortem.done` — Postmortem document generated

## Database Schema

- `incidents` — Incident records with status tracking
- `events` — Event log with causal parent_event_id chain
- `agent_runs` — Agent execution history with inputs/outputs

## Project Structure

```
sentinel/
├── docker-compose.yml
├── .env.example
├── shared/           # Shared library (events, bus, db, llm, tracing)
├── services/         # Each worker is a Docker service
│   ├── webhook_ingress/
│   ├── triage_worker/
│   ├── diagnostics_worker/
│   ├── rca_worker/
│   ├── remediation_worker/
│   ├── deployment_worker/
│   ├── postmortem_worker/
│   ├── notifier_worker/
│   └── dashboard_api/
├── infra/            # Postgres init, Redis config
└── demo/             # Target app + seed scripts
```

## Demo App

The demo `target_app` is an intentionally fragile Flask app at `http://localhost:5000`:
- `POST /checkout` — Shopping cart checkout (has buggy coupon code handling)
- `GET /metrics` — Returns error_rate, latency_p99, request_count
- `GET /health` — Health check

## License

MIT
