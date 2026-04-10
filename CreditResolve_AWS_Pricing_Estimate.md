# Credit Resolve — AWS Redshift Pricing Estimate

## Current GCP Spend (from billing data)

| Service | Monthly Cost (₹) | Monthly Cost ($) |
|---------|------------------|------------------|
| BigQuery | ₹80,05,172 | ~$95,300 |
| Compute Engine | ₹26,62,843 | ~$31,700 |
| Datastream | ₹7,66,544 | ~$9,125 |
| Networking | ₹2,39,951 | ~$2,857 |
| Cloud Monitoring | ₹2,37,247 | ~$2,825 |
| Others | ₹2,71,042 | ~$3,226 |
| **TOTAL** | **₹1,20,82,799** | **~$143,843** |

*Exchange rate: ₹84 = $1*

---

## Current BigQuery Workload Profile

| Metric | Value |
|--------|-------|
| Total data size | 1.85 TB (customer says 3-4 TB) |
| Data scanned/day | 142.07 TB |
| Avg slot utilization | 134.5 slots |
| Peak concurrent queries | 232 |
| Queries/day | ~20,000 (max) |
| Query mix | 98.35% ad-hoc, 1.65% scheduled |
| Daily incremental data | ~10 GB |
| Streaming refresh | 15-minute intervals from PostgreSQL |

---

## Recommended AWS Architecture

**PostgreSQL (EC2) → DMS/Zero-ETL → Redshift** (eliminates BigQuery + Datastream)

Since the single source is self-hosted PostgreSQL on EC2 (already on AWS), we can use AWS DMS or Redshift Zero-ETL for near-real-time replication — no need for a separate streaming service like Datastream.

---

## Option 1: Redshift Serverless (Mumbai, ap-south-1)

Best for: Ad-hoc heavy workloads (98% ad-hoc queries)

BQ slot mapping: 1 BQ slot ≈ 2 GB RAM. 1 Redshift RPU = 16 GB RAM.
134.5 BQ slots ≈ 269 GB → ceil(269 / 16) = ~17 RPU

| Component | Calculation | Monthly Cost |
|-----------|-------------|-------------|
| Base RPU | 134.5 BQ slots × 2 GB ÷ 16 GB/RPU ≈ 16 RPU (nearest multiple of 8) | — |
| Active hours/day | With 20K queries/day, ~16 active hours estimated | — |
| RPU-hours/month | 16 RPU × 16 hrs × 30 days = 7,680 RPU-hrs | — |
| On-demand cost | 7,680 × $0.4275/RPU-hr | **$3,283/mo** |
| 1-yr reservation (20% off) | 7,680 × $0.342 | **$2,627/mo** |
| Managed storage (4 TB) | 4,000 GB × $0.024/GB | **$96/mo** |
| **Total (on-demand)** | | **~$3,379/mo** |
| **Total (1-yr reserved)** | | **~$2,723/mo** |

Note: Peak concurrent queries = 232. Serverless auto-scales RPU up during bursts — you only pay for actual RPU-hours consumed.

---

## Option 2: Redshift Provisioned ra3.4xlarge (Mumbai)

Best for: Predictable workloads, cost optimization with RI

Each ra3.4xlarge = 12 vCPUs, 96 GB RAM
134.5 BQ slots × 2 GB = 269 GB RAM → ceil(269 / 96) = 3 nodes

| Component | Calculation | Monthly Cost |
|-----------|-------------|-------------|
| Nodes needed | ceil(269 GB / 96 GB per node) = 3 nodes | — |
| On-demand | 3 × $3.706/hr × 730 hrs | **$8,116/mo** |
| 1-yr RI | 3 × $2.5942/hr × 730 hrs | **$5,681/mo** |
| 3-yr RI | 3 × $1.6121/hr × 730 hrs | **$3,530/mo** |
| Managed storage (4 TB) | 4,000 GB × $0.024/GB | **$96/mo** |
| **Total (on-demand)** | | **~$8,212/mo** |
| **Total (1-yr RI)** | | **~$5,777/mo** |
| **Total (3-yr RI)** | | **~$3,626/mo** |

---

## Option 3: Redshift Provisioned ra3.xlplus (Mumbai)

Smaller nodes, more granular scaling

Each ra3.xlplus = 4 vCPUs, 32 GB RAM
134.5 BQ slots × 2 GB = 269 GB RAM → ceil(269 / 32) = 9 nodes

| Component | Calculation | Monthly Cost |
|-----------|-------------|-------------|
| Nodes needed | ceil(269 GB / 32 GB per node) = 9 nodes | — |
| On-demand | 9 × $1.235/hr × 730 hrs | **$8,114/mo** |
| 1-yr RI | 9 × $0.8645/hr × 730 hrs | **$5,680/mo** |
| 3-yr RI | 9 × $0.5373/hr × 730 hrs | **$3,530/mo** |
| Managed storage (4 TB) | 4,000 GB × $0.024/GB | **$96/mo** |
| **Total (on-demand)** | | **~$8,210/mo** |
| **Total (1-yr RI)** | | **~$5,776/mo** |
| **Total (3-yr RI)** | | **~$3,626/mo** |

---

## Data Streaming: DMS vs Zero-ETL

Replacing Datastream (₹7.66L/mo = ~$9,125/mo) for PostgreSQL → Redshift streaming:

| Option | Monthly Cost | Notes |
|--------|-------------|-------|
| AWS DMS (CDC) | ~$200–400/mo | t3.medium replication instance, 10 GB/day incremental |
| Redshift Zero-ETL | Included in Redshift cost | Native integration, near-real-time, no extra infra |

**Savings on streaming alone: ~$8,700–9,000/mo**

---

## CloudWatch Monitoring

Replacing Cloud Monitoring (₹2.37L/mo = ~$2,825/mo):

| Component | Detail | Monthly Cost |
|-----------|--------|-------------|
| CloudWatch Metrics | Redshift publishes 15+ metrics free. Custom metrics: $0.30/metric/mo | ~$10 |
| CloudWatch Dashboards | First 3 free, $3/dashboard/mo after | ~$10 |
| CloudWatch Alarms | $0.10/alarm/mo (standard), ~20 alarms | ~$2 |
| CloudWatch Logs | Redshift audit logs, ~10 GB/mo × $0.50/GB ingestion | ~$5 |
| **Total CloudWatch** | | **~$27/mo** |

CloudWatch basic monitoring for Redshift is included at no extra cost. The ₹2.37L they spend on GCP Cloud Monitoring drops to under $30/mo on AWS.

---

## Cost Comparison Summary

| Scenario | Monthly Cost ($) | Monthly Cost (₹) | vs Current GCP |
|----------|-----------------|-------------------|----------------|
| **Current GCP (BQ + Datastream)** | ~$104,425 | ~₹87.7L | baseline |
| Redshift Serverless (on-demand) | ~$3,379 | ~₹2.8L | **97% savings** |
| Redshift Serverless (1-yr reserved) | ~$2,723 | ~₹2.3L | **97% savings** |
| Redshift Provisioned ra3.4xl (on-demand) | ~$8,212 | ~₹6.9L | **92% savings** |
| **Redshift Provisioned ra3.4xl (1-yr RI)** | **~$5,777** | **~₹4.9L** | **94% savings** |
| Redshift Provisioned ra3.4xl (3-yr RI) | ~$3,626 | ~₹3.0L | **97% savings** |
| Redshift Provisioned ra3.xlplus (1-yr RI) | ~$5,776 | ~₹4.9L | **94% savings** |

*Current GCP comparison = BigQuery (₹80L) + Datastream (₹7.66L) = ₹87.7L (~$104K)*
*Compute Engine costs remain similar on AWS (EC2 for PostgreSQL already on AWS)*

---

## Recommendation

**Redshift Provisioned ra3.4xlarge × 3 nodes with 1-yr RI** at ~₹4.9L/month

- Best balance of cost and commitment flexibility
- 3 nodes with 288 GB total RAM handles 269 GB (134.5 BQ slots × 2 GB) with headroom
- Concurrency scaling handles burst to 232 concurrent queries
- 1-yr RI gives 94% savings vs current BQ spend without 3-year lock-in
- DMS or Zero-ETL replaces Datastream at near-zero additional cost
- Already on AWS (50K credits + existing EC2 PostgreSQL) — no egress costs

---

## Additional Savings

- **$50K AWS credits** cover ~8 months of Redshift provisioned (1-yr RI at ~$5.8K/mo)
- **Eliminate Datastream** ($9K/mo) — DMS or Zero-ETL is near-free
- **Eliminate BigQuery on-demand** ($95K/mo) — replaced by Redshift
- **No GCP egress** — data stays within AWS

*Sources: AWS Redshift Pricing (ap-south-1), GCP billing data provided by Credit Resolve*
