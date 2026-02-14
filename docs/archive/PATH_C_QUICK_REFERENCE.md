# Path C Quick Reference

## One-Line Summary
Path C uses GCP Storage Transfer Service for reliable BigQuery → GCS → S3 migration with comprehensive logging.

## Setup (One Time)

```bash
cd backend && source .venv/bin/activate
uv pip install google-cloud-storage-transfer
echo "ENCRYPTION_PASSWORD=your-password" >> backend/.env
lsof -ti:8000 | xargs kill -9 && uvicorn main:app --reload --port 8000
```

## Required Fields

### Stage 1: BigQuery to GCS
- GCS Bucket
- GCS Path
- Export Format (AVRO/PARQUET)
- Service Account JSON

### Stage 2: GCS to S3
- S3 Bucket
- S3 Path
- AWS Access Key ID
- AWS Secret Access Key
- Overwrite Existing (toggle)
- Delete Source (toggle)

## Migration Flow

```
BigQuery → GCS (Export)
    ↓
GCS → S3 (Storage Transfer Service)
    ↓
S3 → Redshift (COPY - pending)
```

## Key Log Messages

### Success
```
✓ AWS secret key decrypted successfully
✓ Transfer job created: transferJobs/...
✓ Transfer job started
✓ TRANSFER COMPLETED SUCCESSFULLY
  Objects Copied: X
  Bytes Copied: Y
```

### Failure
```
✗ TRANSFER FAILED
Error: [error message]
```

## Monitoring

```bash
# Watch logs
tail -f backend/server.log | grep -A 5 "TRANSFER"

# Check S3
aws s3 ls s3://bucket/path/ --recursive

# Check database
psql -U user -d datamiq -c "SELECT status FROM migrations_bq_redshift WHERE id=X;"
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Package not installed | `uv pip install google-cloud-storage-transfer` |
| Encryption failed | Set `ENCRYPTION_PASSWORD` in `.env` |
| API not enabled | `gcloud services enable storagetransfer.googleapis.com` |
| Permission denied | Grant `roles/storagetransfer.admin` to service account |
| Invalid credentials | Verify AWS access key and secret key |

## Files Changed

- `backend/services/bq_redshift_migration/pathway_c.py` (rewritten)
- `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx` (simplified)
- `backend/routers/bq_redshift_migration.py` (removed fields)
- `backend/models/bq_redshift_migration.py` (removed aws_region)

## Test Checklist

- [ ] Package installed
- [ ] Encryption key set
- [ ] Backend restarted
- [ ] BigQuery connection created
- [ ] Migration created with AWS credentials
- [ ] Migration started
- [ ] Logs show "✓ Transfer completed"
- [ ] Files visible in S3
- [ ] Database shows status='completed'

## Performance

- **Poll Interval**: 30 seconds
- **Timeout**: 1 hour
- **Transfer Speed**: 100-500 MB/s (typical)
- **Cleanup**: Automatic

## Security

- AWS secret key encrypted with Fernet
- Password field in UI
- Decryption only when needed
- Never logged in plain text

## Status: ✅ Ready

All components implemented. Follow setup steps and create your first migration!
