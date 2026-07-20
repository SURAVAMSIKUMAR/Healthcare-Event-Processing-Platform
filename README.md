# Health Events Backend

FastAPI + PostgreSQL backend to ingest typed healthcare events with idempotency and asynchronous processing.

## Delivery checklist
- Complete typed Python source code with modular project structure.
- Dockerfile and Docker Compose for API, worker, PostgreSQL, and Redis broker.
- Alembic migrations, seed data utility, .env.example, API documentation endpoint, and setup instructions.
- Automated tests + k6 load-test script + architecture diagram.
- Design notes for idempotency, transactions, retries, concurrency, security, scaling, and limitations.

## Project structure
```text
app/
   api/v1/              # FastAPI routes
   core/                # config, middleware, metrics
   db/                  # SQLAlchemy engine/session
   models/              # ORM entities
   schemas/             # Pydantic request/response schemas
   services/            # business logic (ingestion, processing, auth, audit)
   workers/             # Celery app and tasks
   utils/               # utility scripts (seed data)
alembic/               # migration environment and revisions
tests/                 # unit/api/integration-marked tests
perf/k6/               # load-test scenario scripts
docs/architecture.md   # concise system architecture diagram
```

## API documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Task 1 coverage
- `POST /api/v1/events` supports event types:
  - `VITALS`
  - `LAB_RESULT`
  - `MEDICATION_ORDER`
  - `PATIENT_ADMISSION`
  - `PATIENT_DISCHARGE`
- Strong typed validation with per-event payload schemas.
- Idempotent event ingestion using unique `event_id` constraint.
- Raw event persistence for audit.
- Asynchronous queueing using Celery + Redis.

## Quick start
1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:
   - `pip install -e .[dev]`
3. Copy env file:
   - `copy .env.example .env`
4. Start infra with Docker:
   - `docker compose up -d`
5. Run migrations:
   - `alembic upgrade head`
6. Run API:
   - `uvicorn app.main:app --reload`
7. Run worker (separate terminal):
   - `celery -A app.workers.celery_app.celery_app worker --loglevel=info`

## API example
```bash
curl -X POST http://127.0.0.1:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt-001",
    "event_type": "VITALS",
    "occurred_at": "2026-07-17T10:00:00Z",
    "patient_id": "pat-123",
    "payload": {
      "heart_rate": 82,
      "systolic_bp": 120,
      "diastolic_bp": 78,
      "temperature_c": 36.8,
      "respiratory_rate": 16,
      "oxygen_saturation": 98
    }
  }'
```

## Notes
- Duplicate `event_id` requests are accepted but not re-queued.
- Raw event JSON is stored in `raw_events` for audit and traceability.

## Task 2 coverage
- Worker processing normalizes event data and stores canonical records in `processed_events`.
- Transient failures retry with exponential backoff (`2^n` seconds) via Celery retry policy.
- Permanent failures and exhausted retries are moved to `failed_events` (dead-letter store).
- Configurable rule engine is stored in DB table `alert_rules`.
- Supported operators: `LT`, `LTE`, `GT`, `GTE`, `EQ`, `BETWEEN`, `OUTSIDE_RANGE`.
- Default alert rules include:
   - Low SpO2
   - High heart rate
   - Low systolic BP
   - High temperature
   - Abnormal lab values
   - Event received after discharge
- A single event can trigger multiple `alerts` records with severity, status, trigger timestamp, and acknowledgement metadata.

## Task 3 coverage
- Patient state is maintained in `patient_states` with:
   - hospital
   - department
   - admission status
   - latest event timestamp
   - latest clinical values
   - active critical-alert count
- Older events do not overwrite newer patient state; stale events are processed for audit/alerts but ignored for state overwrite.
- Concurrency safety is implemented with transactional processing and row-level locking (`SELECT ... FOR UPDATE`) during patient state updates.

## Task 4 coverage
- PostgreSQL schema is migration-driven using Alembic with initial migration at `alembic/versions/20260717_0001_initial_schema.py`.
- Tables modeled:
   - `raw_events`
   - `processed_events`
   - `patients`
   - `admissions`
   - `observations`
   - `lab_results`
   - `medication_orders`
   - `alert_rules`
   - `alerts`
   - `failed_events`
   - `processing_history`
   - `patient_states`
   - `hospital_summary_daily`
- Keys, constraints, and indexes are included for idempotency, filtering, timeline queries, and reporting.
- APIs implemented:
   - `GET /api/v1/patients/{patient_id}/timeline`
      - pagination
      - date range filters
      - event-type filter
      - sort order
   - `GET /api/v1/alerts`
      - hospital filter
      - department filter
      - patient filter
      - severity/status filters
      - date range filters
   - `PATCH /api/v1/alerts/{alert_id}/acknowledge`
      - captures user, timestamp, comments
      - blocks repeated acknowledgement with HTTP 409
   - `GET /api/v1/reports/hospital-summary`
      - returns event/failure counts, active patients, critical alerts, and average processing time
      - reads from pre-aggregated `hospital_summary_daily` to avoid full-table scans on each request

## Task 5 coverage
- Authentication and authorization:
   - JWT-based auth with roles: `ADMIN`, `HOSPITAL_USER`, `CLINICIAN`, `AUDITOR`
   - `POST /api/v1/auth/login` for token issuance
   - `GET /api/v1/auth/me` for caller identity
   - `POST /api/v1/admin/users` for admin-managed user creation
- Hospital-level data isolation:
   - Non-admin users are scoped to their hospital context on timeline, alerts, and report APIs
   - Alert acknowledgement enforces hospital scope ownership for non-admin users
- Audit logging with correlation ID and source IP:
   - Login attempts
   - Patient data access (timeline/alerts/reports)
   - Alert acknowledgements
   - Rule changes (`PATCH /api/v1/rules/{rule_code}`)
   - Administrative actions (user creation)
- Structured logging and error handling:
   - Request middleware emits JSON structured logs and injects `x-correlation-id`
   - Consistent API error envelope for validation, HTTP, and unhandled errors
- Observability endpoints:
   - `GET /health`
   - `GET /health/ready` with database and broker checks
   - `GET /metrics` exposing Prometheus-compatible metrics

## Task 6 coverage
- Test suite includes:
   - Unit tests for schema validation, rule operators, normalization, stale-state ordering, ingestion duplicate handling, and worker retry/dead-letter behavior.
   - API tests for authorization, duplicate response behavior, consistent validation errors, alert acknowledgement repeat-protection, and hospital-isolation behavior.
   - Integration-marked test entrypoint (`@pytest.mark.integration`) gated by environment for external infra runs.
- Coverage target:
   - `pytest` is configured with coverage and threshold `--cov-fail-under=80` for core logic.
- Performance load test:
   - k6 script at `perf/k6/ingestion_and_reporting.js`
   - Covers high-rate ingestion, duplicates, invalid payloads, same-patient concurrency, and reporting traffic.
   - Report template at `perf/PERFORMANCE_REPORT.md` to document throughput, p95 latency, error rate, and bottlenecks.

### Run tests
```bash
pytest
```

### Run only integration tests (with infra)
```bash
pytest -m integration
```

### Run performance test (k6)
```bash
k6 run perf/k6/ingestion_and_reporting.js \
   -e BASE_URL=http://127.0.0.1:8000 \
   -e JWT_TOKEN=<valid_jwt>
```

## Dockerized run
1. Create env file:
   - `copy .env.example .env`
2. Start complete stack:
   - `docker compose up --build`
3. Services:
   - API: `http://localhost:8000`
   - PostgreSQL: `localhost:5432`
   - Redis: `localhost:6379`

## Seed data
- Utility: `python -m app.utils.seed_data`
- Seeds:
  - default rules
  - bootstrap admin user
  - demo `HOSPITAL_USER`, `CLINICIAN`, `AUDITOR`

## Architecture diagram
- See [docs/architecture.md](docs/architecture.md).

## Idempotency strategy
- Unique constraint on `raw_events.event_id` prevents duplicate processing.
- Duplicate requests return accepted response with duplicate flag but do not re-queue.

## Transaction boundaries
- Ingestion transaction: raw event insert + enqueue status update.
- Worker processing transaction: normalization, domain writes, alerts, patient state update, summary update, and processing-history write.
- Dead-letter transaction: failed-event write + raw-event failed status + summary/history update.

## Retry strategy
- Celery task retries transient failures with exponential backoff: $2^n$ seconds.
- Permanent failures or exhausted retries are moved to `failed_events`.

## Concurrency handling
- Row-level lock (`SELECT ... FOR UPDATE`) on `patient_states` for safe concurrent updates.
- Out-of-order protection by timestamp guard: older events do not overwrite newer patient state.

## Security decisions
- JWT bearer auth with role-based authorization.
- Roles: `ADMIN`, `HOSPITAL_USER`, `CLINICIAN`, `AUDITOR`.
- Hospital-level data isolation enforced for non-admin users.
- Audit logs capture correlation ID and source IP for critical actions.

## Scaling approach
- Stateless API and worker services allow horizontal scaling.
- Broker-backed async processing smooths spikes in ingestion traffic.
- Reporting endpoint reads pre-aggregated summary table to avoid full-table scans.

## Known limitations
- Current integration tests are environment-gated and require running infra.
- Reporting aggregates are daily and eventually consistent with worker completion.
- Rule-management API currently supports updates but not full CRUD lifecycle.

## Constraint compliance
- No secrets or real credentials are committed in source control.
   - `.env.example` uses placeholders only.
   - Bootstrap and demo user passwords are environment-driven and optional.
- Ingestion is asynchronous by design.
   - `POST /api/v1/events` stores and enqueues work only.
   - Processing, rule evaluation, and alert generation run in Celery workers.
- Persistent infrastructure is used.
   - PostgreSQL is the primary datastore.
   - Redis is the broker/result backend.
   - The solution is a full multi-module backend, not a single script/notebook.
- AI-assisted development note.
   - The implementation is structured with explicit service boundaries, type hints, and design rationale so every major decision can be explained during review.
