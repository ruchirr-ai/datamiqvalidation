# Migration Cost Estimate — BigQuery to Redshift (1 TB)

**Data:** 1 TB total — 70% deep layer (long-term), 30% top layer (active)

---

## 1. BQ → GCS Export

- Batch export (`bq extract`) is **free** — no compute charge, no per-byte charge
- Long-term storage data exports at the same speed, no extra cost
- Same-region BQ → GCS transfer: **$0**

---

## 2. GCP Data Out (GCS → AWS)

GCP has two network tiers with different egress pricing:

| Tier | 0–200 GB | 200 GB–1 TB | 1–10 TB | 1 TB Total |
|------|----------|-------------|---------|------------|
| Premium (default) | $0.12/GB | $0.12/GB | $0.11/GB | **~$113** |
| Standard | FREE | $0.085/GB | $0.085/GB | **~$70** |

*Standard Tier recommended for one-time migration (no need for Google's premium backbone).*
*Source: [GCP Network Tiers Pricing](https://cloud.google.com/network-tiers/pricing)*

- GCS temp storage (~1 week): **~$6**
- AWS data transfer in: **$0** (always free)

**Total data-out cost: ~$76** (Standard Tier) or **~$119** (Premium Tier)

---

## 3. Airbyte (Firebase → Redshift ongoing pipeline)

### Option A: Airbyte Cloud

- Base plan: **$10/month** (includes 4 credits)
- Additional credits: **$2.50 each**
- Firebase is an API source: **$15 per million rows** (6 credits)
- Databases/files: **$10 per GB** (4 credits)

| Volume | Est. Monthly Cost |
|--------|------------------|
| 1M rows/day | ~$450/month |
| 5M rows/day | ~$2,250/month |
| 20M rows/day | ~$9,000/month |

*Source: [Airbyte Pricing](https://airbyte.com/pricing), [Credit Docs](https://docs.airbyte.com/platform/cloud/managing-airbyte-cloud/manage-credits)*

### Option B: Airbyte Self-Hosted (Open Source)

Software is free (MIT license). Infrastructure cost breakdown:

| Component | Spec | Est. Cost/month |
|-----------|------|----------------|
| EC2 instance | t3.xlarge (4 vCPU, 16 GB) | ~$120 |
| RDS PostgreSQL | db.t3.small (Airbyte metadata DB) | ~$30 |
| EBS storage | 100 GB gp3 | ~$10 |
| Monitoring/misc | CloudWatch, logs | ~$10 |
| **Total** | | **~$170/month** |

No per-row or per-credit charges — flat infra cost regardless of sync volume. Requires self-management of updates, scaling, and monitoring.

---

## Total Migration Cost Summary

| Component | One-Time | Monthly (ongoing) |
|-----------|----------|-------------------|
| BQ → GCS export | $0 | — |
| GCS → AWS egress (1 TB, Standard Tier) | ~$76 | — |
| Airbyte Cloud (5M rows/day) | — | ~$2,250 |
| Airbyte Self-Hosted | — | ~$170 |
