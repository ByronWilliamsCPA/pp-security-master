# ADR-007: Deployment and Infrastructure Strategy

**Date**: 2025-08-22  
**Status**: Deferred (accepted in principle; not yet implemented as of 2026-06-19)  
**Deciders**: Byron, Development Team  
**Consulted**: Unraid Community Apps Documentation, PostgreSQL 17 Performance Guidelines, Docker Best Practices  
**Informed**: Infrastructure Team, Operations Team  

## Context

The Security Master Service requires a robust, scalable infrastructure that balances enterprise-grade capabilities with home lab practicality. The system must handle:

- **PostgreSQL 17**: Primary database for all financial data storage
- **Python Application**: FastAPI service for web UI and API endpoints
- **Background Workers**: Async processing for API calls and data classification
- **Redis Cache**: High-performance caching for external API responses
- **File Storage**: Secure storage for raw broker files and backups

The infrastructure operates on Unraid, which provides enterprise storage capabilities with user-friendly management. Key requirements include:

1. **Performance**: Support for 10,000+ securities with real-time classification
2. **Reliability**: 99.9% uptime for financial data access
3. **Security**: Isolated networks and encrypted data storage
4. **Scalability**: Ability to add processing power as data volume grows
5. **Maintainability**: Simple deployment and update procedures

## Infrastructure Requirements Analysis

### Performance Requirements

- **Database**: PostgreSQL 17 with 10,000+ securities, 100,000+ transactions
- **API Response**: <2 seconds for individual security classification
- **Batch Processing**: 1,000+ securities processed overnight
- **Concurrent Users**: 5-10 simultaneous web UI users
- **Storage**: 100GB+ for financial data, 500GB+ for raw file archives

### Reliability Requirements

- **Database Uptime**: 99.9% availability (8.76 hours downtime/year)
- **Backup Strategy**: Automated daily backups with 7-year retention
- **Disaster Recovery**: <4 hours to restore from backup
- **Data Integrity**: Zero data loss during normal operations
- **Service Recovery**: <15 minutes to restart services after failure

## Decision

We will implement a **containerized microservices architecture** on Unraid using Docker Compose with PostgreSQL 17 as the primary database, Redis for caching, and a Python FastAPI application with background workers.

### Infrastructure Architecture

#### **Unraid Host Configuration**

```yaml
# Unraid System Specifications
system:
  cpu: "Modern multi-core CPU (8+ cores recommended)"
  memory: "32GB+ RAM for database performance"
  storage:
    cache_pool: "1TB+ NVMe SSD for database and active files"
    array_storage: "Multi-TB for long-term archive storage"
    backup_storage: "Separate backup destination (local + offsite)"
  
  network:
    primary: "Gigabit Ethernet minimum"
    isolation: "VLANs for service separation"
    backup: "Secondary network for backup operations"
```

#### **Container Architecture**

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgresql:
    image: postgres:17-alpine
    container_name: pp_security_db
    environment:
      POSTGRES_DB: pp_security_master
      POSTGRES_USER: pp_admin
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./backups:/var/lib/postgresql/backups
      - ./init:/docker-entrypoint-initdb.d
    networks:
      - database_net
    secrets:
      - db_password
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    container_name: pp_security_cache
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - cache_net
    restart: unless-stopped
    
  api:
    build: 
      context: .
      dockerfile: docker/api.Dockerfile
    container_name: pp_security_api
    environment:
      DATABASE_URL: postgresql://pp_admin:${DB_PASSWORD}@postgresql:5432/pp_security_master
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - api_net
      - database_net
      - cache_net
    depends_on:
      - postgresql
      - redis
    restart: unless-stopped
    
  worker:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    container_name: pp_security_worker
    environment:
      DATABASE_URL: postgresql://pp_admin:${DB_PASSWORD}@postgresql:5432/pp_security_master
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - database_net
      - cache_net
    depends_on:
      - postgresql
      - redis
    restart: unless-stopped

networks:
  api_net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24
  database_net:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.21.0.0/24
  cache_net:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.22.0.0/24

volumes:
  pg_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/cache/appdata/pp-security/postgresql
  redis_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/cache/appdata/pp-security/redis

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

### PostgreSQL 17 Optimization

#### **Database Configuration**

```sql
-- postgresql.conf optimizations for financial data workload
-- Memory settings
shared_buffers = '8GB'                    # 25% of system RAM
effective_cache_size = '24GB'             # 75% of system RAM
work_mem = '256MB'                        # For complex queries
maintenance_work_mem = '1GB'              # For VACUUM, indexes

-- Connection settings
max_connections = 200                     # Support concurrent users
superuser_reserved_connections = 3        # Admin connections

-- Checkpoint settings
checkpoint_completion_target = 0.9        # Spread I/O load
checkpoint_timeout = '15min'              # Checkpoint frequency
max_wal_size = '4GB'                      # WAL file management
min_wal_size = '1GB'

-- Query optimization
random_page_cost = 1.1                    # SSD-optimized
effective_io_concurrency = 200            # SSD concurrent I/O
seq_page_cost = 1.0                       # Sequential scan cost

-- Logging and monitoring
log_statement = 'mod'                     # Log data modifications
log_min_duration_statement = 1000         # Log slow queries (>1s)
log_checkpoints = on                      # Monitor checkpoint performance
log_connections = on                      # Track connections
log_disconnections = on
```

#### **Database Schema Optimization**

```sql
-- Index strategy for financial data queries
CREATE INDEX CONCURRENTLY idx_securities_master_isin 
    ON securities_master (isin) WHERE isin IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_securities_master_symbol 
    ON securities_master (symbol) WHERE symbol IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_transactions_date_security 
    ON consolidated_transactions (transaction_date, security_id);

CREATE INDEX CONCURRENTLY idx_transactions_institution_type 
    ON consolidated_transactions (institution, transaction_type);

-- Partitioning for large transaction tables
CREATE TABLE pp_account_transactions_2024 PARTITION OF pp_account_transactions
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE pp_account_transactions_2025 PARTITION OF pp_account_transactions
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
```

### Storage Strategy

#### **Unraid Storage Configuration**

```yaml
storage_pools:
  cache_pool:
    type: "NVMe SSD"
    size: "1TB+"
    purpose: "Hot data (database, logs, active processing)"
    backup: "Daily incremental to array"
    
  array_storage:
    type: "HDD Array with parity"
    size: "Multi-TB"
    purpose: "Archive storage (raw files, historical data)"
    backup: "Weekly full to offsite"
    
  backup_pool:
    type: "Separate physical storage"
    size: "2x primary data"
    purpose: "Local backup copies"
    encryption: "Full disk encryption"

directory_structure:
  /mnt/cache/appdata/pp-security/:
    - postgresql/          # Database files
    - redis/              # Cache data
    - logs/               # Application logs
    - temp/               # Temporary processing files
    
  /mnt/user/pp-security/:
    - raw_files/          # Original broker files
    - backups/            # Database backups
    - exports/            # Generated reports
    - archive/            # Historical data
```

#### **Backup and Recovery Strategy**

```bash
#!/bin/bash
# Automated backup script for PostgreSQL and application data

# Daily incremental database backup
docker exec pp_security_db pg_dump \
    -U pp_admin \
    -Fc \
    -f /var/lib/postgresql/backups/daily_$(date +%Y%m%d).dump \
    pp_security_master

# Weekly full system backup
tar -czf /mnt/user/pp-security/backups/full_$(date +%Y%m%d).tar.gz \
    /mnt/cache/appdata/pp-security/

# Offsite backup via rclone
rclone sync /mnt/user/pp-security/backups/ \
    remote:pp-security-backups/ \
    --encrypt-password="$BACKUP_PASSWORD"

# Cleanup old backups (retain 30 days local, 1 year offsite)
find /mnt/user/pp-security/backups/ -name "daily_*.dump" -mtime +30 -delete
find /mnt/user/pp-security/backups/ -name "full_*.tar.gz" -mtime +90 -delete
```

### Performance Monitoring and Alerting

#### **System Monitoring Stack**

```yaml
monitoring:
  prometheus:
    image: prom/prometheus
    config: ./monitoring/prometheus.yml
    retention: "90d"
    
  grafana:
    image: grafana/grafana
    dashboards:
      - postgresql_performance
      - application_metrics
      - infrastructure_health
      
  alertmanager:
    image: prom/alertmanager
    rules:
      - database_performance
      - disk_space
      - service_health
```

#### **Key Performance Metrics**

```yaml
alerts:
  database:
    - name: "High Query Duration"
      threshold: ">5 seconds average"
      action: "Alert and log slow queries"
      
    - name: "Connection Pool Exhaustion"
      threshold: ">90% connections used"
      action: "Scale up or optimize connections"
      
    - name: "Disk Space Critical"
      threshold: "<10% free space"
      action: "Emergency cleanup and alert"
      
  application:
    - name: "API Response Time"
      threshold: ">3 seconds p95"
      action: "Check external API performance"
      
    - name: "Classification Queue Backlog"
      threshold: ">1000 pending items"
      action: "Scale worker processes"
      
    - name: "Memory Usage High"
      threshold: ">85% RAM utilization"
      action: "Review memory leaks and optimize"
```

## Deployment Strategy

### Environment Management

```bash
# Production deployment script
#!/bin/bash

# Environment setup
export ENVIRONMENT="production"
export LOG_LEVEL="WARNING"
export DEBUG="false"

# Database migration
docker-compose exec api alembic upgrade head

# Service health check
./scripts/health_check.sh

# Rolling deployment
docker-compose up -d --force-recreate --renew-anon-volumes

# Verification
./scripts/verify_deployment.sh
```

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy to Unraid

on:
  push:
    branches: [main]
    
jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Run tests
        run: uv run pytest
        
      - name: Security scan
        run: |
          uv run pip-audit
          uv run bandit -r src
          
      - name: Build images
        run: docker-compose build
        
      - name: Deploy services
        run: ./scripts/deploy.sh
        
      - name: Health check
        run: ./scripts/health_check.sh
```

## Security and Network Architecture

### Network Isolation

```yaml
network_architecture:
  external_access:
    - cloudflare_tunnel:
        port: 443
        destination: "api:5050"
        encryption: "TLS 1.3"
        
  internal_networks:
    - api_net: "172.20.0.0/24"      # API server network
    - database_net: "172.21.0.0/24" # Database isolation
    - cache_net: "172.22.0.0/24"    # Redis cache network
    
  firewall_rules:
    - block_all_by_default: true
    - allow_cloudflare_ips: true
    - allow_internal_communication: true
    - block_external_database_access: true
```

### Data Encryption

```yaml
encryption_strategy:
  at_rest:
    - postgresql_tde: "AES-256"
    - volume_encryption: "LUKS2"
    - backup_encryption: "GPG + AES-256"
    
  in_transit:
    - api_traffic: "TLS 1.3"
    - database_connections: "SSL/TLS"
    - internal_services: "mTLS"
    
  key_management:
    - hardware_security: "TPM 2.0"
    - key_rotation: "90 days"
    - backup_keys: "Offsite secure storage"
```

## Scalability and Growth Planning

### Horizontal Scaling Strategy

```yaml
scaling_options:
  database:
    - read_replicas: "PostgreSQL streaming replication"
    - connection_pooling: "PgBouncer for connection management"
    - query_optimization: "Regular EXPLAIN ANALYZE review"
    
  application:
    - load_balancing: "Multiple API containers behind HAProxy"
    - worker_scaling: "Celery workers based on queue depth"
    - caching: "Redis cluster for distributed caching"
    
  storage:
    - cache_expansion: "Additional NVMe SSDs as needed"
    - array_expansion: "Additional HDDs for archive storage"
    - network_upgrade: "10GbE for high-throughput operations"
```

### Resource Planning

```yaml
growth_projections:
  year_1:
    securities: "10,000"
    transactions: "100,000"
    storage: "500GB"
    users: "5"
    
  year_3:
    securities: "50,000"
    transactions: "1,000,000"
    storage: "2TB"
    users: "15"
    
  year_5:
    securities: "100,000"
    transactions: "5,000,000"
    storage: "10TB"
    users: "25"
```

## Disaster Recovery and Business Continuity

### Recovery Time Objectives (RTO)

- **Database Recovery**: <4 hours from backup
- **Application Recovery**: <1 hour from container restart
- **Full System Recovery**: <8 hours from bare metal
- **Data Recovery**: <24 hours from offsite backup

### Recovery Point Objectives (RPO)

- **Transaction Data**: <1 hour (via WAL shipping)
- **Classification Data**: <4 hours (via daily backup)
- **Raw Files**: <24 hours (via array parity)
- **Configuration**: <1 hour (via Git repository)

## Success Metrics

### Performance Targets

- **Database Query Performance**: <500ms p95 for common queries
- **API Response Time**: <2 seconds p95 for classification requests
- **Batch Processing**: 1,000 securities classified per hour
- **System Availability**: 99.9% uptime (measured monthly)

### Operational Targets

- **Deployment Time**: <15 minutes for routine updates
- **Recovery Time**: <4 hours for database restoration
- **Backup Success Rate**: 100% for automated backups
- **Monitoring Coverage**: 100% of critical services monitored

## Consequences

### Positive

- **Enterprise Performance**: PostgreSQL 17 provides institutional-grade performance
- **Simplified Management**: Unraid provides user-friendly infrastructure management
- **Cost Efficiency**: Home lab infrastructure minimizes operational costs
- **Scalability**: Container architecture supports growth and feature expansion

### Negative

- **Single Point of Failure**: Home lab lacks enterprise redundancy
- **Network Dependency**: Relies on home internet for external API access
- **Hardware Limitations**: Physical server constraints limit maximum scale
- **Operational Complexity**: Full-stack management requires broad technical skills

### Risk Mitigation

- **Comprehensive Backups**: Multiple backup strategies mitigate hardware failure
- **Monitoring and Alerting**: Proactive monitoring minimizes downtime
- **Documentation**: Detailed procedures enable quick recovery
- **Staged Deployment**: Testing procedures minimize production issues

## Related Decisions

- **ADR-001**: Transaction-Centric Architecture (database design requirements)
- **ADR-006**: Security and Authentication Architecture (security infrastructure)
- **ADR-005**: External API Integration Strategy (external connectivity requirements)

## References

- PostgreSQL 17 Performance Tuning Guide
- Unraid Community Apps Documentation
- Docker Compose Best Practices
- Cloudflare Tunnel Configuration Guide
- Database Backup and Recovery Strategies
