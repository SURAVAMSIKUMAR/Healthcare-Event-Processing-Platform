import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const ingestLatency = new Trend("ingest_latency_ms");
const reportLatency = new Trend("report_latency_ms");
const errorRate = new Rate("scenario_error_rate");

const baseUrl = __ENV.BASE_URL || "http://127.0.0.1:8000";
const token = __ENV.JWT_TOKEN || "";

export const options = {
  scenarios: {
    high_rate_ingestion: {
      executor: "constant-arrival-rate",
      rate: 120,
      timeUnit: "1s",
      duration: "2m",
      preAllocatedVUs: 20,
      maxVUs: 100,
      exec: "highRateIngestion",
    },
    duplicate_retries: {
      executor: "constant-vus",
      vus: 10,
      duration: "2m",
      exec: "duplicateIngestion",
    },
    invalid_payloads: {
      executor: "constant-vus",
      vus: 8,
      duration: "2m",
      exec: "invalidPayloadIngestion",
    },
    same_patient_concurrency: {
      executor: "constant-arrival-rate",
      rate: 60,
      timeUnit: "1s",
      duration: "2m",
      preAllocatedVUs: 12,
      exec: "samePatientConcurrentIngestion",
    },
    reporting_traffic: {
      executor: "constant-vus",
      vus: 15,
      duration: "2m",
      exec: "reportingTraffic",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<750"],
    scenario_error_rate: ["rate<0.05"],
  },
};

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function vitalsPayload(eventId, patientId) {
  return JSON.stringify({
    event_id: eventId,
    event_type: "VITALS",
    occurred_at: new Date().toISOString(),
    patient_id: patientId,
    payload: {
      heart_rate: 80 + Math.floor(Math.random() * 40),
      systolic_bp: 100 + Math.floor(Math.random() * 30),
      diastolic_bp: 65 + Math.floor(Math.random() * 20),
      temperature_c: 36 + Math.random() * 3,
      respiratory_rate: 12 + Math.floor(Math.random() * 8),
      oxygen_saturation: 88 + Math.floor(Math.random() * 12),
    },
  });
}

export function highRateIngestion() {
  const eventId = `evt-hi-${__VU}-${__ITER}-${Date.now()}`;
  const patientId = `pat-${__VU}`;
  const res = http.post(`${baseUrl}/api/v1/events`, vitalsPayload(eventId, patientId), {
    headers: authHeaders(),
  });

  ingestLatency.add(res.timings.duration);
  const ok = check(res, {
    "high_rate_ingestion accepted": (r) => r.status === 202,
  });
  errorRate.add(!ok);
}

export function duplicateIngestion() {
  const eventId = `evt-dup-${__VU}-${Math.floor(__ITER / 2)}`;
  const patientId = `dup-pat-${__VU}`;
  const res = http.post(`${baseUrl}/api/v1/events`, vitalsPayload(eventId, patientId), {
    headers: authHeaders(),
  });

  ingestLatency.add(res.timings.duration);
  const ok = check(res, {
    "duplicate endpoint reachable": (r) => r.status === 202,
  });
  errorRate.add(!ok);
}

export function invalidPayloadIngestion() {
  const badPayload = JSON.stringify({
    event_id: `evt-bad-${__VU}-${__ITER}`,
    event_type: "VITALS",
    occurred_at: new Date().toISOString(),
    patient_id: `bad-pat-${__VU}`,
    payload: {
      heart_rate: 9999,
      systolic_bp: 120,
      diastolic_bp: 80,
      temperature_c: 36.5,
      respiratory_rate: 16,
      oxygen_saturation: 99,
    },
  });

  const res = http.post(`${baseUrl}/api/v1/events`, badPayload, {
    headers: authHeaders(),
  });

  ingestLatency.add(res.timings.duration);
  const ok = check(res, {
    "invalid payload rejected": (r) => r.status === 422,
  });
  errorRate.add(!ok);
}

export function samePatientConcurrentIngestion() {
  const eventId = `evt-con-${__VU}-${__ITER}-${Date.now()}`;
  const patientId = "same-patient-1";
  const res = http.post(`${baseUrl}/api/v1/events`, vitalsPayload(eventId, patientId), {
    headers: authHeaders(),
  });

  ingestLatency.add(res.timings.duration);
  const ok = check(res, {
    "same patient ingestion accepted": (r) => r.status === 202,
  });
  errorRate.add(!ok);
}

export function reportingTraffic() {
  const headers = authHeaders();
  const summaryRes = http.get(`${baseUrl}/api/v1/reports/hospital-summary`, { headers });
  const alertsRes = http.get(`${baseUrl}/api/v1/alerts?page=1&page_size=20`, { headers });

  reportLatency.add(summaryRes.timings.duration);
  reportLatency.add(alertsRes.timings.duration);

  const ok = check(summaryRes, {
    "summary responds": (r) => r.status === 200,
  }) && check(alertsRes, {
    "alerts responds": (r) => r.status === 200,
  });

  errorRate.add(!ok);
  sleep(0.25);
}
