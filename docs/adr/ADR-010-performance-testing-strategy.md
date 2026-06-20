# ADR-010: Performance Testing Strategy

**Date**: 2025-08-23  
**Status**: Accepted  
**Deciders**: Byron, Development Team  
**Consulted**: Database Performance Team, Production Operations  
**Informed**: QA Team, Executive Stakeholders  

## Context

The Security Master Service handles large volumes of financial data including:

- High-frequency transaction processing from multiple institutions
- Real-time security classification with external API calls
- Complex analytics calculations on portfolio datasets
- Large-scale Portfolio Performance XML import/export operations

Performance requirements identified from project planning review:

- **Classification API Response**: <2s p95 for classification requests
- **Large Portfolio Processing**: Complete backup for 10,000+ transactions within 30 seconds  
- **Migration Performance**: Migration completes within 2 hours for large portfolios
- **Concurrent User Support**: Support multiple simultaneous classification operations

Without comprehensive performance testing, the system risks:

- Poor user experience with slow classification responses
- System failures under production load
- Scalability limitations as portfolio sizes grow
- Database performance degradation over time

## Decision

We will implement a **comprehensive, multi-layered performance testing strategy** that validates system performance at unit, integration, and system levels throughout the development lifecycle.

### Performance Testing Architecture

#### **Four-Tier Testing Strategy**

```python
Unit Performance Tests    → Individual function/class performance
Component Performance     → Database operations, API calls, file processing  
Integration Performance   → End-to-end workflow performance
Load/Stress Testing      → System behavior under production-like conditions
```

#### **Performance Testing Tools & Framework**

```python
# Core Performance Testing Framework
class PerformanceTestSuite:
    """Comprehensive performance testing for Security Master Service"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.load_generator = LoadGenerator()
        self.database_profiler = DatabaseProfiler()
    
    def run_classification_performance_test(self, securities_count: int) -> PerformanceReport:
        """Test classification engine performance with varying loads"""
        pass
    
    def run_database_performance_test(self, transaction_count: int) -> DatabaseReport:
        """Test database performance with large transaction datasets"""
        pass
    
    def run_api_performance_test(self, concurrent_requests: int) -> APIReport:
        """Test external API integration performance under load"""
        pass
```

## Performance Testing Strategy

### Tier 1: Unit Performance Testing

**Objectives**: Validate individual component performance and identify bottlenecks

#### **Critical Components for Unit Performance Testing**

1. **Classification Engine Components**

   ```python
   class ClassificationPerformanceTests:
       @performance_test(max_duration=0.5, memory_limit="100MB")
       def test_fund_classification_performance(self):
           # Test individual fund classification speed
           pass
       
       @performance_test(max_duration=0.2, memory_limit="50MB")  
       def test_equity_classification_performance(self):
           # Test individual equity classification speed
           pass
   ```

2. **Database Operation Performance**

   ```python
   class DatabasePerformanceTests:
       @performance_test(max_duration=1.0)
       def test_bulk_transaction_insert(self):
           # Test bulk transaction insertion performance
           pass
       
       @performance_test(max_duration=2.0)
       def test_portfolio_aggregation_query(self):
           # Test complex portfolio aggregation performance
           pass
   ```

3. **File Processing Performance**

   ```python
   class FileProcessingPerformanceTests:
       @performance_test(max_duration=30.0)
       def test_large_csv_processing(self):
           # Test processing of large broker CSV files
           pass
       
       @performance_test(max_duration=60.0)
       def test_pp_xml_parsing(self):
           # Test Portfolio Performance XML parsing speed
           pass
   ```

#### **Performance Test Markers**

```python
# Custom pytest markers for performance testing
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.benchmark
```

### Tier 2: Component Performance Testing

**Objectives**: Test component interactions and validate system boundaries

#### **Database Component Testing**

```python
class DatabaseComponentPerformanceTests:
    def test_concurrent_classification_updates(self):
        """Test database performance with concurrent classification updates"""
        # Simulate multiple classification workers updating securities
        # Measure lock contention and query performance
        # Validate connection pool efficiency
        pass
    
    def test_large_dataset_queries(self):
        """Test query performance with production-sized datasets"""
        # Generate 50,000+ securities, 100,000+ transactions
        # Test complex joins and aggregations
        # Measure memory usage and execution time
        pass
```

#### **External API Integration Testing**

```python
class APIComponentPerformanceTests:
    def test_openfigi_rate_limiting(self):
        """Test OpenFIGI API performance with rate limiting"""
        # Test circuit breaker functionality
        # Measure retry logic performance
        # Validate caching effectiveness
        pass
    
    def test_concurrent_api_calls(self):
        """Test concurrent external API call performance"""
        # Simulate multiple classification requests
        # Measure API response times and error rates
        # Test connection pool management
        pass
```

### Tier 3: Integration Performance Testing

**Objectives**: Validate end-to-end workflow performance under realistic conditions

#### **End-to-End Performance Scenarios**

1. **Broker File Import Performance**

   ```python
   def test_wells_fargo_import_performance(self):
       """Test complete Wells Fargo CSV import workflow"""
       # Import 10,000 transaction CSV file
       # Measure parsing, validation, database insertion
       # Target: <5 minutes for 10,000 transactions
       pass
   
   def test_ibkr_flex_import_performance(self):
       """Test Interactive Brokers Flex Query import"""
       # Process complex derivatives and options data
       # Measure XML parsing and transformation performance
       # Target: <10 minutes for complex portfolio
       pass
   ```

2. **Classification Pipeline Performance**

   ```python
   def test_full_classification_pipeline(self):
       """Test complete classification workflow performance"""
       # Process 1,000 unclassified securities
       # Measure Tier 1-4 classification performance
       # Target: <30 minutes for 1,000 securities
       pass
   ```

3. **Portfolio Performance Export**

   ```python
   def test_pp_xml_export_performance(self):
       """Test Portfolio Performance XML generation"""
       # Generate complete PP XML for large portfolio
       # Measure query execution and XML serialization
       # Target: <30 seconds for 10,000+ transactions
       pass
   ```

### Tier 4: Load & Stress Testing

**Objectives**: Validate system behavior under production load and beyond

#### **Load Testing Scenarios**

```python
class LoadTestingFramework:
    def __init__(self):
        self.locust_config = {
            'users': 10,  # Concurrent users
            'spawn_rate': 2,  # Users per second
            'host': 'https://pp-security.local:5050'
        }
    
    def classification_load_test(self):
        """Load test classification API endpoints"""
        # 10 concurrent users submitting classification requests
        # Sustain load for 30 minutes
        # Measure response times, error rates, throughput
        pass
    
    def database_load_test(self):
        """Load test database under concurrent operations"""
        # Multiple concurrent imports, exports, classifications
        # Monitor connection pool utilization
        # Measure query performance degradation
        pass
```

#### **Stress Testing Scenarios**

1. **Database Stress Testing**

   ```bash
   # PostgreSQL stress testing with pgbench
   pgbench -c 20 -j 4 -T 300 pp_security_master
   
   # Custom stress test with realistic workload
   uv run python -m tests.performance.database_stress_test \
       --concurrent-workers 20 \
       --test-duration 1800 \
       --transaction-rate 100
   ```

2. **Memory Stress Testing**

   ```python
   def test_large_portfolio_memory_usage(self):
       """Test memory usage with very large portfolios"""
       # Load portfolio with 100,000+ transactions
       # Monitor memory usage during processing
       # Validate memory cleanup after operations
       pass
   ```

3. **API Rate Limit Stress Testing**

   ```python
   def test_api_rate_limit_handling(self):
       """Test system behavior when hitting API rate limits"""
       # Overwhelm OpenFIGI API rate limits
       # Validate circuit breaker functionality
       # Test graceful degradation and recovery
       pass
   ```

## Performance Benchmarking

### Baseline Performance Metrics

**Database Performance Baselines**:

```sql
-- Query performance benchmarks
-- Simple security lookup: <10ms
-- Complex portfolio aggregation: <500ms  
-- Bulk transaction insert (1000 records): <2s
-- Full portfolio export query: <5s
```

**API Performance Baselines**:

- OpenFIGI classification request: <3s average, <10s p99
- Internal classification API: <2s p95, <5s p99
- Portfolio analytics calculation: <30s for complex metrics

**System Resource Baselines**:

- Memory usage: <4GB for typical operations, <8GB for large imports
- CPU utilization: <50% during normal operations, <80% during imports
- Database connections: <20 concurrent connections typical

### Performance Monitoring & Alerting

```python
class PerformanceMonitor:
    """Real-time performance monitoring and alerting"""
    
    def __init__(self):
        self.metrics = {
            'classification_response_time': Histogram(),
            'database_query_duration': Histogram(), 
            'memory_usage': Gauge(),
            'active_connections': Gauge()
        }
    
    def check_performance_thresholds(self):
        """Monitor performance against defined thresholds"""
        # Alert if classification p95 > 2s
        # Alert if database connections > 50
        # Alert if memory usage > 8GB
        pass
```

## Implementation Strategy

### Phase 1: Foundation (Week 1-2)

- Set up performance testing framework and tooling
- Implement basic unit performance tests
- Establish baseline metrics collection

### Phase 2: Component Testing (Week 3-5)  

- Database performance testing with realistic datasets
- External API performance testing with mocking
- File processing performance validation

### Phase 3: Integration Testing (Week 6-7)

- End-to-end workflow performance testing
- Cross-component performance validation
- Performance regression testing setup

### Phase 4: Load Testing (Week 8-9)

- Production-like load testing setup
- Stress testing implementation
- Performance monitoring and alerting

### Continuous Performance Testing

**Development Integration**:

```yaml
# GitHub Actions performance testing workflow
name: Performance Tests
on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily performance tests

jobs:
  performance_tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run Unit Performance Tests
        run: uv run pytest -m "performance and not slow"
      
      - name: Run Component Performance Tests  
        run: uv run pytest -m "performance and component"
        
      - name: Performance Regression Check
        run: uv run python scripts/performance_regression_check.py
```

**Production Monitoring**:

- Real-time performance metrics collection
- Automated performance threshold alerting
- Weekly performance report generation
- Monthly performance optimization reviews

## Performance Optimization Strategies

### Database Optimization

1. **Query Optimization**
   - Index optimization for frequently queried columns
   - Query plan analysis and optimization
   - Materialized views for complex aggregations
   - Connection pooling optimization

2. **Schema Optimization**
   - Table partitioning for large time-series data
   - Denormalization for read-heavy operations  
   - Archive strategy for historical data

### Application Performance

1. **Caching Strategy**
   - Redis caching for classification results
   - Application-level caching for computed metrics
   - HTTP response caching for static data

2. **Async Processing**
   - Background job processing for heavy operations
   - Async/await for I/O bound operations
   - Queue management for batch processing

### Infrastructure Optimization

1. **Resource Allocation**
   - Memory allocation tuning
   - CPU resource optimization
   - Storage I/O optimization

2. **Scaling Strategy**  
   - Horizontal scaling preparation
   - Load balancing configuration
   - Auto-scaling trigger configuration

## Success Criteria

### Performance Requirements Validation

1. **Response Time Requirements**
   - Classification API: 95% of requests < 2s
   - Database queries: 95% of queries < 500ms  
   - Portfolio export: Complete in <30s for 10,000 transactions

2. **Throughput Requirements**
   - Support 50 concurrent classification requests
   - Process 1,000 transactions/minute during imports
   - Handle 10 concurrent portfolio exports

3. **Resource Utilization**
   - Memory usage <8GB under load
   - CPU utilization <80% under normal load
   - Database connection pool <50% utilized

4. **Reliability Under Load**
   - 99.9% success rate during load testing
   - Graceful degradation under stress conditions
   - Complete recovery within 5 minutes after stress

## Risk Mitigation

### Performance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Database performance degradation | Medium | High | Query optimization, indexing strategy, monitoring |
| External API rate limiting | High | Medium | Caching, circuit breakers, fallback strategies |
| Memory leaks in long-running operations | Medium | Medium | Memory profiling, garbage collection tuning |
| Poor performance with large datasets | High | High | Pagination, streaming, background processing |

### Testing Environment Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Insufficient test data volume | Medium | High | Synthetic data generation, production data sampling |
| Test environment differs from production | High | Medium | Production-like testing environment, infrastructure as code |
| Performance test maintenance overhead | Medium | Medium | Automated test generation, CI/CD integration |

## Monitoring & Reporting

### Performance Metrics Dashboard

**Real-time Metrics**:

- Current response times (p50, p95, p99)
- Active database connections
- Memory and CPU utilization  
- API call success rates and latencies

**Historical Analysis**:

- Performance trend analysis over time
- Regression detection and alerting
- Capacity planning projections
- Performance optimization impact measurement

### Performance Reporting

**Weekly Performance Reports**:

- Performance SLA compliance summary
- Performance degradation incidents
- Optimization opportunities identified
- Resource utilization trends

**Monthly Performance Reviews**:

- Performance goal achievement assessment
- System capacity planning analysis  
- Performance optimization project planning
- Performance testing strategy refinements

## Related Decisions

- **ADR-001**: Transaction-Centric Architecture (performance implications)
- **ADR-002**: Portfolio Performance Backup Restoration (export performance requirements)
- **ADR-005**: External API Integration Strategy (API performance considerations)
- **ADR-011**: Production Monitoring Architecture (performance monitoring integration)

## References

- PostgreSQL Performance Monitoring Best Practices
- Python Application Performance Testing with pytest-benchmark
- Locust Load Testing Framework Documentation  
- APM (Application Performance Monitoring) Best Practices
- Database Performance Tuning Guidelines
