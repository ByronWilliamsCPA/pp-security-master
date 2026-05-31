"""
Complete External Service Resilience and Monitoring Implementation
Copy this to: src/security_master/resilience/service_monitor.py
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import aiohttp
from pydantic import BaseModel, Field


class ServiceStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit open, requests failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class ServiceMetrics:
    """Service performance metrics."""

    name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time_ms: float = 0.0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    current_status: ServiceStatus = ServiceStatus.UNKNOWN
    circuit_state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def failure_rate(self) -> float:
        return 1.0 - self.success_rate

    @property
    def average_response_time_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time_ms / self.successful_requests


@dataclass
class HealthCheckResult:
    """Result of service health check."""

    service_name: str
    status: ServiceStatus
    response_time_ms: float
    timestamp: datetime
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""

    failure_threshold: int = Field(5, ge=1)
    success_threshold: int = Field(3, ge=1)
    timeout_seconds: int = Field(60, ge=1)
    max_failures_per_minute: int = Field(10, ge=1)


class ServiceResilienceConfig(BaseModel):
    """Service resilience configuration."""

    health_check_interval_seconds: int = Field(30, ge=5)
    request_timeout_seconds: int = Field(10, ge=1)
    max_retries: int = Field(3, ge=0)
    retry_backoff_factor: float = Field(1.5, ge=1.0)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    enable_graceful_degradation: bool = True
    alert_threshold_failure_rate: float = Field(0.5, ge=0.0, le=1.0)


class CircuitBreaker:
    """Circuit breaker implementation for external service calls."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.failure_timestamps: list[datetime] = []
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker.{name}")

    def can_execute(self) -> bool:
        """Check if request can be executed.

        Returns:
            bool: True when circuit is closed or half-open and ready to retry.
        """
        now = datetime.now()

        # Clean old failure timestamps
        self.failure_timestamps = [
            ts for ts in self.failure_timestamps if now - ts < timedelta(minutes=1)
        ]

        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            # Check if timeout period has passed
            if self.last_failure_time and now - self.last_failure_time > timedelta(
                seconds=self.config.timeout_seconds,
            ):
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.logger.info(f"Circuit breaker {self.name} moving to HALF_OPEN")
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Record successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.logger.info(f"Circuit breaker {self.name} moving to CLOSED")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed request."""
        now = datetime.now()
        self.failure_count += 1
        self.last_failure_time = now
        self.failure_timestamps.append(now)

        # Check rate limit
        if len(self.failure_timestamps) >= self.config.max_failures_per_minute:
            self.state = CircuitState.OPEN
            self.logger.warning(f"Circuit breaker {self.name} OPEN due to rate limit")
            return

        # Check failure threshold
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.logger.warning(f"Circuit breaker {self.name} OPEN due to failures")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.logger.warning(f"Circuit breaker {self.name} back to OPEN")


class ServiceMonitor:
    """Monitor external service health and performance."""

    def __init__(self, config: ServiceResilienceConfig | None = None):
        self.config = config or ServiceResilienceConfig()
        self.services: dict[str, ServiceMetrics] = {}
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.health_checks: dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
        self.fallback_handlers: dict[str, Callable] = {}
        self.alert_handlers: list[Callable[[str, ServiceMetrics], Awaitable[None]]] = []
        self.logger = logging.getLogger(f"{__name__}.ServiceMonitor")
        self._monitoring_task: asyncio.Task | None = None
        self._running = False

    def register_service(
        self,
        name: str,
        health_check: Callable[[], Awaitable[HealthCheckResult]],
        fallback_handler: Callable | None = None,
    ):
        """Register a service for monitoring.

        Args:
            name (str): Unique name identifier for the service.
            health_check (Callable[[], Awaitable[HealthCheckResult]]): Async callable returning a health check result.
            fallback_handler (Callable | None): Optional async callable to invoke when the service is unavailable.
        """
        self.services[name] = ServiceMetrics(name=name)
        self.circuit_breakers[name] = CircuitBreaker(name, self.config.circuit_breaker)
        self.health_checks[name] = health_check

        if fallback_handler:
            self.fallback_handlers[name] = fallback_handler

        self.logger.info(f"Registered service: {name}")

    def add_alert_handler(
        self,
        handler: Callable[[str, ServiceMetrics], Awaitable[None]],
    ):
        """Add alert handler for service issues.

        Args:
            handler (Callable[[str, ServiceMetrics], Awaitable[None]]): Async callable invoked when a service alert fires.
        """
        self.alert_handlers.append(handler)

    async def execute_with_resilience(
        self,
        service_name: str,
        operation: Callable[[], Awaitable[Any]],
        fallback_value: Any = None,
    ) -> Any:
        """Execute operation with circuit breaker and fallback.

        Args:
            service_name (str): Name of the registered service to use.
            operation (Callable[[], Awaitable[Any]]): Async callable to execute with resilience.
            fallback_value (Any): Value to return if all attempts and fallback handler fail.

        Returns:
            Any: Result of the operation, fallback handler, or fallback_value.

        Raises:
            ValueError: If an error occurs.
        """
        if service_name not in self.services:
            raise ValueError(f"Service {service_name} not registered")

        circuit_breaker = self.circuit_breakers[service_name]
        metrics = self.services[service_name]

        # Check circuit breaker
        if not circuit_breaker.can_execute():
            self.logger.warning(
                f"Circuit breaker OPEN for {service_name}, using fallback",
            )
            return await self._execute_fallback(service_name, fallback_value)

        # Execute with retry logic
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                # Execute operation with timeout
                result = await asyncio.wait_for(
                    operation(),
                    timeout=self.config.request_timeout_seconds,
                )

                # Record success
                response_time_ms = (time.time() - start_time) * 1000
                self._record_success(service_name, response_time_ms)
                circuit_breaker.record_success()

                return result

            except (TimeoutError, aiohttp.ClientError, Exception) as e:
                self.logger.warning(
                    f"Attempt {attempt + 1} failed for {service_name}: {e}",
                )

                # Record failure
                self._record_failure(service_name, str(e))
                circuit_breaker.record_failure()

                # Last attempt, use fallback
                if attempt == self.config.max_retries:
                    self.logger.error(
                        f"All attempts failed for {service_name}, using fallback",
                    )
                    return await self._execute_fallback(service_name, fallback_value)

                # Wait before retry
                await asyncio.sleep(self.config.retry_backoff_factor**attempt)

        # Should not reach here
        return await self._execute_fallback(service_name, fallback_value)

    async def _execute_fallback(self, service_name: str, fallback_value: Any) -> Any:
        """Execute fallback handler or return fallback value.

        Args:
            service_name (str): Name of the registered service whose fallback handler to invoke.
            fallback_value (Any): Default value to return if no fallback handler is registered.

        Returns:
            Any: Result from the fallback handler or fallback_value when no handler exists.
        """
        if service_name in self.fallback_handlers:
            try:
                return await self.fallback_handlers[service_name]()
            except Exception as e:
                self.logger.error(f"Fallback handler failed for {service_name}: {e}")

        return fallback_value

    def _record_success(self, service_name: str, response_time_ms: float):
        """Record successful request metrics.

        Args:
            service_name (str): Name of the service that succeeded.
            response_time_ms (float): Elapsed time for the request in milliseconds.
        """
        metrics = self.services[service_name]
        metrics.total_requests += 1
        metrics.successful_requests += 1
        metrics.total_response_time_ms += response_time_ms
        metrics.last_success = datetime.now()
        metrics.consecutive_failures = 0

        # Update status
        if metrics.success_rate >= 0.9:
            metrics.current_status = ServiceStatus.HEALTHY
        elif metrics.success_rate >= 0.5:
            metrics.current_status = ServiceStatus.DEGRADED
        else:
            metrics.current_status = ServiceStatus.UNHEALTHY

    def _record_failure(self, service_name: str, error: str):
        """Record failed request metrics.

        Args:
            service_name (str): Name of the service that failed.
            error (str): Error message describing the failure.
        """
        metrics = self.services[service_name]
        metrics.total_requests += 1
        metrics.failed_requests += 1
        metrics.last_failure = datetime.now()
        metrics.consecutive_failures += 1

        # Update status
        if metrics.failure_rate >= 0.5:
            metrics.current_status = ServiceStatus.UNHEALTHY
        elif metrics.failure_rate >= 0.1:
            metrics.current_status = ServiceStatus.DEGRADED
        else:
            metrics.current_status = ServiceStatus.HEALTHY

        # Update circuit state
        metrics.circuit_state = self.circuit_breakers[service_name].state

    async def start_monitoring(self):
        """Start background monitoring task."""
        if self._running:
            return

        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Started service monitoring")

    async def stop_monitoring(self):
        """Stop background monitoring task."""
        if not self._running:
            return

        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Stopped service monitoring")

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
                await self._check_alerts()
                await asyncio.sleep(self.config.health_check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

    async def _run_health_checks(self):
        """Run health checks for all registered services."""
        if not self.health_checks:
            return

        tasks = []
        for service_name, health_check in self.health_checks.items():
            task = asyncio.create_task(
                self._run_single_health_check(service_name, health_check),
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_single_health_check(
        self,
        service_name: str,
        health_check: Callable[[], Awaitable[HealthCheckResult]],
    ):
        """Run health check for a single service.

        Args:
            service_name (str): Name of the service being checked.
            health_check (Callable[[], Awaitable[HealthCheckResult]]): Async callable that performs the health check.
        """
        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                health_check(),
                timeout=self.config.request_timeout_seconds,
            )

            # Update metrics based on health check result
            if result.status == ServiceStatus.HEALTHY:
                self._record_success(service_name, result.response_time_ms)
                self.circuit_breakers[service_name].record_success()
            else:
                self._record_failure(
                    service_name,
                    result.error or "Health check failed",
                )
                self.circuit_breakers[service_name].record_failure()

        except Exception as e:
            self.logger.warning(f"Health check failed for {service_name}: {e}")
            self._record_failure(service_name, str(e))
            self.circuit_breakers[service_name].record_failure()

    async def _check_alerts(self):
        """Check if any services need alerts."""
        for service_name, metrics in self.services.items():
            if (
                metrics.failure_rate >= self.config.alert_threshold_failure_rate
                or metrics.current_status == ServiceStatus.UNHEALTHY
            ):

                # Send alerts
                for alert_handler in self.alert_handlers:
                    try:
                        await alert_handler(service_name, metrics)
                    except Exception as e:
                        self.logger.error(f"Alert handler error: {e}")

    def get_service_status(self, service_name: str) -> ServiceMetrics | None:
        """Get current status of a service.

        Args:
            service_name (str): Name of the service to look up.

        Returns:
            ServiceMetrics | None: Current metrics for the service, or None if not registered.
        """
        return self.services.get(service_name)

    def get_all_service_status(self) -> dict[str, ServiceMetrics]:
        """Get status of all services.

        Returns:
            dict[str, ServiceMetrics]: Copy of the service metrics dict keyed by service name.
        """
        return self.services.copy()

    def get_system_health(self) -> dict[str, Any]:
        """Get overall system health summary.

        Returns:
            dict[str, Any]: Summary dict with overall_status, service counts, and per-service details.
        """
        if not self.services:
            return {
                "overall_status": ServiceStatus.UNKNOWN,
                "total_services": 0,
                "healthy_services": 0,
                "degraded_services": 0,
                "unhealthy_services": 0,
                "services": {},
            }

        status_counts = {
            ServiceStatus.HEALTHY: 0,
            ServiceStatus.DEGRADED: 0,
            ServiceStatus.UNHEALTHY: 0,
            ServiceStatus.UNKNOWN: 0,
        }

        service_details = {}

        for name, metrics in self.services.items():
            status_counts[metrics.current_status] += 1
            service_details[name] = {
                "status": metrics.current_status,
                "success_rate": metrics.success_rate,
                "circuit_state": metrics.circuit_state,
                "average_response_time_ms": metrics.average_response_time_ms,
            }

        # Determine overall status
        if status_counts[ServiceStatus.UNHEALTHY] > 0:
            overall_status = ServiceStatus.UNHEALTHY
        elif status_counts[ServiceStatus.DEGRADED] > 0:
            overall_status = ServiceStatus.DEGRADED
        elif status_counts[ServiceStatus.HEALTHY] > 0:
            overall_status = ServiceStatus.HEALTHY
        else:
            overall_status = ServiceStatus.UNKNOWN

        return {
            "overall_status": overall_status,
            "total_services": len(self.services),
            "healthy_services": status_counts[ServiceStatus.HEALTHY],
            "degraded_services": status_counts[ServiceStatus.DEGRADED],
            "unhealthy_services": status_counts[ServiceStatus.UNHEALTHY],
            "unknown_services": status_counts[ServiceStatus.UNKNOWN],
            "services": service_details,
        }


# Example health check implementations
async def openfigi_health_check() -> HealthCheckResult:
    """Health check for OpenFIGI API.

    Returns:
        HealthCheckResult: Health check result indicating HEALTHY, DEGRADED, or UNHEALTHY.
    """
    try:
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.openfigi.com/v3/search",
                params={"query": "test"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_time_ms = (time.time() - start_time) * 1000

                if response.status == 200:
                    return HealthCheckResult(
                        service_name="openfigi",
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=response_time_ms,
                        timestamp=datetime.now(),
                    )
                return HealthCheckResult(
                    service_name="openfigi",
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    error=f"HTTP {response.status}",
                )

    except Exception as e:
        return HealthCheckResult(
            service_name="openfigi",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            error=str(e),
        )


async def pp_classifier_health_check() -> HealthCheckResult:
    """Health check for pp-portfolio-classifier.

    Returns:
        HealthCheckResult: Health check result indicating HEALTHY or UNHEALTHY.
    """
    try:
        start_time = time.time()

        # Test import and basic functionality
        from security_master.adapters.pp_classifier_adapter import PPClassifierAdapter

        adapter = PPClassifierAdapter()

        if adapter.is_available():
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="pp-classifier",
                status=ServiceStatus.HEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
            )
        return HealthCheckResult(
            service_name="pp-classifier",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            error="pp-portfolio-classifier not available",
        )

    except Exception as e:
        return HealthCheckResult(
            service_name="pp-classifier",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            error=str(e),
        )


async def database_health_check() -> HealthCheckResult:
    """Health check for database connection.

    Returns:
        HealthCheckResult: Health check result indicating HEALTHY or UNHEALTHY.
    """
    try:
        start_time = time.time()

        # Test database connection
        # This would use your actual database connection
        # from security_master.database.engine import DatabaseEngine
        # engine = DatabaseEngine()
        # await engine.execute("SELECT 1")

        response_time_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            service_name="database",
            status=ServiceStatus.HEALTHY,
            response_time_ms=response_time_ms,
            timestamp=datetime.now(),
        )

    except Exception as e:
        return HealthCheckResult(
            service_name="database",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=0.0,
            timestamp=datetime.now(),
            error=str(e),
        )


# Example alert handlers
async def log_alert_handler(service_name: str, metrics: ServiceMetrics):
    """Log-based alert handler.

    Args:
        service_name (str): Name of the service that triggered the alert.
        metrics (ServiceMetrics): Current metrics for the alerting service.
    """
    logger = logging.getLogger("ServiceAlert")
    logger.error(
        f"Service {service_name} unhealthy: "
        f"success_rate={metrics.success_rate:.1%}, "
        f"status={metrics.current_status.value}, "
        f"consecutive_failures={metrics.consecutive_failures}",
    )


async def webhook_alert_handler(service_name: str, metrics: ServiceMetrics):
    """Webhook-based alert handler.

    Args:
        service_name (str): Name of the service that triggered the alert.
        metrics (ServiceMetrics): Current metrics for the alerting service.
    """
    # This would send alerts to external monitoring systems
    alert_data = {
        "service": service_name,
        "status": metrics.current_status.value,
        "success_rate": metrics.success_rate,
        "consecutive_failures": metrics.consecutive_failures,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://hooks.slack.com/your-webhook-url",
                json={
                    "text": f"🚨 Service {service_name} is {metrics.current_status.value}",
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status != 200:
                    logger.warning(f"Alert webhook failed: HTTP {response.status}")
    except Exception as e:
        logger.error(f"Alert webhook error: {e}")


async def main():
    """Example usage of service monitor."""
    logging.basicConfig(level=logging.INFO)

    # Create service monitor
    config = ServiceResilienceConfig(
        health_check_interval_seconds=10,
        alert_threshold_failure_rate=0.3,
    )
    monitor = ServiceMonitor(config)

    # Register services
    monitor.register_service("openfigi", openfigi_health_check)
    monitor.register_service("pp-classifier", pp_classifier_health_check)
    monitor.register_service("database", database_health_check)

    # Add alert handlers
    monitor.add_alert_handler(log_alert_handler)
    # monitor.add_alert_handler(webhook_alert_handler)

    # Start monitoring
    await monitor.start_monitoring()

    try:
        # Example service call with resilience
        async def example_openfigi_call():
            # Simulate API call
            await asyncio.sleep(0.1)
            return {"result": "success"}

        result = await monitor.execute_with_resilience(
            "openfigi",
            example_openfigi_call,
            fallback_value={"result": "fallback"},
        )
        print(f"Result: {result}")

        # Let monitoring run for a while
        await asyncio.sleep(30)

        # Check system health
        health = monitor.get_system_health()
        print(f"\nSystem Health: {health}")

    finally:
        await monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
