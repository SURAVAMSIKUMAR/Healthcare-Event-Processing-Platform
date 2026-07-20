# Performance Test Report

## Scope
Test suite: k6 mixed workload for:
- high-rate ingestion
- duplicate ingestion
- invalid payload ingestion
- same-patient concurrency ingestion
- reporting traffic

Script: perf/k6/ingestion_and_reporting.js

## Environment
- Date:
- API version/commit:
- Host machine:
- CPU/RAM:
- Database topology:
- Broker topology:
- Test duration:

## Run Command
```bash
k6 run perf/k6/ingestion_and_reporting.js \
  -e BASE_URL=http://127.0.0.1:8000 \
  -e JWT_TOKEN=<valid_jwt>
```

## Results
- Throughput (req/s):
- p95 response time (ms):
- Error rate (%):

## Scenario Breakdown
| Scenario | Req Count | Throughput (req/s) | p95 (ms) | Error Rate (%) |
|---|---:|---:|---:|---:|
| high_rate_ingestion |  |  |  |  |
| duplicate_retries |  |  |  |  |
| invalid_payloads |  |  |  |  |
| same_patient_concurrency |  |  |  |  |
| reporting_traffic |  |  |  |  |

## Bottlenecks Observed
1. 
2. 
3. 

## Optimization Recommendations
1. 
2. 
3. 
