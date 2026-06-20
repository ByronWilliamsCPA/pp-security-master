# ADR-006: Security and Authentication Architecture

**Date**: 2025-08-22  
**Status**: Deferred (accepted in principle; not yet implemented as of 2026-06-19)  
**Deciders**: Byron, Development Team  
**Consulted**: Cloudflare Zero Trust Documentation, FastAPI Security Patterns, Unraid Security Best Practices  
**Informed**: Infrastructure Team, Operations Team  

## Context

The Security Master Service handles sensitive financial data including:

- Complete portfolio holdings and valuations
- Institution transaction data (Wells Fargo, Interactive Brokers, AltoIRA)
- API keys for external services (OpenFIGI, Alpha Vantage)
- Personal financial information across multiple accounts

The system operates in a home lab environment (Unraid) but requires enterprise-grade security controls to protect this sensitive financial data. Key security requirements include:

1. **Authentication**: Secure user access to web UI and CLI tools
2. **Authorization**: Role-based access to different data sets and operations
3. **Data Protection**: Encryption at rest and in transit
4. **API Security**: Secure external API key management
5. **Network Security**: Controlled access to database and services
6. **Audit Logging**: Complete audit trail of all financial data access

## Security Threat Model

### High-Risk Threats

1. **Data Breach**: Unauthorized access to complete financial portfolio data
2. **API Key Compromise**: Theft of external API credentials leading to cost/quota abuse
3. **Transaction Manipulation**: Unauthorized modification of financial transaction data
4. **Lateral Movement**: Compromise leading to access to other Unraid services

### Medium-Risk Threats

1. **Session Hijacking**: Stolen authentication tokens for unauthorized access
2. **Privilege Escalation**: Normal user gaining administrative access
3. **Data Export**: Unauthorized bulk export of financial data
4. **Service Disruption**: Denial of service attacks against the classification service

### Accepted Risks

1. **Physical Access**: Home lab environment assumes physical security
2. **Insider Threats**: Single-user system with trusted physical access
3. **Social Engineering**: Limited external attack surface reduces risk

## Decision

We will implement a **layered security architecture** using Cloudflare Zero Trust for authentication, JWT tokens for session management, and comprehensive encryption for data protection.

### Authentication Architecture

#### **Cloudflare Zero Trust Integration**

```yaml
# Cloudflare Zero Trust Configuration
authentication:
  provider: cloudflare_zero_trust
  domain: "pp-security.your-domain.com"
  application_audience: "pp-security-master"
  session_duration: "8h"
  
access_policies:
  - name: "Admin Access"
    decision: "allow"
    users: ["byron@your-domain.com"]
    applications: ["pp-security-admin"]
    
  - name: "Read-Only Access" 
    decision: "allow"
    users: ["readonly@your-domain.com"]
    applications: ["pp-security-readonly"]
```

#### **JWT Token Management**

```python
class SecurityMasterAuth:
    """Authentication and authorization for Security Master Service"""
    
    def __init__(self):
        self.jwt_secret = os.getenv("JWT_SECRET")  # 256-bit key
        self.cloudflare_audience = os.getenv("CLOUDFLARE_AUDIENCE")
        self.session_timeout = timedelta(hours=8)
    
    async def verify_cloudflare_token(self, cf_token: str) -> UserClaims:
        """Verify Cloudflare Access JWT token"""
        # Verify with Cloudflare public keys
        # Extract user claims and permissions
        pass
    
    def generate_internal_jwt(self, user_claims: UserClaims) -> str:
        """Generate internal JWT for API access"""
        payload = {
            "sub": user_claims.email,
            "role": user_claims.role,
            "permissions": user_claims.permissions,
            "exp": datetime.utcnow() + self.session_timeout
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")
```

### Authorization Framework

#### **Role-Based Access Control (RBAC)**

```python
class SecurityRole(Enum):
    ADMIN = "admin"          # Full access to all data and operations
    ANALYST = "analyst"      # Read access to all data, write access to classifications
    READONLY = "readonly"    # Read-only access to aggregated data only
    
class Permission(Enum):
    # Data access permissions
    READ_TRANSACTIONS = "read:transactions"
    READ_HOLDINGS = "read:holdings"  
    READ_CLASSIFICATIONS = "read:classifications"
    READ_INSTITUTION_DATA = "read:institution_data"
    
    # Write permissions
    WRITE_CLASSIFICATIONS = "write:classifications"
    WRITE_MANUAL_ENTRIES = "write:manual_entries"
    
    # Administrative permissions
    MANAGE_API_KEYS = "manage:api_keys"
    MANAGE_USERS = "manage:users"
    EXPORT_DATA = "export:data"
    
ROLE_PERMISSIONS = {
    SecurityRole.ADMIN: [Permission.READ_TRANSACTIONS, Permission.READ_HOLDINGS, 
                        Permission.READ_CLASSIFICATIONS, Permission.READ_INSTITUTION_DATA,
                        Permission.WRITE_CLASSIFICATIONS, Permission.WRITE_MANUAL_ENTRIES,
                        Permission.MANAGE_API_KEYS, Permission.MANAGE_USERS, Permission.EXPORT_DATA],
    
    SecurityRole.ANALYST: [Permission.READ_TRANSACTIONS, Permission.READ_HOLDINGS,
                          Permission.READ_CLASSIFICATIONS, Permission.WRITE_CLASSIFICATIONS,
                          Permission.WRITE_MANUAL_ENTRIES],
    
    SecurityRole.READONLY: [Permission.READ_HOLDINGS, Permission.READ_CLASSIFICATIONS]
}
```

### Data Protection Strategy

#### **Encryption at Rest**

- **Database Encryption**: PostgreSQL Transparent Data Encryption (TDE) for all tables
- **File Encryption**: GPG encryption for `.env` files and API key storage
- **Backup Encryption**: Encrypted backups using Unraid CA Backup with encryption
- **Key Management**: Hardware security module (HSM) or Unraid encrypted storage

#### **Encryption in Transit**

- **HTTPS Only**: TLS 1.3 for all web traffic via Cloudflare
- **Database Connections**: SSL/TLS for all PostgreSQL connections
- **API Calls**: HTTPS for all external API communications
- **Internal Communication**: mTLS for service-to-service communication

#### **API Key Management**

```python
class APIKeyManager:
    """Secure management of external API keys"""
    
    def __init__(self):
        self.encryption_key = self.load_master_key()
        self.key_rotation_interval = timedelta(days=90)
    
    def store_api_key(self, service: str, api_key: str) -> None:
        """Store encrypted API key in database"""
        encrypted_key = self.encrypt_key(api_key)
        # Store with rotation schedule and usage tracking
        pass
    
    def get_api_key(self, service: str) -> str:
        """Retrieve and decrypt API key"""
        encrypted_key = self.retrieve_encrypted_key(service)
        return self.decrypt_key(encrypted_key)
    
    def rotate_api_key(self, service: str, new_key: str) -> None:
        """Rotate API key with zero-downtime transition"""
        # Gradual transition from old to new key
        pass
```

### Network Security Architecture

#### **Network Segmentation**

```yaml
# Unraid Network Configuration
networks:
  security_master_net:
    subnet: "172.20.0.0/24"
    gateway: "172.20.0.1"
    
  database_net:
    subnet: "172.21.0.0/24"
    gateway: "172.21.0.1"
    isolated: true  # Database access only

services:
  pp-security-api:
    networks: 
      - security_master_net
    ports:
      - "5050:5050"  # HTTPS only via Cloudflare
      
  postgresql:
    networks:
      - database_net
    ports: []  # No external ports
```

#### **Firewall Rules**

- **Inbound**: Only HTTPS (443) via Cloudflare tunnel
- **Database**: PostgreSQL access only from application containers
- **Outbound**: Restricted to required external APIs (OpenFIGI, Alpha Vantage)
- **Monitoring**: Dedicated monitoring network with read-only access

### Audit Logging Framework

#### **Comprehensive Audit Trail**

```python
class SecurityAuditLogger:
    """Comprehensive audit logging for all security events"""
    
    def __init__(self):
        self.audit_table = "security_audit_log"
        self.retention_period = timedelta(days=2555)  # 7 years
    
    def log_authentication(self, user_id: str, success: bool, source_ip: str) -> None:
        """Log authentication attempts"""
        self.log_event("authentication", {
            "user_id": user_id,
            "success": success,
            "source_ip": source_ip,
            "timestamp": datetime.utcnow(),
            "user_agent": request.headers.get("User-Agent")
        })
    
    def log_data_access(self, user_id: str, resource: str, action: str) -> None:
        """Log all data access operations"""
        self.log_event("data_access", {
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "timestamp": datetime.utcnow(),
            "session_id": current_session.id
        })
    
    def log_classification_change(self, user_id: str, security_id: str, 
                                 old_classification: str, new_classification: str) -> None:
        """Log all classification modifications"""
        self.log_event("classification_change", {
            "user_id": user_id,
            "security_id": security_id,
            "old_classification": old_classification,
            "new_classification": new_classification,
            "timestamp": datetime.utcnow(),
            "rationale": request.json.get("rationale")
        })
```

## Implementation Strategy

### Phase 1: Foundation Security (MVP)

- **Basic Authentication**: Simple JWT tokens for CLI access
- **Database Security**: PostgreSQL user accounts with limited permissions
- **API Key Storage**: Encrypted `.env` files with GPG
- **Basic Logging**: Database audit trail for all modifications

### Phase 2: Enterprise Security (Release 2.0)

- **Cloudflare Zero Trust**: Full web UI authentication via Cloudflare
- **RBAC Implementation**: Role-based access control with granular permissions
- **Advanced Encryption**: TDE for database, mTLS for service communication
- **Security Monitoring**: Real-time security event detection and alerting

### Phase 3: Advanced Security (Release 3.0)

- **Multi-Factor Authentication**: Hardware token support via Cloudflare
- **Behavioral Analysis**: Anomaly detection for unusual access patterns
- **Key Rotation**: Automated API key rotation with zero downtime
- **Compliance Reporting**: SOX/PCI compliance audit reporting

## Security Configuration

### Environment Security

```bash
# .env.example (encrypted with GPG in production)
# Database credentials
DB_PASSWORD="$(openssl rand -base64 32)"
JWT_SECRET="$(openssl rand -base64 64)"

# API keys (encrypted)
OPENFIGI_API_KEY="encrypted:$(gpg --encrypt --armor api_key)"
ALPHA_VANTAGE_KEY="encrypted:$(gpg --encrypt --armor api_key)"

# Cloudflare Zero Trust
CLOUDFLARE_AUDIENCE="your-app-audience-tag"
CLOUDFLARE_DOMAIN="pp-security.your-domain.com"

# Security settings
SESSION_TIMEOUT="28800"  # 8 hours
PASSWORD_MIN_LENGTH="16"
REQUIRE_MFA="true"
```

### Database Security Hardening

```sql
-- Create limited database users
CREATE ROLE pp_app_readonly WITH LOGIN PASSWORD 'strong_password';
CREATE ROLE pp_app_readwrite WITH LOGIN PASSWORD 'strong_password';

-- Grant minimal required permissions
GRANT CONNECT ON DATABASE pp_security_master TO pp_app_readonly;
GRANT USAGE ON SCHEMA public TO pp_app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pp_app_readonly;

GRANT CONNECT ON DATABASE pp_security_master TO pp_app_readwrite;
GRANT USAGE ON SCHEMA public TO pp_app_readwrite;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO pp_app_readwrite;

-- Enable row-level security
ALTER TABLE securities_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE pp_account_transactions ENABLE ROW LEVEL SECURITY;

-- Create policies for data isolation
CREATE POLICY user_data_access ON securities_master
    FOR ALL TO pp_app_readwrite
    USING (created_by = current_user OR current_user = 'pp_admin');
```

## Security Monitoring and Alerting

### Real-Time Security Monitoring

- **Failed Authentication**: >3 failed attempts in 15 minutes
- **Unusual Data Access**: Access patterns outside normal hours
- **Large Data Export**: Bulk export operations
- **API Key Usage Anomalies**: Unusual external API usage patterns

### Security Metrics and KPIs

- **Authentication Success Rate**: >99.5% for legitimate users
- **Mean Time to Detection**: <5 minutes for security incidents
- **False Positive Rate**: <2% for security alerts
- **Compliance Score**: 100% for defined security controls

## Risk Mitigation

### Data Protection Risks

- **Database Compromise**: Multiple layers of encryption and access controls
- **API Key Theft**: Encrypted storage, rotation, and usage monitoring
- **Session Hijacking**: Short session timeouts and secure token handling
- **Privilege Escalation**: Principle of least privilege and audit logging

### Operational Security Risks

- **Service Disruption**: Rate limiting and DDoS protection via Cloudflare
- **Insider Threats**: Comprehensive audit logging and access monitoring
- **Configuration Drift**: Infrastructure as code and automated security scanning
- **Backup Security**: Encrypted backups with offsite storage

## Consequences

### Positive

- **Enterprise-Grade Security**: Comprehensive protection for sensitive financial data
- **Compliance Ready**: Audit trail and controls support regulatory requirements
- **Scalable Authentication**: Cloudflare Zero Trust scales with organizational growth
- **Defense in Depth**: Multiple security layers protect against various attack vectors

### Negative

- **Implementation Complexity**: Security features add development and operational complexity
- **Performance Impact**: Encryption and authentication add computational overhead
- **User Experience**: Security controls may impact user workflow efficiency
- **Operational Overhead**: Security monitoring and key management require ongoing attention

### Risk Mitigation

- **Phased Implementation**: Gradual security enhancement reduces complexity
- **Performance Optimization**: Efficient algorithms and caching minimize overhead
- **User Training**: Clear documentation and training improve user experience
- **Automation**: Automated security operations reduce manual overhead

## Related Decisions

- **ADR-005**: External API Integration Strategy (API key management requirements)
- **ADR-007**: Deployment and Infrastructure Strategy (network security architecture)
- **ADR-004**: Data Quality and Validation Framework (audit logging requirements)

## References

- Cloudflare Zero Trust Documentation: <https://developers.cloudflare.com/cloudflare-one/>
- OWASP Web Application Security Testing Guide
- PostgreSQL Security Best Practices
- JWT Security Best Current Practices (RFC 8725)
- NIST Cybersecurity Framework
