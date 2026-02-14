# AWS DMS Redshift Connection Fields

## Overview

Complete list of fields required for AWS Database Migration Service (DMS) Redshift endpoint configuration. These fields should be included in the Admin > Data Connections section for Amazon Redshift.

## Required Fields

### Basic Connection Information

1. **Server Name** (ServerName)
   - Type: String
   - Required: Yes
   - Description: The name of the Amazon Redshift cluster
   - Example: `my-redshift-cluster.abc123.us-east-1.redshift.amazonaws.com`

2. **Port** (Port)
   - Type: Integer
   - Required: Yes
   - Default: 5439
   - Description: The port number for Amazon Redshift

3. **Database Name** (DatabaseName)
   - Type: String
   - Required: Yes
   - Description: The name of the Amazon Redshift database

4. **Username** (Username)
   - Type: String
   - Required: Yes
   - Description: Amazon Redshift user name for a registered user

5. **Password** (Password)
   - Type: String (Encrypted)
   - Required: Yes
   - Description: Password for the user

### S3 Staging Configuration

6. **S3 Bucket Name** (BucketName)
   - Type: String
   - Required: Yes
   - Description: Name of intermediate S3 bucket for .csv files
   - Example: `my-dms-staging-bucket`

7. **S3 Bucket Folder** (BucketFolder)
   - Type: String
   - Required: No
   - Description: S3 folder path for staging files
   - Example: `dms-staging/redshift`

8. **Service Access Role ARN** (ServiceAccessRoleArn)
   - Type: String
   - Required: Yes
   - Description: IAM role ARN with S3 and Redshift access
   - Example: `arn:aws:iam::123456789012:role/dms-redshift-role`

### Security & Encryption

9. **Encryption Mode** (EncryptionMode)
   - Type: Select
   - Options: `sse-s3` (default), `sse-kms`
   - Required: No
   - Description: Server-side encryption type for S3

10. **KMS Key ID** (ServerSideEncryptionKmsKeyId)
    - Type: String
    - Required: Only if EncryptionMode = sse-kms
    - Description: AWS KMS key ID for encryption
    - Example: `arn:aws:kms:us-east-1:123456789012:key/abc-123`

### AWS Secrets Manager (Alternative to Password)

11. **Secrets Manager Secret ID** (SecretsManagerSecretId)
    - Type: String
    - Required: No (alternative to password)
    - Description: ARN or name of Secrets Manager secret
    - Example: `arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift-creds`

12. **Secrets Manager Access Role ARN** (SecretsManagerAccessRoleArn)
    - Type: String
    - Required: Only if using Secrets Manager
    - Description: IAM role ARN for Secrets Manager access

### Connection Settings

13. **Connection Timeout** (ConnectionTimeout)
    - Type: Integer (milliseconds)
    - Required: No
    - Default: 60000
    - Description: Connection timeout in milliseconds

14. **Load Timeout** (LoadTimeout)
    - Type: Integer (milliseconds)
    - Required: No
    - Default: 1200000
    - Description: Timeout for COPY, INSERT, DELETE, UPDATE operations

### Data Loading Options

15. **Max File Size** (MaxFileSize)
    - Type: Integer (KB)
    - Required: No
    - Default: 1048576 (1 GB)
    - Description: Maximum .csv file size for S3 upload

16. **File Transfer Upload Streams** (FileTransferUploadStreams)
    - Type: Integer
    - Range: 1-64
    - Default: 10
    - Description: Number of parallel streams for S3 multipart upload

17. **Write Buffer Size** (WriteBufferSize)
    - Type: Integer (KB)
    - Required: No
    - Default: 1000
    - Description: In-memory buffer size for .csv generation

### Data Format Options

18. **Date Format** (DateFormat)
    - Type: String
    - Required: No
    - Default: 'YYYY-MM-DD'
    - Options: 'auto', custom format, or NULL
    - Description: Date format for data loading

19. **Time Format** (TimeFormat)
    - Type: String
    - Required: No
    - Default: 10
    - Options: 'auto', 'epochsecs', 'epochmillisecs', custom format
    - Description: Time format for data loading

20. **Accept Any Date** (AcceptAnyDate)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Allow invalid date formats (loads as NULL)

### Data Transformation Options

21. **Empty As Null** (EmptyAsNull)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Migrate empty CHAR/VARCHAR as NULL

22. **Trim Blanks** (TrimBlanks)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Remove trailing whitespace from VARCHAR

23. **Remove Quotes** (RemoveQuotes)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Remove surrounding quotation marks from strings

24. **Truncate Columns** (TruncateColumns)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Truncate data to fit column size

25. **Replace Invalid Chars** (ReplaceInvalidChars)
    - Type: String
    - Required: No
    - Description: Characters to replace in data

26. **Replace Chars** (ReplaceChars)
    - Type: String
    - Required: No
    - Default: "?"
    - Description: Replacement characters for invalid chars

### Compression & Optimization

27. **Comp Update** (CompUpdate)
    - Type: Boolean
    - Required: No
    - Default: true
    - Description: Apply automatic compression for empty tables

28. **Explicit IDs** (ExplicitIds)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Override IDENTITY columns with source values

29. **Map Boolean As Boolean** (MapBooleanAsBoolean)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Migrate boolean as boolean (not varchar(1))

### Schema Options

30. **Case Sensitive Names** (CaseSensitiveNames)
    - Type: Boolean
    - Required: No
    - Default: false
    - Description: Support case-sensitive schema names

31. **After Connect Script** (AfterConnectScript)
    - Type: Text
    - Required: No
    - Description: SQL code to run after connecting

## Field Grouping for UI

### Group 1: Basic Connection (Required)
- Server Name
- Port
- Database Name
- Username
- Password

### Group 2: S3 Staging (Required)
- S3 Bucket Name
- S3 Bucket Folder
- Service Access Role ARN

### Group 3: Security & Encryption (Optional)
- Encryption Mode
- KMS Key ID
- Secrets Manager Secret ID
- Secrets Manager Access Role ARN

### Group 4: Connection Settings (Optional)
- Connection Timeout
- Load Timeout

### Group 5: Performance Tuning (Optional)
- Max File Size
- File Transfer Upload Streams
- Write Buffer Size

### Group 6: Data Format (Optional)
- Date Format
- Time Format
- Accept Any Date

### Group 7: Data Transformation (Optional)
- Empty As Null
- Trim Blanks
- Remove Quotes
- Truncate Columns
- Replace Invalid Chars
- Replace Chars

### Group 8: Optimization (Optional)
- Comp Update
- Explicit IDs
- Map Boolean As Boolean
- Case Sensitive Names

### Group 9: Advanced (Optional)
- After Connect Script

## Implementation Priority

### Phase 1: Essential Fields (MVP)
1. Server Name
2. Port
3. Database Name
4. Username
5. Password
6. S3 Bucket Name
7. Service Access Role ARN

### Phase 2: Security & Performance
8. S3 Bucket Folder
9. Encryption Mode
10. KMS Key ID
11. Connection Timeout
12. Load Timeout
13. Max File Size

### Phase 3: Data Handling
14. Date Format
15. Time Format
16. Empty As Null
17. Trim Blanks
18. Comp Update

### Phase 4: Advanced Features
19. Secrets Manager integration
20. File Transfer Upload Streams
21. All remaining optional fields

## Validation Rules

1. **Server Name**: Must be valid Redshift cluster endpoint
2. **Port**: Must be integer, typically 5439
3. **S3 Bucket Name**: Must be valid S3 bucket name format
4. **Service Access Role ARN**: Must be valid IAM role ARN format
5. **KMS Key ID**: Required only if Encryption Mode = sse-kms
6. **Secrets Manager fields**: Both ARN fields required if using Secrets Manager
7. **Integer fields**: Must be within specified ranges
8. **Boolean fields**: true/false only

## Testing Requirements

For each Redshift connection, test:
1. Basic connectivity (server, port, database, credentials)
2. S3 bucket access (read/write permissions)
3. IAM role permissions (S3, Redshift, KMS if applicable)
4. Network connectivity (security groups, VPC)
5. Encryption settings (if KMS enabled)

## References

- [AWS DMS RedshiftSettings API](https://docs.aws.amazon.com/dms/latest/APIReference/API_RedshiftSettings.html)
- [AWS DMS Redshift as Target](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Target.Redshift.html)
- [Redshift COPY Command](https://docs.aws.amazon.com/redshift/latest/dg/r_COPY.html)
