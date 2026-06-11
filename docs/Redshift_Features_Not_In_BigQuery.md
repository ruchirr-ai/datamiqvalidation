# Redshift Capabilities Without a BigQuery Equivalent

---

## 1. Workload Management (WLM)

- Define multiple query queues with priority levels, memory allocation, and concurrency limits per queue
- Route users or query groups to specific queues — isolate ETL from dashboards on the same cluster
- Short Query Acceleration automatically fast-tracks queries predicted to finish quickly
- Query Monitoring Rules auto-terminate queries that exceed defined thresholds (time, CPU, rows scanned)
- BigQuery uses a single shared slot pool with dynamic concurrency — no user-configurable queues or priority routing

---

## 2. Data Sharing (Zero-Copy, Cross-Cluster)

- Share live tables and schemas between separate clusters, serverless workgroups, AWS accounts, and regions without copying data
- Each consumer gets its own isolated compute — no performance impact on the producer
- Supports multi-tenant architectures where tenants share data but have independent compute
- BigQuery shares data within the same infrastructure via authorized views and Analytics Hub — no concept of isolated consumer compute on shared data

---

## 3. Zero-ETL Integrations

- Aurora MySQL/PostgreSQL, RDS, and DynamoDB replicate into Redshift natively in near-real-time
- No pipelines, no Glue jobs, no orchestration — data appears in seconds after being written to the source
- Built into the platform with no additional service cost
- BigQuery requires Datastream (separate billable service) for CDC, with no native DynamoDB or Aurora integration

---

## 4. Integrated Data Lake Engine (RG Instances)

- Graviton-based RG instances include a built-in vectorized engine for querying Iceberg and Parquet on S3
- No per-TB Spectrum scanning charges — data lake queries are covered by the node cost
- Automatic statistics collection (JIT ANALYZE) for data lake tables without manual intervention
- BigQuery charges per-TB for bytes processed on all queries regardless of where data resides

---

## 5. Concurrency Scaling

- Automatically adds transient compute capacity during burst periods so queries never queue
- Scales back down when demand subsides — no manual intervention
- BigQuery queues queries when slot capacity is exhausted with no automatic burst mechanism
