from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.kms_encryption_service import get_kms_encryption_service

db = next(get_db())
m = db.query(MigrationBQRedshift).filter_by(id=20).first()

print(f"access_key: [{m.aws_access_key_id}]")
print(f"access_key_len: {len(m.aws_access_key_id) if m.aws_access_key_id else 0}")
print(f"access_key_starts: {m.aws_access_key_id[:4] if m.aws_access_key_id else 'N/A'}")

enc = m.aws_secret_access_key_encrypted or ''
print(f"secret_encrypted_len: {len(enc)}")

try:
    svc = get_kms_encryption_service()
    secret = svc.decrypt(enc, {"migration_id": "20", "field": "aws_secret_access_key"})
except Exception as e:
    print(f"KMS decrypt failed: {e}")
    secret = enc

print(f"secret_len: {len(secret)}")
print(f"secret_has_plus: {'+' in secret}")
print(f"secret_has_slash: {'/' in secret}")
print(f"secret_has_newline: {chr(10) in secret or chr(13) in secret}")
print(f"secret_has_space: {' ' in secret}")
print(f"secret_repr: {repr(secret)}")
db.close()
