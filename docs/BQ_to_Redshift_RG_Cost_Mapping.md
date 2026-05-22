# BigQuery to Redshift RG (Graviton) — Cost Mapping (Mumbai, ap-south-1)

**Mapping:** 1 BigQuery slot = 1 GiB memory

**RG Instance Specs:**
- rg.xlarge: 4 vCPUs, 32 GiB RAM, 32 TB max RMS
- rg.4xlarge: 16 vCPUs, 128 GiB RAM, 128 TB max RMS

**Mumbai Pricing (estimated, 30% lower per-vCPU than RA3 Mumbai):**
- rg.xlarge: ~$0.865/hr ($631/mo per node)
- rg.4xlarge: ~$3.46/hr ($2,526/mo per node)
- RMS storage: $0.024/GB/month

---

## Redshift RG Provisioned (Mumbai)

| BQ Slots | Memory (GiB) | RG Node Type | Nodes | Cost ($/month) | Max Storage | Storage Cost ($/mo) |
|----------|-------------|-------------|-------|---------------|-------------|-------------------|
| 100 | 100 | rg.xlarge | 3 | $1,893 | 96 TB | $2.40 |
| 200 | 200 | rg.xlarge | 6 | $3,786 | 192 TB | $4.80 |
| 300 | 300 | rg.xlarge | 9 | $5,679 | 288 TB | $7.20 |
| 400 | 400 | rg.xlarge | 13 | $8,203 | 416 TB | $9.60 |
| 500 | 500 | rg.xlarge | 16 | $10,096 | 512 TB | $12.00 |
| 600 | 600 | rg.4xlarge | 5 | $12,630 | 640 TB | $14.40 |
| 700 | 700 | rg.4xlarge | 6 | $15,156 | 768 TB | $16.80 |
| 800 | 800 | rg.4xlarge | 6 | $15,156 | 768 TB | $19.20 |
| 900 | 900 | rg.4xlarge | 7 | $17,682 | 896 TB | $21.60 |
| 1,000 | 1,000 | rg.4xlarge | 8 | $20,208 | 1,024 TB | $24.00 |
| 1,200 | 1,200 | rg.4xlarge | 10 | $25,260 | 1,280 TB | $28.80 |
| 1,400 | 1,400 | rg.4xlarge | 11 | $27,786 | 1,408 TB | $33.60 |
| 1,600 | 1,600 | rg.4xlarge | 13 | $32,838 | 1,664 TB | $38.40 |
| 1,800 | 1,800 | rg.4xlarge | 14 | $35,364 | 1,792 TB | $43.20 |
| 2,000 | 2,000 | rg.4xlarge | 16 | $40,416 | 2,048 TB | $48.00 |
| 2,500 | 2,500 | rg.4xlarge | 20 | $50,520 | 2,560 TB | $60.00 |
| 3,000 | 3,000 | rg.4xlarge | 24 | $60,624 | 3,072 TB | $72.00 |
| 3,500 | 3,500 | rg.4xlarge | 28 | $70,728 | 3,584 TB | $84.00 |
| 4,000 | 4,000 | rg.4xlarge | 32 | $80,832 | 4,096 TB | $96.00 |
| 4,500 | 4,500 | rg.4xlarge | 36 | $90,936 | 4,608 TB | $108.00 |
| 5,000 | 5,000 | rg.4xlarge | 40 | $101,040 | 5,120 TB | $120.00 |

---

## RG vs RA3 Savings (Mumbai, same node count logic)

| BQ Slots | RA3 ($/mo) | RG ($/mo) | Savings $ | Savings % |
|----------|-----------|-----------|-----------|-----------|
| 100 | $2,705 | $1,893 | $812 | 30% |
| 300 | $8,114 | $5,679 | $2,435 | 30% |
| 600 | $16,232 | $12,630 | $3,602 | 22% |
| 1,000 | $27,054 | $20,208 | $6,846 | 25% |
| 2,000 | $45,991 | $40,416 | $5,575 | 12% |
| 5,000 | $108,237 | $101,040 | $7,197 | 7% |

**Note:** At higher slot counts, RG savings per node are offset by needing more nodes (rg.4xlarge = 128 GiB vs ra3.16xlarge = 384 GiB). Once larger RG instance sizes launch (expected later 2026), savings at scale will improve.

---

## Key Differences: RG vs RA3

| | rg.xlarge | ra3.xlplus | rg.4xlarge | ra3.4xlarge |
|---|---|---|---|---|
| vCPUs | 4 | 4 | 16 | 12 |
| Memory | 32 GiB | 32 GiB | 128 GiB | 96 GiB |
| Mumbai $/hr | ~$0.865 | $1.235 | ~$3.46 | $3.706 |
| Mumbai $/mo | ~$631 | $902 | ~$2,526 | $2,705 |
| Spectrum charges | None (built-in) | $5/TB scanned | None (built-in) | $5/TB scanned |
| Data lake engine | Integrated vectorized | Spectrum (external) | Integrated vectorized | Spectrum (external) |
| Performance vs RA3 | Up to 2.2x faster | baseline | Up to 2.4x faster | baseline |

*Sources: AWS Redshift Pricing, RG Launch Blog (May 2026). Mumbai RG pricing estimated from 30% per-vCPU discount on RA3 Mumbai rates.*
