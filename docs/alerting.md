---
title: Alerts
parent: Platform
nav_order: 3
---

# Alerts

v1 does not create the alert policies. Apply this page after a Cloud Run service is deployed. Use one Slack notification channel per GCP project. Staging alerts go to the staging project's channel. Production alerts go to that app's production project channel.

Create three policies for each service.

## 1. Server errors

Metric `run.googleapis.com/request_count`, filtered to the service and to `response_code_class = 5xx`.

Alert when, for five minutes, the 5xx count is at least 1 and 5xx responses are more than 1% of all requests. A single failed probe should not page.

## 2. No ready revision

Alert when the service has no revision whose ready condition is true. This is the "the deploy left it down" signal.

## 3. Unhandled application errors

Log-based alert. The template logger writes JSON with a `severity` field. Match:

```
resource.type="cloud_run_revision"
resource.labels.service_name="<service name from service.yaml>"
severity>=ERROR
```

Alert when this appears at least once in five minutes. Tighten it after the first week if the channel is noisy.

## What is not in this set

Uptime checks from outside GCP, latency objectives, and product analytics. Add an uptime check on `/api/health` when the service is `public` or `app-login`. An `iap` service needs an authenticated probe, which v1 does not include.
