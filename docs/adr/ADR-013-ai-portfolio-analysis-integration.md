# ADR-013: AI-Based Portfolio Analysis Integration

## Status

Deferred (proposed; downstream of the MVP, not yet implemented as of 2026-06-19)

This AI/LLM integration is downstream of the MVP (XML round-trip and broker ingestion) and will be reconsidered once that core is built and tested.

## Context

The PromptCraft project is an internal initiative to build a suite of LLM-based applications with specialized agents for various business functions. One of the key agents will be focused on portfolio and investment analysis. To enable this, the Security-Master service must provide a secure and efficient way for the AI agent to access portfolio data, reports, and analytics in a format that is optimized for LLM consumption. This will allow the agent to perform in-depth analysis, generate insights, and provide valuable feedback to portfolio managers.

## Decision

We will implement a dedicated data access layer specifically for AI and LLM-based integrations. This layer will expose curated, well-structured data and reports through a secure API. The key components of this solution are:

### 1. LLM-Optimized Data Formats

- **JSON-based Schemas**: Define clear, well-documented JSON schemas for all data entities (e.g., securities, transactions, positions, portfolio metrics).
- **Structured Text Reports**: Generate human-readable but structured text reports (e.g., Markdown) for complex analytics, making them easily parsable by LLMs.
- **Token-Efficient Payloads**: Design data payloads to be as concise as possible to minimize token consumption and improve API response times.

### 2. Secure API Endpoints

- **Read-Only Access**: The initial API will be strictly read-only to prevent any accidental or malicious data modification.
- **Authentication and Authorization**: Implement robust authentication (e.g., API keys, OAuth2) and authorization mechanisms to ensure that only the designated AI agent can access the data.
- **Rate Limiting and Throttling**: Protect the API from abuse and ensure fair usage by implementing rate limiting and throttling.

### 3. Data Transformation and Caching

- **ETL for AI**: Create a dedicated ETL (Extract, Transform, Load) process to convert raw portfolio data into the LLM-optimized formats.
- **Caching Layer**: Implement a caching layer (e.g., Redis) to store frequently accessed data and reports, reducing the load on the primary database and improving API performance.

### 4. Extensible Framework

- **Modular Design**: Design the data access layer in a modular way to easily add new data entities, reports, and API endpoints as the AI agent's capabilities evolve.
- **Versioning**: Implement API versioning to ensure backward compatibility and allow for future changes without breaking existing integrations.

## Implementation Strategy

### Technical Architecture

```text
src/security_master/llm_integration/
├── api/                # FastAPI application for the LLM API
│   ├── endpoints/      # API endpoints for different data entities
│   └── security.py     # Authentication and authorization logic
├── schemas/            # Pydantic models for the LLM-optimized data formats
├── services/           # Business logic for data transformation and caching
└── etl/                # ETL scripts to prepare data for the API
```

### Database Schema Extensions

- No immediate changes to the core database schema are required. The LLM integration will primarily read from the existing data and use a separate cache for its own purposes.

### Key Implementation Steps

1. **Develop Pydantic Schemas**: Define the initial set of Pydantic models for the LLM-optimized data formats.
2. **Build the API**: Create a new FastAPI application with the initial set of read-only endpoints.
3. **Implement ETL Scripts**: Develop the initial ETL scripts to transform data from the PostgreSQL database to the LLM-optimized formats.
4. **Set up Caching**: Configure and integrate a Redis cache to improve API performance.
5. **Secure the API**: Implement API key-based authentication and basic rate limiting.

## Consequences

### Positive

- **Enables Advanced AI Capabilities**: Unlocks the potential for sophisticated AI-powered portfolio analysis and insights.
- **Scalable and Secure Data Access**: Provides a scalable and secure way to expose data to internal AI applications.
- **Reusable Infrastructure**: The data access layer can be reused for other internal tools and applications.
- **Improved Decision-Making**: AI-generated insights can help portfolio managers make better-informed decisions.

### Challenges

- **Increased Complexity**: Adds a new component to the overall system architecture that needs to be developed, maintained, and monitored.
- **Data Privacy and Security**: Exposing data via an API introduces new security risks that must be carefully managed.
- **Performance Overhead**: The ETL process and API requests will add some overhead to the system.
- **Schema Management**: The LLM-optimized schemas will need to be versioned and kept in sync with the core application's data models.

## Related ADRs

- ADR-005: External API Integration Strategy
- ADR-006: Security and Authentication Architecture
- ADR-009: Institutional Grade Quantitative Portfolio Analytics
