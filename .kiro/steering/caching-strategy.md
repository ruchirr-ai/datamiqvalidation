---
inclusion: always
---

# Caching Strategy

## Redis as Cache Layer

### Overview
Redis is used as the primary caching layer to accelerate UI loading and reduce database load. All frequently accessed data should be cached in Redis with appropriate TTL (Time To Live) values.

### Cache-Aside Pattern
Implement the cache-aside (lazy loading) pattern with fallback to database:

1. **Read Flow**:
   - Check Redis cache first
   - If cache hit: return cached data
   - If cache miss or Redis unavailable: fetch from PostgreSQL
   - Store fetched data in Redis for future requests
   - Return data to client

2. **Write Flow**:
   - Write data to PostgreSQL (source of truth)
   - Invalidate or update Redis cache
   - Return success to client

### Fallback Strategy
**CRITICAL**: If Redis is not accessible, the application MUST continue to function by falling back to the database.

```python
def get_data(key):
    try:
        # Try Redis first
        cached_data = redis_client.get(key)
        if cached_data:
            return json.loads(cached_data)
    except (RedisError, ConnectionError) as e:
        logger.warning(f"Redis unavailable: {e}, falling back to database")
    
    # Fallback to database
    data = db.query(...)
    
    # Try to cache for next time (best effort)
    try:
        redis_client.setex(key, ttl, json.dumps(data))
    except Exception as e:
        logger.warning(f"Failed to cache data: {e}")
    
    return data
```

### What to Cache

#### High Priority (Short TTL: 1-5 minutes)
- Active migration status and progress
- Real-time monitoring metrics
- Current task states
- User session data

#### Medium Priority (Medium TTL: 15-60 minutes)
- Database connection metadata
- Assessment reports
- Migration project configurations
- Validation results

#### Low Priority (Long TTL: 1-24 hours)
- Database type mappings
- Static configuration data
- User preferences
- Lookup tables

### Cache Keys Convention
Use consistent, hierarchical key naming:
```
{module}:{entity}:{id}:{attribute}

Examples:
- connections:metadata:conn-123
- projects:config:proj-456
- monitoring:metrics:task-789
- assessment:report:assess-101
```

### TTL Guidelines
- **Real-time data**: 1-5 minutes
- **Frequently changing data**: 15-30 minutes
- **Moderately stable data**: 1-4 hours
- **Stable data**: 12-24 hours
- **Static data**: 24+ hours

### Cache Invalidation
Implement cache invalidation strategies:

1. **Time-based**: Use TTL for automatic expiration
2. **Event-based**: Invalidate on data updates
3. **Pattern-based**: Invalidate related keys using patterns

```python
# Invalidate specific key
redis_client.delete(f"projects:config:{project_id}")

# Invalidate pattern
keys = redis_client.keys(f"monitoring:metrics:task-{task_id}:*")
if keys:
    redis_client.delete(*keys)
```

### Redis Configuration
Configure Redis via .env:
```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password
REDIS_SSL=true
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
```

### AWS ElastiCache
For production, use AWS ElastiCache for Redis:
- Enable encryption in transit
- Enable encryption at rest
- Use Redis 6.x or higher
- Enable automatic failover
- Use cluster mode for high availability
- Configure appropriate instance size
- Enable CloudWatch metrics

### Error Handling
- Never let Redis failures break the application
- Always have database fallback
- Log Redis errors for monitoring
- Implement circuit breaker pattern for Redis
- Set reasonable timeouts

### Monitoring
Monitor Redis performance:
- Cache hit/miss ratio
- Memory usage
- Connection pool status
- Command latency
- Eviction rate
- Network throughput

### Best Practices
- Use connection pooling
- Implement retry logic with exponential backoff
- Set appropriate timeouts
- Use Redis pipelines for bulk operations
- Compress large cached values
- Monitor cache size and eviction policies
- Use Redis Sentinel or Cluster for HA
- Regularly review and optimize cache keys
