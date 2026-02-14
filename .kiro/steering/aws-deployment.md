---
inclusion: always
---

# AWS Deployment & Best Practices

## AWS Services

### Core Services
- **ECS/EKS**: Container orchestration for backend
- **RDS PostgreSQL**: Managed database service
- **ElastiCache Redis**: Managed Redis cache layer
- **KMS**: Key management for encryption
- **Secrets Manager**: Secure credential storage
- **CloudWatch**: Logging and monitoring
- **S3**: Backup storage and static assets
- **VPC**: Network isolation
- **ALB**: Application load balancing

### Optional Services
- **CloudFront**: CDN for frontend
- **Route 53**: DNS management
- **WAF**: Web application firewall
- **GuardDuty**: Threat detection
- **Config**: Compliance monitoring
- **CloudTrail**: API audit logging

## Infrastructure as Code
- Use Terraform or AWS CDK
- Version control all infrastructure code
- Use separate stacks per environment
- Implement proper state management
- Document infrastructure dependencies

## Networking

### VPC Design
- Use private subnets for backend and database
- Use public subnets for load balancers only
- Implement NAT Gateway for outbound traffic
- Use multiple availability zones
- Implement proper security groups

### Security Groups
- Principle of least privilege
- Allow only required ports
- Use security group references
- Document all rules
- Regular security group audits

## High Availability

### Multi-AZ Deployment
- Deploy across multiple availability zones
- Use RDS Multi-AZ for database
- Use ALB for traffic distribution
- Implement health checks
- Auto-scaling for backend services

### Disaster Recovery
- Automated backups to S3
- Cross-region replication for critical data
- Documented recovery procedures
- Regular DR testing
- RTO/RPO definitions

## Monitoring & Alerting

### CloudWatch Metrics
- Application metrics
- Database performance
- Infrastructure health
- Custom business metrics

### Alarms
- High error rates
- Database connection issues
- High latency
- Resource exhaustion
- Security events

### Dashboards
- Application health dashboard
- Migration progress dashboard
- Infrastructure dashboard
- Security dashboard

## Cost Optimization
- Use appropriate instance sizes
- Implement auto-scaling
- Use Spot instances where appropriate
- Set up cost alerts
- Regular cost reviews
- Use S3 lifecycle policies
- Implement database connection pooling

## Security Best Practices

### IAM
- Use IAM roles for services
- Implement least privilege
- Enable MFA for human users
- Regular access reviews
- Use IAM policies effectively

### Encryption
- Enable encryption at rest (RDS, S3)
- Use TLS for all connections
- KMS for key management
- Rotate encryption keys

### Compliance
- Enable CloudTrail
- Enable AWS Config
- Regular security audits
- Compliance reporting
- Vulnerability scanning

## Deployment Pipeline
- Use CI/CD (GitHub Actions, GitLab CI, or AWS CodePipeline)
- Automated testing before deployment
- Blue-green or canary deployments
- Automated rollback on failure
- Environment promotion (dev → staging → prod)
