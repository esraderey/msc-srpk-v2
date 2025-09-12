"""
Sistema avanzado de métricas y dashboards para MSC SRPK v2.0
Proporciona análisis en tiempo real, tendencias y visualizaciones.
"""

import json
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import os
import threading
from collections import defaultdict, deque
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Tipos de métricas disponibles."""
    QUALITY = "quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TESTING = "testing"
    USAGE = "usage"
    TREND = "trend"


class MetricGranularity(Enum):
    """Granularidad temporal de las métricas."""
    REAL_TIME = "real_time"  # Cada segundo
    MINUTE = "minute"        # Cada minuto
    HOUR = "hour"            # Cada hora
    DAY = "day"              # Cada día
    WEEK = "week"            # Cada semana
    MONTH = "month"          # Cada mes


@dataclass
class MetricDataPoint:
    """Punto de datos de una métrica."""
    timestamp: datetime
    metric_type: MetricType
    metric_name: str
    value: float
    metadata: Dict[str, Any] = None
    tags: Dict[str, str] = None
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['metric_type'] = self.metric_type.value
        return data


@dataclass
class MetricAggregation:
    """Agregación de métricas."""
    metric_name: str
    metric_type: MetricType
    granularity: MetricGranularity
    timestamp: datetime
    count: int
    sum: float
    avg: float
    min: float
    max: float
    std: float
    percentiles: Dict[str, float] = None


class MetricsDatabase:
    """Base de datos para almacenar métricas."""
    
    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = db_path
        self._init_database()
        self._lock = threading.Lock()
    
    def _init_database(self):
        """Inicializa la base de datos."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    metadata TEXT,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON metrics(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_type_name 
                ON metrics(metric_type, metric_name)
            """)
            
            # Tabla para agregaciones
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metric_aggregations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    granularity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    sum_value REAL NOT NULL,
                    avg_value REAL NOT NULL,
                    min_value REAL NOT NULL,
                    max_value REAL NOT NULL,
                    std_value REAL NOT NULL,
                    percentiles TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(metric_name, metric_type, granularity, timestamp)
                )
            """)
            
            conn.commit()
    
    def store_metric(self, metric: MetricDataPoint):
        """Almacena una métrica."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO metrics 
                    (timestamp, metric_type, metric_name, value, metadata, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    metric.timestamp.isoformat(),
                    metric.metric_type.value,
                    metric.metric_name,
                    metric.value,
                    json.dumps(metric.metadata) if metric.metadata else None,
                    json.dumps(metric.tags) if metric.tags else None
                ))
                conn.commit()
    
    def get_metrics(self, 
                   metric_name: str,
                   metric_type: MetricType,
                   start_time: datetime,
                   end_time: datetime,
                   granularity: MetricGranularity = MetricGranularity.MINUTE) -> List[MetricAggregation]:
        """Obtiene métricas agregadas."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM metric_aggregations 
                WHERE metric_name = ? AND metric_type = ? AND granularity = ?
                AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (
                metric_name,
                metric_type.value,
                granularity.value,
                start_time.isoformat(),
                end_time.isoformat()
            ))
            
            results = []
            for row in cursor.fetchall():
                aggregation = MetricAggregation(
                    metric_name=row[1],
                    metric_type=MetricType(row[2]),
                    granularity=MetricGranularity(row[3]),
                    timestamp=datetime.fromisoformat(row[4]),
                    count=row[5],
                    sum=row[6],
                    avg=row[7],
                    min=row[8],
                    max=row[9],
                    std=row[10],
                    percentiles=json.loads(row[11]) if row[11] else None
                )
                results.append(aggregation)
            
            return results
    
    def aggregate_metrics(self, 
                         granularity: MetricGranularity,
                         end_time: datetime = None):
        """Agrega métricas por granularidad temporal."""
        if end_time is None:
            end_time = datetime.now()
        
        # Calcular tiempo de inicio basado en granularidad
        if granularity == MetricGranularity.MINUTE:
            start_time = end_time - timedelta(minutes=1)
        elif granularity == MetricGranularity.HOUR:
            start_time = end_time - timedelta(hours=1)
        elif granularity == MetricGranularity.DAY:
            start_time = end_time - timedelta(days=1)
        elif granularity == MetricGranularity.WEEK:
            start_time = end_time - timedelta(weeks=1)
        elif granularity == MetricGranularity.MONTH:
            start_time = end_time - timedelta(days=30)
        else:
            return
        
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Obtener métricas raw para agregar
                cursor = conn.execute("""
                    SELECT metric_name, metric_type, value
                    FROM metrics 
                    WHERE timestamp BETWEEN ? AND ?
                    AND timestamp NOT IN (
                        SELECT DISTINCT timestamp FROM metric_aggregations 
                        WHERE granularity = ?
                    )
                """, (
                    start_time.isoformat(),
                    end_time.isoformat(),
                    granularity.value
                ))
                
                # Agrupar por métrica
                metrics_by_name = defaultdict(list)
                for row in cursor.fetchall():
                    metrics_by_name[(row[0], row[1])].append(row[2])
                
                # Calcular agregaciones
                for (metric_name, metric_type), values in metrics_by_name.items():
                    if not values:
                        continue
                    
                    values_array = np.array(values)
                    
                    aggregation = MetricAggregation(
                        metric_name=metric_name,
                        metric_type=MetricType(metric_type),
                        granularity=granularity,
                        timestamp=end_time,
                        count=len(values),
                        sum=float(np.sum(values_array)),
                        avg=float(np.mean(values_array)),
                        min=float(np.min(values_array)),
                        max=float(np.max(values_array)),
                        std=float(np.std(values_array)),
                        percentiles={
                            "p50": float(np.percentile(values_array, 50)),
                            "p90": float(np.percentile(values_array, 90)),
                            "p95": float(np.percentile(values_array, 95)),
                            "p99": float(np.percentile(values_array, 99))
                        }
                    )
                    
                    # Insertar agregación
                    conn.execute("""
                        INSERT OR REPLACE INTO metric_aggregations 
                        (metric_name, metric_type, granularity, timestamp, 
                         count, sum_value, avg_value, min_value, max_value, 
                         std_value, percentiles)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        aggregation.metric_name,
                        aggregation.metric_type.value,
                        aggregation.granularity.value,
                        aggregation.timestamp.isoformat(),
                        aggregation.count,
                        aggregation.sum,
                        aggregation.avg,
                        aggregation.min,
                        aggregation.max,
                        aggregation.std,
                        json.dumps(aggregation.percentiles)
                    ))
                
                conn.commit()


class MetricsCollector:
    """Recolector de métricas en tiempo real."""
    
    def __init__(self, db: MetricsDatabase):
        self.db = db
        self._metrics_buffer = deque(maxlen=1000)
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
    
    def start(self):
        """Inicia el recolector."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._collect_loop)
            self._thread.daemon = True
            self._thread.start()
            logger.info("Métricas recolector iniciado")
    
    def stop(self):
        """Detiene el recolector."""
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("Métricas recolector detenido")
    
    def _collect_loop(self):
        """Loop principal de recolección."""
        while self._running:
            try:
                # Procesar buffer
                with self._lock:
                    while self._metrics_buffer:
                        metric = self._metrics_buffer.popleft()
                        self.db.store_metric(metric)
                
                # Agregar métricas
                self.db.aggregate_metrics(MetricGranularity.MINUTE)
                
                time.sleep(1)  # Recolectar cada segundo
                
            except Exception as e:
                logger.error(f"Error en recolección de métricas: {e}")
                time.sleep(5)
    
    def record_metric(self, 
                     metric_type: MetricType,
                     metric_name: str,
                     value: float,
                     metadata: Dict[str, Any] = None,
                     tags: Dict[str, str] = None):
        """Registra una métrica."""
        metric = MetricDataPoint(
            timestamp=datetime.now(),
            metric_type=metric_type,
            metric_name=metric_name,
            value=value,
            metadata=metadata,
            tags=tags
        )
        
        with self._lock:
            self._metrics_buffer.append(metric)


class QualityMetrics:
    """Métricas de calidad de código."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_complexity_metrics(self, 
                                 file_path: str,
                                 cyclomatic_complexity: int,
                                 cognitive_complexity: int,
                                 maintainability_index: float):
        """Registra métricas de complejidad."""
        tags = {"file_path": file_path}
        
        self.collector.record_metric(
            MetricType.QUALITY,
            "cyclomatic_complexity",
            cyclomatic_complexity,
            tags=tags
        )
        
        self.collector.record_metric(
            MetricType.QUALITY,
            "cognitive_complexity",
            cognitive_complexity,
            tags=tags
        )
        
        self.collector.record_metric(
            MetricType.QUALITY,
            "maintainability_index",
            maintainability_index,
            tags=tags
        )
    
    def record_security_metrics(self, 
                               file_path: str,
                               security_issues: List[str]):
        """Registra métricas de seguridad."""
        tags = {"file_path": file_path}
        
        self.collector.record_metric(
            MetricType.SECURITY,
            "security_issues_count",
            len(security_issues),
            metadata={"issues": security_issues},
            tags=tags
        )
    
    def record_code_smells(self, 
                          file_path: str,
                          code_smells: List[str]):
        """Registra code smells."""
        tags = {"file_path": file_path}
        
        self.collector.record_metric(
            MetricType.QUALITY,
            "code_smells_count",
            len(code_smells),
            metadata={"smells": code_smells},
            tags=tags
        )


class PerformanceMetrics:
    """Métricas de rendimiento."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_analysis_time(self, 
                            project_path: str,
                            analysis_time: float,
                            files_processed: int):
        """Registra tiempo de análisis."""
        tags = {"project_path": project_path}
        
        self.collector.record_metric(
            MetricType.PERFORMANCE,
            "analysis_time",
            analysis_time,
            metadata={"files_processed": files_processed},
            tags=tags
        )
        
        self.collector.record_metric(
            MetricType.PERFORMANCE,
            "files_per_second",
            files_processed / max(analysis_time, 0.001),
            tags=tags
        )
    
    def record_embedding_time(self, 
                             code_size: int,
                             embedding_time: float):
        """Registra tiempo de generación de embeddings."""
        self.collector.record_metric(
            MetricType.PERFORMANCE,
            "embedding_generation_time",
            embedding_time,
            metadata={"code_size": code_size},
            tags={"operation": "embedding"}
        )


class TestingMetrics:
    """Métricas de testing."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_test_results(self, 
                           test_framework: str,
                           total_tests: int,
                           passed_tests: int,
                           failed_tests: int,
                           execution_time: float):
        """Registra resultados de tests."""
        tags = {"framework": test_framework}
        
        self.collector.record_metric(
            MetricType.TESTING,
            "total_tests",
            total_tests,
            tags=tags
        )
        
        self.collector.record_metric(
            MetricType.TESTING,
            "test_success_rate",
            passed_tests / max(total_tests, 1),
            tags=tags
        )
        
        self.collector.record_metric(
            MetricType.TESTING,
            "test_execution_time",
            execution_time,
            tags=tags
        )


class UsageMetrics:
    """Métricas de uso."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_command_usage(self, 
                           command: str,
                           execution_time: float,
                           success: bool):
        """Registra uso de comandos."""
        self.collector.record_metric(
            MetricType.USAGE,
            "command_usage",
            1 if success else 0,
            metadata={
                "command": command,
                "execution_time": execution_time,
                "success": success
            }
        )
    
    def record_license_validation(self, 
                                 license_type: str,
                                 success: bool):
        """Registra validación de licencias."""
        self.collector.record_metric(
            MetricType.USAGE,
            "license_validation",
            1 if success else 0,
            tags={"license_type": license_type}
        )


class MetricsDashboard:
    """Dashboard de métricas."""
    
    def __init__(self, db: MetricsDatabase):
        self.db = db
    
    def get_quality_overview(self, 
                           hours: int = 24) -> Dict[str, Any]:
        """Obtiene resumen de calidad."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Obtener métricas de calidad
        complexity_metrics = self.db.get_metrics(
            "cyclomatic_complexity",
            MetricType.QUALITY,
            start_time,
            end_time
        )
        
        maintainability_metrics = self.db.get_metrics(
            "maintainability_index",
            MetricType.QUALITY,
            start_time,
            end_time
        )
        
        security_metrics = self.db.get_metrics(
            "security_issues_count",
            MetricType.SECURITY,
            start_time,
            end_time
        )
        
        return {
            "complexity": {
                "current": complexity_metrics[-1].avg if complexity_metrics else 0,
                "trend": self._calculate_trend(complexity_metrics),
                "distribution": self._get_distribution(complexity_metrics)
            },
            "maintainability": {
                "current": maintainability_metrics[-1].avg if maintainability_metrics else 0,
                "trend": self._calculate_trend(maintainability_metrics),
                "distribution": self._get_distribution(maintainability_metrics)
            },
            "security": {
                "current": security_metrics[-1].avg if security_metrics else 0,
                "trend": self._calculate_trend(security_metrics),
                "distribution": self._get_distribution(security_metrics)
            }
        }
    
    def get_performance_overview(self, 
                               hours: int = 24) -> Dict[str, Any]:
        """Obtiene resumen de rendimiento."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        analysis_time_metrics = self.db.get_metrics(
            "analysis_time",
            MetricType.PERFORMANCE,
            start_time,
            end_time
        )
        
        embedding_time_metrics = self.db.get_metrics(
            "embedding_generation_time",
            MetricType.PERFORMANCE,
            start_time,
            end_time
        )
        
        return {
            "analysis_time": {
                "current": analysis_time_metrics[-1].avg if analysis_time_metrics else 0,
                "trend": self._calculate_trend(analysis_time_metrics),
                "percentiles": analysis_time_metrics[-1].percentiles if analysis_time_metrics else None
            },
            "embedding_time": {
                "current": embedding_time_metrics[-1].avg if embedding_time_metrics else 0,
                "trend": self._calculate_trend(embedding_time_metrics),
                "percentiles": embedding_time_metrics[-1].percentiles if embedding_time_metrics else None
            }
        }
    
    def get_testing_overview(self, 
                           hours: int = 24) -> Dict[str, Any]:
        """Obtiene resumen de testing."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        success_rate_metrics = self.db.get_metrics(
            "test_success_rate",
            MetricType.TESTING,
            start_time,
            end_time
        )
        
        execution_time_metrics = self.db.get_metrics(
            "test_execution_time",
            MetricType.TESTING,
            start_time,
            end_time
        )
        
        return {
            "success_rate": {
                "current": success_rate_metrics[-1].avg if success_rate_metrics else 0,
                "trend": self._calculate_trend(success_rate_metrics),
                "distribution": self._get_distribution(success_rate_metrics)
            },
            "execution_time": {
                "current": execution_time_metrics[-1].avg if execution_time_metrics else 0,
                "trend": self._calculate_trend(execution_time_metrics),
                "percentiles": execution_time_metrics[-1].percentiles if execution_time_metrics else None
            }
        }
    
    def get_usage_overview(self, 
                         hours: int = 24) -> Dict[str, Any]:
        """Obtiene resumen de uso."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        command_usage_metrics = self.db.get_metrics(
            "command_usage",
            MetricType.USAGE,
            start_time,
            end_time
        )
        
        license_validation_metrics = self.db.get_metrics(
            "license_validation",
            MetricType.USAGE,
            start_time,
            end_time
        )
        
        return {
            "commands_executed": {
                "total": sum(m.count for m in command_usage_metrics),
                "successful": sum(m.sum for m in command_usage_metrics),
                "success_rate": self._calculate_average_success_rate(command_usage_metrics)
            },
            "license_validations": {
                "total": sum(m.count for m in license_validation_metrics),
                "successful": sum(m.sum for m in license_validation_metrics),
                "success_rate": self._calculate_average_success_rate(license_validation_metrics)
            }
        }
    
    def _calculate_trend(self, metrics: List[MetricAggregation]) -> str:
        """Calcula tendencia de métricas."""
        if len(metrics) < 2:
            return "stable"
        
        recent = metrics[-1].avg
        previous = metrics[-2].avg
        
        if recent > previous * 1.1:
            return "increasing"
        elif recent < previous * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def _get_distribution(self, metrics: List[MetricAggregation]) -> Dict[str, float]:
        """Obtiene distribución de métricas."""
        if not metrics:
            return {}
        
        latest = metrics[-1]
        return {
            "min": latest.min,
            "max": latest.max,
            "avg": latest.avg,
            "std": latest.std,
            "percentiles": latest.percentiles or {}
        }
    
    def _calculate_average_success_rate(self, metrics: List[MetricAggregation]) -> float:
        """Calcula tasa de éxito promedio."""
        if not metrics:
            return 0.0
        
        total_count = sum(m.count for m in metrics)
        total_success = sum(m.sum for m in metrics)
        
        return total_success / max(total_count, 1)
    
    def generate_report(self, 
                       hours: int = 24) -> Dict[str, Any]:
        """Genera reporte completo."""
        return {
            "timestamp": datetime.now().isoformat(),
            "period_hours": hours,
            "quality": self.get_quality_overview(hours),
            "performance": self.get_performance_overview(hours),
            "testing": self.get_testing_overview(hours),
            "usage": self.get_usage_overview(hours)
        }


# Instancia global del sistema de métricas
_metrics_db = None
_metrics_collector = None
_quality_metrics = None
_performance_metrics = None
_testing_metrics = None
_usage_metrics = None
_dashboard = None


def initialize_metrics(db_path: str = "metrics.db"):
    """Inicializa el sistema de métricas."""
    global _metrics_db, _metrics_collector, _quality_metrics, _performance_metrics, _testing_metrics, _usage_metrics, _dashboard
    
    _metrics_db = MetricsDatabase(db_path)
    _metrics_collector = MetricsCollector(_metrics_db)
    _quality_metrics = QualityMetrics(_metrics_collector)
    _performance_metrics = PerformanceMetrics(_metrics_collector)
    _testing_metrics = TestingMetrics(_metrics_collector)
    _usage_metrics = UsageMetrics(_metrics_collector)
    _dashboard = MetricsDashboard(_metrics_db)
    
    # Iniciar recolector
    _metrics_collector.start()
    
    logger.info("Sistema de métricas inicializado")


def get_quality_metrics() -> QualityMetrics:
    """Obtiene instancia de métricas de calidad."""
    return _quality_metrics


def get_performance_metrics() -> PerformanceMetrics:
    """Obtiene instancia de métricas de rendimiento."""
    return _performance_metrics


def get_testing_metrics() -> TestingMetrics:
    """Obtiene instancia de métricas de testing."""
    return _testing_metrics


def get_usage_metrics() -> UsageMetrics:
    """Obtiene instancia de métricas de uso."""
    return _usage_metrics


def get_dashboard() -> MetricsDashboard:
    """Obtiene instancia del dashboard."""
    return _dashboard


def shutdown_metrics():
    """Cierra el sistema de métricas."""
    global _metrics_collector
    if _metrics_collector:
        _metrics_collector.stop()
        logger.info("Sistema de métricas cerrado")
