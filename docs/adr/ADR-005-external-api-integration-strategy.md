# ADR-005: External API Integration Strategy

**Date**: 2025-08-22  
**Status**: Deferred (accepted in principle; not yet implemented as of 2026-06-19)  
**Deciders**: Byron, Development Team  
**Consulted**: OpenFIGI API Documentation, Alpha Vantage Rate Limits, Securities Classification Requirements  
**Informed**: Data Quality Team, Infrastructure Team  

## Context

The Securities Master Service requires external API integrations to provide comprehensive security classification beyond what Portfolio Performance native sources and pp-portfolio-classifier can provide. The primary external APIs identified are:

1. **OpenFIGI API** (Bloomberg) - Equity and bond identification and classification
2. **Alpha Vantage API** - Fundamental data and company profiles  
3. **Financial Modeling Prep API** - Company profiles, financial ratios, ESG data

Each API has different cost models, rate limits, reliability characteristics, and data quality levels. We need a unified strategy that maximizes data quality while managing costs and ensuring system reliability.

## Key Challenges

### Rate Limiting and Cost Management

- **OpenFIGI**: Free tier with 250 requests/hour, paid tiers up to 10,000 requests/hour
- **Alpha Vantage**: Free tier with 25 requests/day, paid tiers up to 1,200 requests/minute
- **Financial Modeling Prep**: Free tier with 250 requests/day, paid tiers up to 10,000 requests/hour

### Data Quality and Reliability

- **API Availability**: External dependencies may experience outages
- **Data Consistency**: Different APIs may provide conflicting classifications
- **Response Time**: External API calls add latency to classification processes
- **Error Handling**: Need robust fallback strategies for API failures

### Classification Accuracy

- **GICS Code Variations**: Different APIs may use different GICS versions
- **Data Freshness**: API data may be stale for recently listed securities
- **Coverage Gaps**: Some securities may not be available in external APIs

## Decision

We will implement a **unified external API integration framework** with intelligent caching, rate limiting, error handling, and cost optimization strategies.

### API Integration Architecture

#### **Tier 3 API Framework Design**

```python
class ExternalAPIManager:
    """Unified manager for all external API integrations"""
    
    def __init__(self):
        self.apis = {
            'openfigi': OpenFIGIClient(),
            'alpha_vantage': AlphaVantageClient(), 
            'financial_modeling_prep': FMPClient()
        }
        self.cache = APIResponseCache()
        self.rate_limiter = APIRateLimiter()
        self.circuit_breaker = APICircuitBreaker()
    
    async def classify_security(self, security_identifier: str) -> ClassificationResult:
        """Classify security using available APIs with fallback logic"""
        for api_name in self.get_api_priority_order():
            if not self.rate_limiter.can_request(api_name):
                continue
                
            cached_result = self.cache.get(api_name, security_identifier)
            if cached_result and not cached_result.is_stale():
                return cached_result
                
            try:
                result = await self.apis[api_name].classify(security_identifier)
                self.cache.store(api_name, security_identifier, result)
                return result
            except APIException as e:
                self.circuit_breaker.record_failure(api_name)
                continue
        
        return self.queue_for_manual_classification(security_identifier)
```

### Rate Limiting Strategy

#### **Intelligent Request Management**

- **Request Prioritization**: High-value securities (by portfolio weight) get priority
- **Batch Processing**: Group requests to maximize API efficiency
- **Time-Based Scheduling**: Spread requests across hours/days to stay within limits
- **Adaptive Throttling**: Dynamically adjust request rates based on API response times

#### **Cost Optimization**

```python
class APIRateLimiter:
    """Cost-aware rate limiting with priority queues"""
    
    def __init__(self):
        self.api_quotas = {
            'openfigi': {'free': 250, 'paid': 10000, 'window': 3600},
            'alpha_vantage': {'free': 25, 'paid': 1200, 'window': 86400},
            'financial_modeling_prep': {'free': 250, 'paid': 10000, 'window': 86400}
        }
        self.priority_queue = PriorityQueue()
        
    def calculate_request_priority(self, security: Security) -> float:
        """Calculate priority based on portfolio weight and data quality needs"""
        portfolio_weight = security.get_total_portfolio_weight()
        data_age = security.get_classification_age_days()
        confidence_score = security.get_current_confidence_score()
        
        # Higher priority for high-weight holdings with old/low-confidence data
        return portfolio_weight * (1.0 - confidence_score) * min(data_age / 30, 1.0)
```

### Caching Strategy

#### **Multi-Level Caching Architecture**

1. **In-Memory Cache**: Redis for frequently accessed classifications (1-hour TTL)
2. **Database Cache**: PostgreSQL for long-term storage (90-day TTL)
3. **File Cache**: Local JSON files for offline fallback (1-year retention)

#### **Cache Invalidation Rules**

- **Time-Based**: Automatic expiration based on data type
  - Price data: 1 hour
  - Basic classification: 30 days  
  - Fundamental data: 90 days
- **Event-Based**: Corporate actions, ticker changes, GICS reclassifications
- **Quality-Based**: Low confidence scores trigger faster refresh

### Error Handling and Resilience

#### **Circuit Breaker Pattern**

```python
class APICircuitBreaker:
    """Circuit breaker for API fault tolerance"""
    
    def __init__(self):
        self.failure_thresholds = {
            'openfigi': {'failures': 5, 'window': 300},      # 5 failures in 5 minutes
            'alpha_vantage': {'failures': 3, 'window': 600}, # 3 failures in 10 minutes
            'financial_modeling_prep': {'failures': 5, 'window': 300}
        }
        self.recovery_timeout = 900  # 15 minutes before retry
    
    def is_circuit_open(self, api_name: str) -> bool:
        """Check if circuit breaker is open for given API"""
        pass
        
    def record_failure(self, api_name: str, error: Exception) -> None:
        """Record API failure and potentially open circuit"""
        pass
```

#### **Graceful Degradation**

- **API Fallback Chain**: OpenFIGI → Alpha Vantage → Financial Modeling Prep → Manual Queue
- **Partial Results**: Accept incomplete data with confidence scoring
- **Offline Mode**: Use cached data when all APIs are unavailable
- **Manual Override**: Always allow manual classification to override API results

### Data Quality Validation

#### **Cross-API Validation**

- **Consistency Checking**: Compare GICS codes across multiple APIs
- **Confidence Scoring**: Weight results based on API reliability and agreement
- **Outlier Detection**: Flag unusual classifications for manual review
- **Data Freshness**: Prefer more recent data when APIs disagree

#### **API Response Validation**

```python
class APIResponseValidator:
    """Validate and normalize API responses"""
    
    def validate_openfigi_response(self, response: Dict) -> ValidationResult:
        """Validate OpenFIGI API response structure and data quality"""
        required_fields = ['figi', 'name', 'exchCode', 'securityType']
        optional_fields = ['gicsSubIndustry', 'industry', 'sector']
        
        validation = ValidationResult()
        
        # Check required fields
        for field in required_fields:
            if field not in response or not response[field]:
                validation.add_error(f"Missing required field: {field}")
        
        # Validate GICS codes
        if 'gicsSubIndustry' in response:
            if not self.is_valid_gics_code(response['gicsSubIndustry']):
                validation.add_warning(f"Invalid GICS code: {response['gicsSubIndustry']}")
        
        return validation
```

## Implementation Strategy

### Phase 1: Foundation (MVP Timeframe)

- **Basic API Integration**: OpenFIGI only with simple rate limiting
- **Basic Caching**: Database-only cache with 30-day TTL
- **Error Handling**: Simple try/catch with manual fallback
- **Cost Control**: Free tier usage only with daily request limits

### Phase 2: Enhanced Integration (Release 2.0)

- **Multi-API Support**: Add Alpha Vantage and Financial Modeling Prep
- **Advanced Caching**: Redis + database + file cache layers
- **Circuit Breaker**: Full fault tolerance with automatic recovery
- **Priority Queuing**: Request prioritization based on portfolio weight

### Phase 3: Advanced Optimization (Release 3.0)

- **Machine Learning**: Predict best API for each security type
- **Cost Optimization**: Dynamic tier management based on usage patterns
- **Real-Time Sync**: Event-driven cache invalidation
- **Custom Algorithms**: Hybrid classification using multiple API sources

## Configuration Management

### API Key Management

- **Environment Variables**: Store API keys in `.env` files (encrypted with GPG)
- **Key Rotation**: Support for multiple keys per API with automatic rotation
- **Usage Monitoring**: Track API key usage against quotas
- **Cost Alerts**: Automated alerts when approaching paid tier thresholds

### Rate Limit Configuration

```yaml
# config/api_limits.yaml
apis:
  openfigi:
    tier: free
    requests_per_hour: 250
    burst_limit: 10
    priority_weight: 1.0
    
  alpha_vantage:
    tier: free  
    requests_per_day: 25
    burst_limit: 5
    priority_weight: 0.8
    
  financial_modeling_prep:
    tier: free
    requests_per_day: 250
    burst_limit: 10
    priority_weight: 0.6
```

## Cost Management Strategy

### Budget Allocation

- **Monthly Budget**: $200-400 for external API costs
- **Tier Strategy**: Start with free tiers, upgrade based on classification volume
- **Cost Monitoring**: Daily usage tracking with automated alerts
- **ROI Analysis**: Track cost per successful classification

### Usage Optimization

- **Request Deduplication**: Avoid duplicate requests for same security
- **Batch Operations**: Group requests when APIs support batch endpoints
- **Smart Scheduling**: Distribute requests across time windows
- **Portfolio Weighting**: Prioritize high-value holdings for paid API usage

## Success Metrics

### API Performance Targets

- **Response Time**: <5 seconds average for individual classifications
- **Success Rate**: >95% successful API responses (excluding rate limits)
- **Cache Hit Rate**: >80% for repeated security lookups
- **Cost Efficiency**: <$0.50 per successful equity classification

### Data Quality Targets  

- **Classification Accuracy**: >92% accuracy for Tier 3 API classifications
- **Coverage Completeness**: >95% of public securities classified within 48 hours
- **Data Freshness**: <7 days average age for fundamental data
- **Consistency Score**: <2% classification discrepancies between APIs

### Operational Targets

- **Uptime**: 99.5% API integration availability
- **Error Recovery**: <15 minutes average recovery time from API failures
- **Manual Fallback**: <5% of securities require manual classification
- **Cost Control**: Stay within monthly budget 95% of the time

## Risk Mitigation

### API Dependency Risks

- **Vendor Lock-in**: Support multiple APIs to avoid single vendor dependency
- **Rate Limit Exhaustion**: Intelligent queuing and priority management
- **API Changes**: Version management and backward compatibility
- **Cost Overruns**: Automated spending limits and usage alerts

### Data Quality Risks

- **Stale Data**: Regular refresh cycles and event-driven updates
- **Inconsistent Classifications**: Cross-validation and confidence scoring
- **API Errors**: Comprehensive validation and fallback strategies
- **Manual Review**: Expert validation for high-value or unusual securities

## Consequences

### Positive

- **Comprehensive Coverage**: Access to institutional-grade classification data
- **Cost Control**: Intelligent usage management keeps costs predictable
- **Reliability**: Fault-tolerant design ensures high availability
- **Scalability**: Framework supports adding new APIs as needed
- **Data Quality**: Multi-source validation improves classification accuracy

### Negative

- **Complexity**: Multiple API integrations increase system complexity
- **External Dependencies**: Reliance on external services for critical functionality
- **Cost Management**: Ongoing monitoring required to control API costs
- **Rate Limiting**: API quotas may constrain classification throughput

### Risk Mitigation

- **Circuit Breakers**: Prevent cascade failures from API outages
- **Comprehensive Caching**: Reduce external dependencies through intelligent caching
- **Cost Alerts**: Automated monitoring prevents unexpected charges
- **Manual Fallback**: Always maintain manual classification capability

## Related Decisions

- **ADR-003**: Securities Master Data Sourcing Hierarchy (defines Tier 3 positioning)
- **ADR-004**: Data Quality and Validation Framework (provides validation requirements)
- **ADR-007**: Deployment and Infrastructure Strategy (infrastructure requirements)

## References

- OpenFIGI API Documentation: <https://www.openfigi.com/api>
- Alpha Vantage API Documentation: <https://www.alphavantage.co/documentation/>
- Financial Modeling Prep API: <https://financialmodelingprep.com/developer/docs>
- Bloomberg API Rate Limiting Best Practices
- GICS Sector Classification Standards
