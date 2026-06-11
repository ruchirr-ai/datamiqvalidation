"""
BigQuery to Apache Iceberg Migration Service

Provides schema mapping, partitioning, data loading, and validation
for migrating BigQuery tables to Apache Iceberg on AWS (S3 or S3 Tables).

Features:
- BQ-to-Iceberg type mapping with recursive STRUCT support
- Partition spec mapping with day() default for time-based columns
- Parallel table loading with configurable worker pool
- Schema evolution for incremental loads
- Deduplication guard for retry/resume safety
- Structure report generation with cost analysis
"""
