BigQuery is the analytical data warehouse (`opptra-datawarehouse` or the project's dataset). Do not use BigQuery as a transactional row-locking store, and do not use Google Sheets as a substitute for a table.

Keep schema changes as checked-in SQL DDL files under `scripts/` or `bq-schema/`. Every load job or pipeline write must be idempotent for its date/window (or append-only with a deduplicating view/query over the newest run).

Never sum money metrics across currencies (such as AED, SAR, INR) without explicit currency conversion or per-currency grouping.

Keep `NULL` distinct from `0` when a source channel does not report a metric.
