# Redshift Connection Troubleshooting Guide

## ✅ Connection Test Result

The connection test is working correctly! The error you're seeing is:

```
Connection timeout. Please check:
• Server is reachable
• Network connectivity
• Firewall rules
• Server is running

Error: connection to server at "redshift-demo.c3aimiew2vuv.us-east-1.redshift.amazonaws.com" (54.164.74.249), port 5439 failed: timeout expired
```

This is a **network connectivity issue**, not a code problem. The application is correctly trying to connect to your Redshift cluster, but it cannot reach it.

## 🔍 Root Cause

The timeout error means your local machine (localhost) cannot reach the Redshift cluster. This is typically because:

1. **Redshift cluster is not publicly accessible**
2. **Security group doesn't allow your IP**
3. **Cluster is in a private VPC subnet**
4. **Cluster is paused**

## 🛠️ Solutions

### Option 1: Make Redshift Publicly Accessible (For Testing Only)

⚠️ **Warning**: Only do this for development/testing. Never expose production databases publicly.

1. Go to AWS Console → Amazon Redshift
2. Select your cluster (`redshift-demo`)
3. Click "Actions" → "Modify"
4. Under "Network and security":
   - Set "Publicly accessible" to **Yes**
5. Click "Modify cluster"
6. Wait for the modification to complete

### Option 2: Update Security Group Rules

1. Go to AWS Console → Amazon Redshift
2. Select your cluster
3. Click on the "Properties" tab
4. Under "Network and security settings", click on the VPC security group
5. Click "Edit inbound rules"
6. Add a new rule:
   - **Type**: Custom TCP
   - **Port**: 5439
   - **Source**: 
     - For testing: `My IP` (automatically detects your IP)
     - For specific IP: `<your-ip-address>/32`
     - For any IP (NOT RECOMMENDED): `0.0.0.0/0`
7. Click "Save rules"

### Option 3: Use AWS VPN or Direct Connect

For production environments:
1. Set up AWS VPN or Direct Connect
2. Connect your local network to the VPC
3. Keep Redshift in private subnet

### Option 4: Deploy Application to AWS

The recommended approach for production:

1. Deploy the backend to AWS (EC2, ECS, or App Runner)
2. Place the application in the same VPC as Redshift
3. Configure security groups to allow traffic between them
4. Keep Redshift private (not publicly accessible)

## 🧪 Testing Connection

### Check if Redshift is Reachable

From your local machine (Windows):

```powershell
# Test if port 5439 is open
Test-NetConnection -ComputerName redshift-demo.c3aimiew2vuv.us-east-1.redshift.amazonaws.com -Port 5439
```

Expected output if accessible:
```
TcpTestSucceeded : True
```

Expected output if NOT accessible (current state):
```
TcpTestSucceeded : False
```

### Check Cluster Status

1. Go to AWS Console → Amazon Redshift
2. Check cluster status:
   - ✅ **Available**: Cluster is running
   - ⏸️ **Paused**: Cluster is paused (resume it)
   - 🔄 **Modifying**: Wait for modification to complete
   - ❌ **Unavailable**: Check cluster health

### Verify Credentials

Once network connectivity is established, verify your credentials:

- **Username**: `awsuser`
- **Password**: `g%+8L5L4bB7V`
- **Database**: `dev`
- **Port**: `5439`

## 📋 Quick Checklist

- [ ] Cluster status is "Available"
- [ ] Cluster is "Publicly accessible" (for local testing)
- [ ] Security group allows inbound traffic on port 5439 from your IP
- [ ] Cluster is not paused
- [ ] Endpoint is correct: `redshift-demo.c3aimiew2vuv.us-east-1.redshift.amazonaws.com`
- [ ] Port is correct: `5439`
- [ ] Database name is correct: `dev`

## 🎯 Recommended Approach

### For Local Development:

1. Make cluster publicly accessible
2. Add your IP to security group
3. Test connection
4. Once working, create connections in the app

### For Production:

1. Deploy application to AWS
2. Keep Redshift private
3. Use VPC security groups for access control
4. Use IAM authentication if possible

## 🔐 Security Best Practices

1. **Never expose Redshift publicly in production**
2. **Use VPC and security groups** for network isolation
3. **Rotate credentials regularly**
4. **Use IAM database authentication** when possible
5. **Enable encryption** at rest and in transit
6. **Use AWS Secrets Manager** for credential storage
7. **Audit access** with CloudTrail and database audit logging

## 📞 Next Steps

1. **Check your Redshift cluster settings** in AWS Console
2. **Make it publicly accessible** (for testing only)
3. **Update security group** to allow your IP
4. **Test connection again** in the application
5. **Once working**, you can create the connection and start migrations

## 💡 Alternative: Use EC2 Bastion Host

If you don't want to make Redshift public:

1. Launch an EC2 instance in the same VPC as Redshift
2. SSH into the EC2 instance
3. Use SSH tunneling to forward port 5439:
   ```bash
   ssh -i your-key.pem -L 5439:redshift-endpoint:5439 ec2-user@ec2-ip
   ```
4. Connect to `localhost:5439` from your application

## 📚 AWS Documentation

- [Redshift Security Groups](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-security-groups.html)
- [Publicly Accessible Clusters](https://docs.aws.amazon.com/redshift/latest/mgmt/managing-clusters-vpc.html)
- [Connecting to Redshift](https://docs.aws.amazon.com/redshift/latest/mgmt/connecting-to-cluster.html)
