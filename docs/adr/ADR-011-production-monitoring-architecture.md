# ADR-011: Production Monitoring & Observability Architecture

**Date**: 2025-08-23  
**Status**: Deferred (accepted in principle; not yet implemented as of 2026-06-19)  
**Deciders**: Byron, Development Team  
**Consulted**: Production Operations, Database Administration, Security Team  
**Informed**: Executive Stakeholders, QA Team  

## Context

The Security Master Service processes sensitive financial data with high availability requirements. The system needs comprehensive monitoring and observability to ensure:

**Operational Requirements**:

- 99.9% uptime target for production service
- Early detection of performance degradation
- Real-time alerting for system failures
- Complete audit trail for compliance and debugging

**Business Requirements**:

- Classification accuracy monitoring (>95% target)
- Data quality validation and alerting
- User satisfaction tracking
- Cost monitoring for external API usage

**Technical Requirements**:

- Database performance monitoring
- Application performance metrics
- Infrastructure resource monitoring  
- Security event detection and alerting

Current gaps identified from project planning review:

- No observability framework defined
- Missing production monitoring strategy
- No health check endpoints specified
- Inadequate alerting and notification system

## Decision

We will implement a **comprehensive, multi-layered monitoring and observability architecture** using modern observability principles with metrics, logging, tracing, and alerting.

### Monitoring Architecture Pillars

#### **Four Pillars of Observability**

```text
Metrics     → Quantitative measurements (response times, error rates, throughput)
Logging     → Structured event records with context and correlation
Tracing     → Request flow tracking across system components  
Alerting    → Proactive notification of issues and anomalies
```

#### **Monitoring Stack Architecture**

```python
# Core Monitoring Framework
class SecurityMasterObservability:
    """Comprehensive observability for Security Master Service"""
    
    def __init__(self):
        self.metrics_collector = PrometheusMetrics()
        self.logger = StructuredLogger()
        self.tracer = OpenTelemetryTracer()
        self.alerting = AlertManager()
    
    def instrument_application(self) -> None:
        """Add comprehensive instrumentation to application"""
        pass
    
    def setup_dashboards(self) -> None:
        """Configure monitoring dashboards"""
        pass
    
    def configure_alerts(self) -> None:
        """Set up alerting rules and notifications"""
        pass
```

## Monitoring Strategy

### Layer 1: Application Metrics

**Objectives**: Track application-level performance, business metrics, and user experience

#### **Business Metrics**

```python
class BusinessMetrics:
    """Track key business indicators"""
    
    def __init__(self):
        # Classification metrics
        self.classification_requests = Counter('classification_requests_total')
        self.classification_accuracy = Histogram('classification_accuracy_rate')
        self.classification_duration = Histogram('classification_duration_seconds')
        
        # Data quality metrics  
        self.data_quality_score = Gauge('data_quality_score')
        self.validation_failures = Counter('validation_failures_total')
        
        # User activity metrics
        self.active_users = Gauge('active_users_count')
        self.user_satisfaction = Histogram('user_satisfaction_rating')
```

#### **Application Performance Metrics**

```python
class ApplicationMetrics:
    """Track application performance indicators"""
    
    def __init__(self):
        # API performance
        self.http_request_duration = Histogram('http_request_duration_seconds')
        self.http_request_size = Histogram('http_request_size_bytes')
        self.http_response_size = Histogram('http_response_size_bytes')
        
        # Database metrics
        self.db_query_duration = Histogram('database_query_duration_seconds')
        self.db_connection_pool = Gauge('database_connection_pool_active')
        self.db_transaction_rate = Counter('database_transactions_total')
        
        # External API metrics
        self.external_api_calls = Counter('external_api_calls_total')
        self.external_api_latency = Histogram('external_api_latency_seconds')
        self.external_api_errors = Counter('external_api_errors_total')
```

#### **System Resource Metrics**

```python
class SystemMetrics:
    """Track system resource utilization"""
    
    def __init__(self):
        # Memory and CPU
        self.memory_usage = Gauge('memory_usage_bytes')
        self.cpu_usage = Gauge('cpu_usage_percent')
        
        # Disk and network
        self.disk_usage = Gauge('disk_usage_bytes')
        self.network_io = Counter('network_io_bytes_total')
        
        # Application-specific resources
        self.active_classification_workers = Gauge('classification_workers_active')
        self.queue_depth = Gauge('job_queue_depth')
```

### Layer 2: Structured Logging

**Objectives**: Provide detailed, searchable logs with correlation across system components

#### **Logging Architecture**

```python
import structlog
from typing import Dict, Any

class SecurityMasterLogger:
    """Structured logging with correlation and context"""
    
    def __init__(self):
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def log_classification_request(self, security_id: str, request_context: Dict[str, Any]) -> None:
        """Log classification request with full context"""
        logger = structlog.get_logger("classification")
        logger.info(
            "classification_request_started",
            security_id=security_id,
            user_id=request_context.get("user_id"),
            session_id=request_context.get("session_id"),
            request_id=request_context.get("request_id")
        )
    
    def log_database_operation(self, operation: str, table: str, duration: float) -> None:
        """Log database operations with performance metrics"""
        logger = structlog.get_logger("database")
        logger.info(
            "database_operation_completed",
            operation=operation,
            table=table,
            duration_ms=duration * 1000,
            slow_query=duration > 1.0
        )
```

#### **Log Categories & Levels**

**Application Logs**:

```python
# Classification engine logs
logger.info("classification_started", security_id="US0378331005")
logger.error("classification_failed", error="API timeout", security_id="US0378331005")

# Database operation logs  
logger.debug("query_executed", query="SELECT * FROM securities_master", duration=0.045)
logger.warning("slow_query_detected", query_id="abc123", duration=2.5)

# API interaction logs
logger.info("external_api_call", service="OpenFIGI", endpoint="/search", status=200)
logger.error("external_api_error", service="OpenFIGI", error="rate_limit_exceeded")
```

**Security Logs**:

```python
# Authentication events
logger.info("user_login", user_id="byron@domain.com", source_ip="192.168.1.100")
logger.warning("failed_login_attempt", source_ip="192.168.1.100", attempts=3)

# Authorization events  
logger.info("permission_granted", user_id="byron@domain.com", action="classify_security")
logger.error("permission_denied", user_id="readonly@domain.com", action="export_data")

# Data access events
logger.info("data_exported", user_id="byron@domain.com", record_count=1500)
logger.warning("bulk_export_attempted", user_id="analyst@domain.com", record_count=50000)
```

### Layer 3: Distributed Tracing

**Objectives**: Track request flows across system components for performance analysis and debugging

#### **Tracing Implementation**

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

class DistributedTracing:
    """OpenTelemetry distributed tracing setup"""
    
    def __init__(self):
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer(__name__)
        
        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name="localhost",
            agent_port=14268,
        )
        
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
    
    @trace.get_tracer(__name__).start_as_current_span("classify_security")
    def classify_security(self, security_id: str) -> ClassificationResult:
        """Trace complete classification workflow"""
        span = trace.get_current_span()
        span.set_attribute("security.id", security_id)
        
        # Trace database lookup
        with tracer.start_as_current_span("database_lookup") as db_span:
            security = self.get_security_by_id(security_id)
            db_span.set_attribute("database.table", "securities_master")
        
        # Trace external API call
        with tracer.start_as_current_span("external_api_call") as api_span:
            classification = self.call_openfigi_api(security.isin)
            api_span.set_attribute("api.service", "OpenFIGI")
            api_span.set_attribute("api.response.status", "success")
        
        return classification
```

#### **Trace Correlation**

```python
class TraceCorrelation:
    """Correlate traces with logs and metrics"""
    
    def correlate_request(self, request_id: str) -> None:
        """Add correlation ID to all observability data"""
        span = trace.get_current_span()
        span.set_attribute("request.id", request_id)
        
        # Add to structured logs
        logger = structlog.get_logger().bind(request_id=request_id, trace_id=span.get_span_context().trace_id)
        
        # Add to metrics labels
        metrics.classification_requests.labels(request_id=request_id).inc()
```

### Layer 4: Health Checks & Service Discovery

**Objectives**: Provide real-time system health status and enable automated recovery

#### **Health Check Framework**

```python
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

class HealthCheckService:
    """Comprehensive health checking for all system components"""
    
    def __init__(self):
        self.app = FastAPI()
        self.setup_health_endpoints()
    
    def setup_health_endpoints(self) -> None:
        """Configure health check endpoints"""
        
        @self.app.get("/health")
        async def basic_health_check():
            """Basic liveness check"""
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
        
        @self.app.get("/health/ready")
        async def readiness_check():
            """Comprehensive readiness check"""
            checks = await self.run_all_health_checks()
            
            if all(check["healthy"] for check in checks.values()):
                return JSONResponse(
                    content={"status": "ready", "checks": checks},
                    status_code=status.HTTP_200_OK
                )
            else:
                return JSONResponse(
                    content={"status": "not_ready", "checks": checks},
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE
                )
        
        @self.app.get("/health/detailed")
        async def detailed_health_check():
            """Detailed health information for debugging"""
            return {
                "database": await self.check_database_health(),
                "external_apis": await self.check_external_api_health(),
                "classification_engine": await self.check_classification_health(),
                "file_system": await self.check_filesystem_health(),
                "memory": await self.check_memory_health()
            }
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check PostgreSQL database health"""
        try:
            # Test database connection
            async with get_db_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                
            # Check connection pool status
            pool_status = await self.get_connection_pool_status()
            
            # Check critical table accessibility
            critical_tables = ["securities_master", "pp_account_transactions"]
            table_checks = {}
            for table in critical_tables:
                table_checks[table] = await self.check_table_health(table)
            
            return {
                "healthy": True,
                "connection": "successful",
                "pool_status": pool_status,
                "tables": table_checks,
                "response_time_ms": 45
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "connection": "failed"
            }
    
    async def check_external_api_health(self) -> Dict[str, Any]:
        """Check external API service health"""
        api_checks = {}
        
        # OpenFIGI API health check
        try:
            response = await self.test_openfigi_connection()
            api_checks["OpenFIGI"] = {
                "healthy": response.status_code == 200,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining")
            }
        except Exception as e:
            api_checks["OpenFIGI"] = {
                "healthy": False,
                "error": str(e)
            }
        
        return api_checks
```

#### **Custom Health Checks**

```python
class CustomHealthChecks:
    """Domain-specific health checks"""
    
    async def check_classification_accuracy(self) -> Dict[str, Any]:
        """Monitor classification accuracy over time"""
        # Get recent classification results
        recent_classifications = await self.get_recent_classifications(hours=24)
        
        # Calculate accuracy metrics
        accuracy_rate = self.calculate_accuracy_rate(recent_classifications)
        
        return {
            "healthy": accuracy_rate > 0.95,
            "accuracy_rate": accuracy_rate,
            "total_classifications": len(recent_classifications),
            "threshold": 0.95
        }
    
    async def check_data_quality(self) -> Dict[str, Any]:
        """Monitor data quality metrics"""
        quality_metrics = await self.calculate_data_quality_metrics()
        
        return {
            "healthy": quality_metrics["overall_score"] > 0.90,
            "overall_score": quality_metrics["overall_score"],
            "completeness": quality_metrics["completeness"],
            "consistency": quality_metrics["consistency"],
            "accuracy": quality_metrics["accuracy"]
        }
```

### Layer 5: Alerting & Notification

**Objectives**: Proactive notification of issues with appropriate escalation and context

#### **Alerting Framework**

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

class AlertSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"  
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class Alert:
    name: str
    severity: AlertSeverity
    description: str
    metrics: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: datetime
    correlation_id: str

class AlertManager:
    """Comprehensive alerting system"""
    
    def __init__(self):
        self.notification_channels = {
            AlertSeverity.CRITICAL: ["email", "slack", "pagerduty"],
            AlertSeverity.HIGH: ["email", "slack"],
            AlertSeverity.MEDIUM: ["slack"],
            AlertSeverity.LOW: ["slack"],
            AlertSeverity.INFO: ["log"]
        }
    
    def create_alert(self, name: str, severity: AlertSeverity, **kwargs) -> Alert:
        """Create standardized alert with context"""
        return Alert(
            name=name,
            severity=severity,
            description=kwargs.get("description", ""),
            metrics=kwargs.get("metrics", {}),
            context=kwargs.get("context", {}),
            timestamp=datetime.utcnow(),
            correlation_id=str(uuid.uuid4())
        )
    
    async def send_alert(self, alert: Alert) -> None:
        """Send alert through appropriate channels"""
        channels = self.notification_channels[alert.severity]
        
        for channel in channels:
            await self.send_to_channel(channel, alert)
```

#### **Alert Definitions**

**System Health Alerts**:

```python
# Critical system alerts
ALERT_DATABASE_DOWN = {
    "name": "database_connection_failed",
    "severity": AlertSeverity.CRITICAL,
    "condition": "database_health_check == false",
    "description": "PostgreSQL database connection failed"
}

ALERT_HIGH_ERROR_RATE = {
    "name": "high_error_rate",
    "severity": AlertSeverity.HIGH,
    "condition": "error_rate > 5% over 5 minutes",
    "description": "Application error rate exceeded threshold"
}
```

**Performance Alerts**:

```python
# Performance degradation alerts
ALERT_SLOW_CLASSIFICATION = {
    "name": "slow_classification_response",
    "severity": AlertSeverity.MEDIUM,
    "condition": "classification_p95_latency > 2s",
    "description": "Classification response time exceeded SLA"
}

ALERT_HIGH_MEMORY_USAGE = {
    "name": "high_memory_usage",
    "severity": AlertSeverity.MEDIUM,
    "condition": "memory_usage > 8GB",
    "description": "Memory usage exceeded operational threshold"
}
```

**Business Logic Alerts**:

```python
# Business metric alerts
ALERT_LOW_CLASSIFICATION_ACCURACY = {
    "name": "classification_accuracy_degraded",
    "severity": AlertSeverity.HIGH,
    "condition": "classification_accuracy < 95% over 1 hour",
    "description": "Classification accuracy below business requirement"
}

ALERT_DATA_QUALITY_ISSUES = {
    "name": "data_quality_degraded", 
    "severity": AlertSeverity.MEDIUM,
    "condition": "data_quality_score < 90%",
    "description": "Data quality metrics below acceptable threshold"
}
```

## Implementation Strategy

### Phase 1: Foundation Monitoring (Week 1-2)

- Set up basic metrics collection with Prometheus
- Implement structured logging framework
- Create basic health check endpoints
- Configure simple alerting for critical failures

### Phase 2: Advanced Observability (Week 3-4)

- Implement distributed tracing with OpenTelemetry  
- Set up comprehensive dashboards with Grafana
- Add business metrics and data quality monitoring
- Configure multi-channel alerting system

### Phase 3: Production Readiness (Week 5-6)

- Performance monitoring and benchmarking
- Security event monitoring and alerting
- Automated incident response workflows
- Monitoring documentation and runbooks

### Phase 4: Continuous Improvement (Ongoing)

- Monitoring optimization based on operational experience
- New metric development for emerging requirements
- Alert tuning to reduce false positives
- Dashboard enhancement and user experience improvements

## Technology Stack

### Core Monitoring Tools

**Metrics Collection & Storage**:

```yaml
# Prometheus configuration for metrics collection
prometheus:
  global:
    scrape_interval: 15s
    evaluation_interval: 15s
  
  rule_files:
    - "security_master_alerts.yml"
    - "performance_alerts.yml"
  
  scrape_configs:
    - job_name: 'security-master'
      static_configs:
        - targets: ['localhost:5050']
      metrics_path: '/metrics'
      scrape_interval: 10s
```

**Visualization & Dashboards**:

```yaml
# Grafana dashboard configuration
grafana:
  datasources:
    - name: Prometheus
      type: prometheus
      url: http://prometheus:9090
      
  dashboards:
    - name: Security Master Overview
      panels:
        - classification_performance
        - database_health
        - api_response_times
        - system_resources
```

**Log Management**:

```yaml
# ELK Stack configuration for log management
elasticsearch:
  cluster.name: security-master-logs
  discovery.type: single-node
  
logstash:
  input:
    beats:
      port: 5044
  
  filter:
    json:
      source: message
      
  output:
    elasticsearch:
      hosts: ["elasticsearch:9200"]
      index: "security-master-%{+YYYY.MM.dd}"

kibana:
  server.host: "0.0.0.0"
  elasticsearch.hosts: ["http://elasticsearch:9200"]
```

### Monitoring Infrastructure

**Container-based Deployment**:

```yaml
# Docker Compose monitoring stack
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      
  grafana:
    image: grafana/grafana:latest  
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=secure_password
      
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
      - "14268:14268"
```

## Monitoring Dashboards

### Executive Dashboard

- System uptime and availability
- Classification accuracy trends  
- User activity and satisfaction metrics
- Cost monitoring for external APIs
- Security incident summary

### Operations Dashboard

- Application performance metrics (response times, throughput)
- Database performance and health
- Infrastructure resource utilization
- Alert status and incident tracking
- Deployment and release metrics

### Development Dashboard

- Application error rates and debugging information
- Performance bottleneck identification
- Code quality metrics and technical debt
- Test coverage and quality metrics
- Development velocity and delivery metrics

### Business Intelligence Dashboard

- Portfolio classification accuracy by asset type
- Data quality trends and improvement metrics
- User adoption and feature usage analytics
- Cost analysis and optimization opportunities
- Compliance and audit trail summaries

## Incident Response Integration

### Automated Response Workflows

```python
class IncidentResponseAutomation:
    """Automated incident response workflows"""
    
    async def handle_database_failure(self, alert: Alert) -> None:
        """Automated response to database connectivity issues"""
        # 1. Attempt database connection recovery
        # 2. Switch to read-only mode if recovery fails  
        # 3. Notify operations team
        # 4. Create incident ticket
        pass
    
    async def handle_performance_degradation(self, alert: Alert) -> None:
        """Automated response to performance issues"""
        # 1. Scale up resources if possible
        # 2. Enable performance mode (disable non-critical features)
        # 3. Increase logging detail for debugging
        # 4. Schedule performance analysis
        pass
```

### Incident Documentation

- Automated incident creation and tracking
- Context preservation with logs, metrics, and traces
- Post-incident analysis and improvement recommendations
- Knowledge base updates with resolution procedures

## Success Criteria

### Monitoring Coverage

- **Application Coverage**: 100% of critical workflows instrumented
- **Infrastructure Coverage**: All system components monitored
- **Business Metrics**: Key performance indicators tracked
- **Security Events**: All authentication and authorization events logged

### Performance Monitoring

- **Response Time Monitoring**: 95% of requests tracked
- **Error Rate Monitoring**: All errors categorized and tracked  
- **Resource Utilization**: CPU, memory, disk, network monitored
- **External Dependencies**: All API calls and responses tracked

### Alerting Effectiveness

- **Mean Time to Detection**: <5 minutes for critical issues
- **False Positive Rate**: <5% for critical alerts
- **Alert Response Time**: <15 minutes for high-severity alerts
- **Incident Resolution**: 90% resolved within SLA timeframes

### Operational Excellence

- **System Uptime**: >99.9% availability
- **Monitoring Uptime**: >99.99% monitoring system availability
- **Documentation Coverage**: All monitoring procedures documented
- **Team Training**: 100% operations team trained on monitoring tools

## Related Decisions

- **ADR-010**: Performance Testing Strategy (performance metrics integration)
- **ADR-006**: Security and Authentication Architecture (security monitoring requirements)
- **ADR-005**: External API Integration Strategy (external service monitoring)
- **ADR-007**: Deployment and Infrastructure Strategy (infrastructure monitoring)

## References

- OpenTelemetry Documentation: <https://opentelemetry.io/docs/>
- Prometheus Monitoring Best Practices
- Grafana Dashboard Design Guidelines
- Site Reliability Engineering (SRE) Monitoring Principles
- NIST Cybersecurity Framework Monitoring Guidelines
