"""
Sistema de Monitoreo y Logging Avanzado para MSC SRPK v2.0
Implementa observabilidad completa, alertas, métricas de negocio y dashboards en tiempo real.
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import psutil
import requests
from collections import defaultdict, deque
import structlog
from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Niveles de logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertSeverity(Enum):
    """Severidad de alertas."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MetricType(Enum):
    """Tipos de métricas."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class LogEntry:
    """Entrada de log estructurada."""
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    extra_data: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['level'] = self.level.value
        return data


@dataclass
class Alert:
    """Alerta del sistema."""
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    description: str
    source: str
    metric_name: Optional[str] = None
    threshold: Optional[float] = None
    current_value: Optional[float] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['severity'] = self.severity.value
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


class StructuredLogger:
    """Logger estructurado con contexto."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = structlog.get_logger(name)
        self._context = {}
    
    def bind(self, **kwargs) -> 'StructuredLogger':
        """Añade contexto al logger."""
        new_logger = StructuredLogger(self.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Log con contexto estructurado."""
        frame = traceback.extract_stack()[-2]
        
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            logger_name=self.name,
            message=message,
            module=frame.filename.split('/')[-1],
            function=frame.name,
            line_number=frame.lineno,
            thread_id=threading.get_ident(),
            process_id=os.getpid(),
            extra_data={**self._context, **kwargs}
        )
        
        # Log estructurado
        self.logger.bind(
            timestamp=log_entry.timestamp.isoformat(),
            level=level.value,
            module=log_entry.module,
            function=log_entry.function,
            line=log_entry.line_number,
            thread=log_entry.thread_id,
            process=log_entry.process_id,
            **log_entry.extra_data
        ).log(level.value.lower(), message)
        
        # Enviar a sistema de monitoreo
        MonitoringSystem.get_instance().log_structured(log_entry)
    
    def debug(self, message: str, **kwargs):
        """Log de debug."""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log de información."""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log de advertencia."""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log de error."""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log crítico."""
        self._log(LogLevel.CRITICAL, message, **kwargs)


class MetricsCollector:
    """Recolector de métricas del sistema."""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._counters = {}
        self._gauges = {}
        self._histograms = {}
        self._custom_metrics = {}
        
        # Métricas del sistema
        self._init_system_metrics()
        
        # Métricas de la aplicación
        self._init_app_metrics()
    
    def _init_system_metrics(self):
        """Inicializa métricas del sistema."""
        self.system_cpu_usage = Gauge(
            'system_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'system_memory_usage_percent',
            'Memory usage percentage',
            registry=self.registry
        )
        
        self.system_disk_usage = Gauge(
            'system_disk_usage_percent',
            'Disk usage percentage',
            registry=self.registry
        )
        
        self.system_network_io = Gauge(
            'system_network_io_bytes',
            'Network I/O bytes',
            ['direction'],  # 'in' or 'out'
            registry=self.registry
        )
    
    def _init_app_metrics(self):
        """Inicializa métricas de la aplicación."""
        # Métricas de requests
        self.requests_total = Counter(
            'msc_srpk_requests_total',
            'Total number of requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            'msc_srpk_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Métricas de análisis de código
        self.code_analysis_total = Counter(
            'msc_srpk_code_analysis_total',
            'Total number of code analyses',
            ['language', 'status'],
            registry=self.registry
        )
        
        self.code_analysis_duration = Histogram(
            'msc_srpk_code_analysis_duration_seconds',
            'Code analysis duration in seconds',
            ['language'],
            registry=self.registry
        )
        
        # Métricas de calidad
        self.quality_metrics = Gauge(
            'msc_srpk_quality_metric',
            'Code quality metrics',
            ['metric_name', 'file_path'],
            registry=self.registry
        )
        
        # Métricas de usuarios activos
        self.active_users = Gauge(
            'msc_srpk_active_users',
            'Number of active users',
            registry=self.registry
        )
        
        # Métricas de licencias
        self.license_validations = Counter(
            'msc_srpk_license_validations_total',
            'Total license validations',
            ['status'],  # 'valid', 'invalid', 'expired'
            registry=self.registry
        )
    
    def update_system_metrics(self):
        """Actualiza métricas del sistema."""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_cpu_usage.set(cpu_percent)
            
            # Memoria
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.percent)
            
            # Disco
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.system_disk_usage.set(disk_percent)
            
            # Red
            network = psutil.net_io_counters()
            self.system_network_io.labels(direction='in').set(network.bytes_recv)
            self.system_network_io.labels(direction='out').set(network.bytes_sent)
            
        except Exception as e:
            logger.error(f"Error actualizando métricas del sistema: {e}")
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Registra métrica de request."""
        self.requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status_code
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_code_analysis(self, language: str, duration: float, success: bool):
        """Registra métrica de análisis de código."""
        status = 'success' if success else 'error'
        self.code_analysis_total.labels(
            language=language,
            status=status
        ).inc()
        
        self.code_analysis_duration.labels(language=language).observe(duration)
    
    def record_quality_metric(self, metric_name: str, file_path: str, value: float):
        """Registra métrica de calidad."""
        self.quality_metrics.labels(
            metric_name=metric_name,
            file_path=file_path
        ).set(value)
    
    def update_active_users(self, count: int):
        """Actualiza contador de usuarios activos."""
        self.active_users.set(count)
    
    def record_license_validation(self, status: str):
        """Registra validación de licencia."""
        self.license_validations.labels(status=status).inc()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de métricas."""
        return {
            "system": {
                "cpu_usage": self.system_cpu_usage._value._value,
                "memory_usage": self.system_memory_usage._value._value,
                "disk_usage": self.system_disk_usage._value._value
            },
            "application": {
                "requests_total": sum(c._value._value for c in self.requests_total._metrics.values()),
                "active_users": self.active_users._value._value
            }
        }


class AlertManager:
    """Gestor de alertas del sistema."""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules: List[Dict] = []
        self.alert_channels: List[Callable] = []
        self._init_default_rules()
    
    def _init_default_rules(self):
        """Inicializa reglas de alerta por defecto."""
        self.alert_rules = [
            {
                "name": "high_cpu_usage",
                "metric": "system_cpu_usage_percent",
                "threshold": 80.0,
                "severity": AlertSeverity.HIGH,
                "description": "CPU usage is above 80%"
            },
            {
                "name": "high_memory_usage",
                "metric": "system_memory_usage_percent",
                "threshold": 85.0,
                "severity": AlertSeverity.HIGH,
                "description": "Memory usage is above 85%"
            },
            {
                "name": "high_disk_usage",
                "metric": "system_disk_usage_percent",
                "threshold": 90.0,
                "severity": AlertSeverity.CRITICAL,
                "description": "Disk usage is above 90%"
            },
            {
                "name": "high_error_rate",
                "metric": "msc_srpk_requests_total",
                "condition": "status=500",
                "threshold": 10,
                "severity": AlertSeverity.HIGH,
                "description": "High error rate detected"
            },
            {
                "name": "slow_response_time",
                "metric": "msc_srpk_request_duration_seconds",
                "threshold": 5.0,
                "severity": AlertSeverity.MEDIUM,
                "description": "Response time is above 5 seconds"
            }
        ]
    
    def add_alert_rule(self, rule: Dict):
        """Añade regla de alerta."""
        self.alert_rules.append(rule)
    
    def add_alert_channel(self, channel: Callable):
        """Añade canal de alertas."""
        self.alert_channels.append(channel)
    
    def check_alerts(self, metrics: Dict[str, float]):
        """Verifica alertas basadas en métricas."""
        for rule in self.alert_rules:
            metric_name = rule["metric"]
            threshold = rule["threshold"]
            severity = rule["severity"]
            
            if metric_name in metrics:
                current_value = metrics[metric_name]
                
                if current_value >= threshold:
                    alert_id = f"{rule['name']}_{int(time.time())}"
                    
                    if alert_id not in self.alerts:
                        alert = Alert(
                            alert_id=alert_id,
                            timestamp=datetime.now(),
                            severity=severity,
                            title=rule["name"],
                            description=rule["description"],
                            source=metric_name,
                            metric_name=metric_name,
                            threshold=threshold,
                            current_value=current_value,
                            metadata={"rule": rule}
                        )
                        
                        self.alerts[alert_id] = alert
                        self._send_alert(alert)
    
    def _send_alert(self, alert: Alert):
        """Envía alerta a todos los canales configurados."""
        for channel in self.alert_channels:
            try:
                channel(alert)
            except Exception as e:
                logger.error(f"Error enviando alerta: {e}")
    
    def resolve_alert(self, alert_id: str):
        """Resuelve una alerta."""
        if alert_id in self.alerts:
            self.alerts[alert_id].resolved = True
            self.alerts[alert_id].resolved_at = datetime.now()
    
    def get_active_alerts(self) -> List[Alert]:
        """Obtiene alertas activas."""
        return [alert for alert in self.alerts.values() if not alert.resolved]


class HealthChecker:
    """Verificador de salud del sistema."""
    
    def __init__(self):
        self.checks: List[Callable] = []
        self._init_default_checks()
    
    def _init_default_checks(self):
        """Inicializa verificaciones por defecto."""
        self.checks = [
            self._check_database,
            self._check_disk_space,
            self._check_memory,
            self._check_network,
            self._check_external_services
        ]
    
    def add_check(self, check: Callable):
        """Añade verificación personalizada."""
        self.checks.append(check)
    
    def run_health_check(self) -> Dict[str, Any]:
        """Ejecuta todas las verificaciones de salud."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        failed_checks = 0
        
        for check in self.checks:
            try:
                check_name = check.__name__
                check_result = check()
                results["checks"][check_name] = check_result
                
                if not check_result.get("healthy", False):
                    failed_checks += 1
                    
            except Exception as e:
                results["checks"][check.__name__] = {
                    "healthy": False,
                    "error": str(e)
                }
                failed_checks += 1
        
        if failed_checks > 0:
            results["overall_status"] = "unhealthy"
        
        return results
    
    def _check_database(self) -> Dict[str, Any]:
        """Verifica salud de la base de datos."""
        try:
            # Verificar conexión a SQLite
            conn = sqlite3.connect("msc_srpk.db", timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            
            return {"healthy": True, "message": "Database connection successful"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Verifica espacio en disco."""
        try:
            disk = psutil.disk_usage('/')
            free_percent = (disk.free / disk.total) * 100
            
            if free_percent < 10:
                return {"healthy": False, "error": f"Low disk space: {free_percent:.1f}% free"}
            
            return {
                "healthy": True,
                "free_space_percent": free_percent,
                "free_space_gb": disk.free / (1024**3)
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_memory(self) -> Dict[str, Any]:
        """Verifica memoria disponible."""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                return {"healthy": False, "error": f"High memory usage: {memory.percent}%"}
            
            return {
                "healthy": True,
                "memory_usage_percent": memory.percent,
                "available_gb": memory.available / (1024**3)
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_network(self) -> Dict[str, Any]:
        """Verifica conectividad de red."""
        try:
            # Verificar conectividad básica
            response = requests.get("https://httpbin.org/status/200", timeout=5)
            return {"healthy": True, "status_code": response.status_code}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def _check_external_services(self) -> Dict[str, Any]:
        """Verifica servicios externos."""
        try:
            # Verificar servicios críticos
            services = [
                "https://api.github.com",
                "https://huggingface.co"
            ]
            
            results = {}
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    results[service] = {
                        "healthy": response.status_code == 200,
                        "status_code": response.status_code
                    }
                except Exception as e:
                    results[service] = {
                        "healthy": False,
                        "error": str(e)
                    }
            
            all_healthy = all(result["healthy"] for result in results.values())
            return {
                "healthy": all_healthy,
                "services": results
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}


class MonitoringSystem:
    """Sistema principal de monitoreo."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.logger = StructuredLogger(__name__)
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.health_checker = HealthChecker()
        self.db_path = "monitoring.db"
        self.running = False
        self._init_database()
        self._init_sentry()
    
    @classmethod
    def get_instance(cls):
        """Obtiene instancia singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _init_database(self):
        """Inicializa base de datos de monitoreo."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    logger_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    function TEXT,
                    line_number INTEGER,
                    thread_id INTEGER,
                    process_id INTEGER,
                    user_id TEXT,
                    session_id TEXT,
                    request_id TEXT,
                    correlation_id TEXT,
                    extra_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source TEXT,
                    metric_name TEXT,
                    threshold REAL,
                    current_value REAL,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)
            """)
            
            conn.commit()
    
    def _init_sentry(self):
        """Inicializa Sentry para error tracking."""
        try:
            sentry_dsn = os.getenv('SENTRY_DSN')
            if sentry_dsn:
                sentry_logging = LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR
                )
                
                sentry_sdk.init(
                    dsn=sentry_dsn,
                    integrations=[sentry_logging],
                    traces_sample_rate=0.1,
                    environment=os.getenv('ENVIRONMENT', 'development')
                )
                
                self.logger.info("Sentry initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Sentry: {e}")
    
    def start(self, port: int = 8001):
        """Inicia el sistema de monitoreo."""
        if self.running:
            return
        
        self.running = True
        
        # Iniciar servidor de métricas Prometheus
        start_http_server(port, registry=self.metrics_collector.registry)
        self.logger.info(f"Prometheus metrics server started on port {port}")
        
        # Iniciar loop de monitoreo
        self._monitoring_loop()
        
        self.logger.info("Monitoring system started")
    
    def stop(self):
        """Detiene el sistema de monitoreo."""
        self.running = False
        self.logger.info("Monitoring system stopped")
    
    def _monitoring_loop(self):
        """Loop principal de monitoreo."""
        def run_loop():
            while self.running:
                try:
                    # Actualizar métricas del sistema
                    self.metrics_collector.update_system_metrics()
                    
                    # Verificar alertas
                    metrics_summary = self.metrics_collector.get_metrics_summary()
                    system_metrics = metrics_summary.get("system", {})
                    self.alert_manager.check_alerts(system_metrics)
                    
                    time.sleep(30)  # Verificar cada 30 segundos
                    
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(60)  # Esperar más tiempo en caso de error
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
    
    def log_structured(self, log_entry: LogEntry):
        """Almacena log estructurado."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO logs 
                    (timestamp, level, logger_name, message, module, function, 
                     line_number, thread_id, process_id, user_id, session_id, 
                     request_id, correlation_id, extra_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_entry.timestamp.isoformat(),
                    log_entry.level.value,
                    log_entry.logger_name,
                    log_entry.message,
                    log_entry.module,
                    log_entry.function,
                    log_entry.line_number,
                    log_entry.thread_id,
                    log_entry.process_id,
                    log_entry.user_id,
                    log_entry.session_id,
                    log_entry.request_id,
                    log_entry.correlation_id,
                    json.dumps(log_entry.extra_data) if log_entry.extra_data else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing structured log: {e}")
    
    def get_logs(self, 
                 start_time: datetime,
                 end_time: datetime,
                 level: Optional[LogLevel] = None,
                 limit: int = 1000) -> List[Dict]:
        """Obtiene logs filtrados."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM logs 
                WHERE timestamp BETWEEN ? AND ?
            """
            params = [start_time.isoformat(), end_time.isoformat()]
            
            if level:
                query += " AND level = ?"
                params.append(level.value)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            columns = [description[0] for description in cursor.description]
            
            logs = []
            for row in cursor.fetchall():
                log_dict = dict(zip(columns, row))
                if log_dict['extra_data']:
                    log_dict['extra_data'] = json.loads(log_dict['extra_data'])
                logs.append(log_dict)
            
            return logs
    
    def get_health_status(self) -> Dict[str, Any]:
        """Obtiene estado de salud del sistema."""
        return self.health_checker.run_health_check()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas actuales."""
        return self.metrics_collector.get_metrics_summary()
    
    def get_alerts(self, active_only: bool = True) -> List[Dict]:
        """Obtiene alertas."""
        alerts = self.alert_manager.get_active_alerts() if active_only else list(self.alert_manager.alerts.values())
        return [alert.to_dict() for alert in alerts]


# Decoradores para monitoreo
def monitor_performance(operation_name: str):
    """Decorador para monitorear rendimiento."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            monitoring = MonitoringSystem.get_instance()
            logger = monitoring.logger.bind(operation=operation_name)
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Registrar métrica de éxito
                monitoring.metrics_collector.record_code_analysis(
                    language="python",
                    duration=duration,
                    success=True
                )
                
                logger.info(f"Operation {operation_name} completed successfully", duration=duration)
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Registrar métrica de error
                monitoring.metrics_collector.record_code_analysis(
                    language="python",
                    duration=duration,
                    success=False
                )
                
                logger.error(f"Operation {operation_name} failed", 
                           duration=duration, error=str(e), exc_info=True)
                raise
        
        return wrapper
    return decorator


def track_user_activity(user_id: str):
    """Decorador para trackear actividad de usuario."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitoring = MonitoringSystem.get_instance()
            logger = monitoring.logger.bind(user_id=user_id)
            
            logger.info(f"User activity: {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                logger.info(f"User activity completed: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"User activity failed: {func.__name__}", error=str(e))
                raise
        
        return wrapper
    return decorator


# Inicialización del sistema
def initialize_monitoring(port: int = 8001):
    """Inicializa el sistema de monitoreo."""
    monitoring = MonitoringSystem.get_instance()
    monitoring.start(port)
    
    # Configurar structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger.info("Monitoring system initialized")


def get_monitoring_logger(name: str) -> StructuredLogger:
    """Obtiene logger estructurado."""
    return StructuredLogger(name)


def get_health_status() -> Dict[str, Any]:
    """Obtiene estado de salud."""
    return MonitoringSystem.get_instance().get_health_status()


def get_metrics() -> Dict[str, Any]:
    """Obtiene métricas."""
    return MonitoringSystem.get_instance().get_metrics()


def get_alerts() -> List[Dict]:
    """Obtiene alertas activas."""
    return MonitoringSystem.get_instance().get_alerts()
