Updating the job image does not start a run and does not start a backfill. Do not add a workflow step that executes the job on merge.

Schedules, timeouts, memory, and `enabled` flags live in `service.yaml` and `config/jobs.yaml`. Changing a cron or enabling a job is a pull request, not a console edit. A job with `enabled: false` or an empty schedule list gets no Cloud Scheduler entry and must exit 0 immediately without calling external APIs.

A failed external fetch (such as HTTP 429 or 5xx after retries, or a truncated export file) must exit non-zero so Cloud Run alerts fire. Never swallow an upstream outage and exit 0 as if the inbox were empty.
