# BigQuery to Redshift Migration — Discovery Questionnaire

**Customer Name:** ___________________________
**Date:** ___________________________
**Prepared by:** ShellKode Pvt Ltd

---

## Section 1: BigQuery Workload Profile

| # | Question | SQL (run in BQ console) | Answer |
|---|----------|------------------------|--------|
| 1.1 | Total data size in BigQuery | `SELECT SUM(size_bytes)/POW(1024,4) AS total_tb FROM \`region-YOUR_REGION.INFORMATION_SCHEMA.TABLE_STORAGE\` WHERE table_type='BASE TABLE'` | ________ TB |
| 1.2 | Daily incremental data volume | `SELECT DATE(creation_time) AS day, SUM(total_bytes_processed)/POW(1024,3) AS gb_loaded FROM \`region-YOUR_REGION.INFORMATION_SCHEMA.JOBS\` WHERE job_type='LOAD' AND creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY day ORDER BY day DESC` | ~________ GB/day |
| 1.3 | Average slot utilization | `SELECT ROUND(AVG(period_slot_ms)/1000, 1) AS avg_slots FROM \`region-YOUR_REGION.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT\` WHERE period_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)` | ________ avg slots |
| 1.4 | Peak slot utilization | `SELECT ROUND(MAX(period_slot_ms)/1000, 1) AS peak_slots FROM \`region-YOUR_REGION.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT\` WHERE period_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)` | ________ peak slots |
| 1.5 | TB of data scanned per day | `SELECT DATE(creation_time) AS day, ROUND(SUM(total_bytes_processed)/POW(1024,4), 2) AS tb_scanned FROM \`region-YOUR_REGION.INFORMATION_SCHEMA.JOBS\` WHERE job_type='QUERY' AND creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY day ORDER BY day DESC` | ~________ TB/day |

---

## Section 2: Data Sources & Ingestion

| # | Question | Answer |
|---|----------|--------|
| 2.1 | List all sources that dump data into BigQuery (e.g., Firebase, PostgreSQL, APIs, flat files, Pub/Sub) | |
| 2.2 | For each source — daily incremental data volume | |
| 2.3 | For each source — ingestion method (Datastream, Dataflow, scheduled query, manual upload, etc.) | |
| 2.4 | For each source — refresh frequency (real-time, 15-min, hourly, daily) | |
| 2.5 | Are there any CDC (Change Data Capture) pipelines? If yes, which tool? | |

---

## Section 3: Airflow DAGs

| # | Question | Answer |
|---|----------|--------|
| 3.1 | Where is Airflow hosted? (Cloud Composer, self-hosted VM, etc.) | |
| 3.2 | Total number of Airflow DAGs | |
| 3.3 | List of DAGs that extract data FROM BigQuery (name + schedule) | |
| 3.4 | For each BQ-extracting DAG — the SQL queries used | |
| 3.5 | For each BQ-extracting DAG — destination (PostgreSQL, GCS, API, etc.) | |
| 3.6 | List of DAGs that load data INTO BigQuery (name + source + schedule) | |
| 3.7 | Any DAGs that run transformations within BigQuery? | |

---

## Section 4: Downstream Consumers

| # | Question | Answer |
|---|----------|--------|
| 4.1 | What BI tools connect to BigQuery? (Metabase, Looker, Tableau, etc.) | |
| 4.2 | How many dashboards/reports are powered by BigQuery? | |
| 4.3 | Any applications that query BigQuery directly via API/JDBC? | |

---

## Section 5: Current Costs

| # | Question | Answer |
|---|----------|--------|
| 5.1 | Current monthly BigQuery cost (compute + storage) | ₹ / $ |
| 5.2 | BigQuery pricing model (on-demand or editions)? | |
| 5.3 | Preferred AWS region for Redshift? | |

---

**Note:** Replace `YOUR_REGION` with your BigQuery dataset region (e.g., `us`, `eu`, `asia-south1`) in the SQL queries above.
