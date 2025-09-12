"""
Sistema de Optimización de Rendimiento y Escalabilidad para MSC SRPK v2.0
Implementa caching, procesamiento paralelo, optimización de embeddings y escalabilidad.
"""

import asyncio
import concurrent.futures
import functools
import hashlib
import json
import logging
import os
import pickle
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import torch
from pathlib import Path
import multiprocessing as mp
from queue import Queue, Empty
import psutil
import gc

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Estrategias de caché."""
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    SIZE_LIMITED = "size_limited"


class TaskPriority(Enum):
    """Prioridades de tareas."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento."""
    operation: str
    start_time: float
    end_time: float
    duration: float
    memory_usage: float
    cpu_usage: float
    cache_hits: int = 0
    cache_misses: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """Tasa de acierto del caché."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / max(total, 1)


class LRUCache:
    """Cache LRU optimizado."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: Optional[int] = None):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, float, float]] = {}  # key -> (value, timestamp, access_time)
        self.access_order = deque()
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del caché."""
        with self._lock:
            if key not in self.cache:
                return None
            
            value, timestamp, _ = self.cache[key]
            now = time.time()
            
            # Verificar TTL
            if self.ttl_seconds and (now - timestamp) > self.ttl_seconds:
                self._remove(key)
                return None
            
            # Actualizar orden de acceso
            self.cache[key] = (value, timestamp, now)
            self._update_access_order(key)
            
            return value
    
    def set(self, key: str, value: Any):
        """Establece valor en el caché."""
        with self._lock:
            now = time.time()
            
            # Si la clave existe, actualizar
            if key in self.cache:
                self.cache[key] = (value, now, now)
                self._update_access_order(key)
                return
            
            # Si está lleno, eliminar el menos usado
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            # Agregar nueva entrada
            self.cache[key] = (value, now, now)
            self.access_order.append(key)
    
    def _remove(self, key: str):
        """Elimina entrada del caché."""
        if key in self.cache:
            del self.cache[key]
            try:
                self.access_order.remove(key)
            except ValueError:
                pass
    
    def _update_access_order(self, key: str):
        """Actualiza orden de acceso."""
        try:
            self.access_order.remove(key)
        except ValueError:
            pass
        self.access_order.append(key)
    
    def _evict_lru(self):
        """Elimina el elemento menos usado recientemente."""
        if self.access_order:
            lru_key = self.access_order.popleft()
            self._remove(lru_key)
    
    def clear(self):
        """Limpia el caché."""
        with self._lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        """Tamaño actual del caché."""
        return len(self.cache)
    
    def stats(self) -> Dict[str, Any]:
        """Estadísticas del caché."""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds
        }


class CacheManager:
    """Gestor de caché multicapa."""
    
    def __init__(self):
        self.caches = {
            "embeddings": LRUCache(max_size=500, ttl_seconds=3600),  # 1 hora
            "analysis": LRUCache(max_size=1000, ttl_seconds=1800),   # 30 minutos
            "metrics": LRUCache(max_size=2000, ttl_seconds=900),     # 15 minutos
            "licenses": LRUCache(max_size=100, ttl_seconds=7200)     # 2 horas
        }
        self.stats = defaultdict(lambda: {"hits": 0, "misses": 0})
    
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Obtiene valor del caché."""
        if cache_name not in self.caches:
            return None
        
        value = self.caches[cache_name].get(key)
        if value is not None:
            self.stats[cache_name]["hits"] += 1
        else:
            self.stats[cache_name]["misses"] += 1
        
        return value
    
    def set(self, cache_name: str, key: str, value: Any):
        """Establece valor en el caché."""
        if cache_name in self.caches:
            self.caches[cache_name].set(key, value)
    
    def invalidate(self, cache_name: str, pattern: Optional[str] = None):
        """Invalida caché."""
        if pattern:
            # Invalidar claves que coincidan con el patrón
            cache = self.caches.get(cache_name)
            if cache:
                keys_to_remove = [k for k in cache.cache.keys() if pattern in k]
                for key in keys_to_remove:
                    cache._remove(key)
        else:
            # Limpiar todo el caché
            if cache_name in self.caches:
                self.caches[cache_name].clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de todos los cachés."""
        stats = {}
        for name, cache in self.caches.items():
            stats[name] = {
                **cache.stats(),
                "hit_rate": self.stats[name]["hits"] / max(
                    self.stats[name]["hits"] + self.stats[name]["misses"], 1
                )
            }
        return stats


class TaskQueue:
    """Cola de tareas con prioridades."""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.task_queue = Queue()
        self.workers = []
        self.running = False
        self._lock = threading.Lock()
    
    def start(self):
        """Inicia los workers."""
        with self._lock:
            if not self.running:
                self.running = True
                for _ in range(self.max_workers):
                    worker = threading.Thread(target=self._worker_loop, daemon=True)
                    worker.start()
                    self.workers.append(worker)
    
    def stop(self):
        """Detiene los workers."""
        with self._lock:
            self.running = False
            # Enviar señales de parada
            for _ in self.workers:
                self.task_queue.put(None)
    
    def submit(self, func: Callable, args: Tuple = (), kwargs: Dict = None, 
               priority: TaskPriority = TaskPriority.MEDIUM) -> str:
        """Envía tarea a la cola."""
        task_id = f"task_{int(time.time() * 1000)}_{id(func)}"
        task = {
            "id": task_id,
            "func": func,
            "args": args,
            "kwargs": kwargs or {},
            "priority": priority,
            "created_at": time.time()
        }
        self.task_queue.put(task)
        return task_id
    
    def _worker_loop(self):
        """Loop principal del worker."""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:  # Señal de parada
                    break
                
                try:
                    # Ejecutar tarea
                    result = task["func"](*task["args"], **task["kwargs"])
                    logger.debug(f"Tarea {task['id']} completada")
                except Exception as e:
                    logger.error(f"Error en tarea {task['id']}: {e}")
                finally:
                    self.task_queue.task_done()
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error en worker: {e}")


class EmbeddingOptimizer:
    """Optimizador de embeddings."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.batch_size = 32
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_cache = {}
    
    def encode_batch(self, code_snippets: List[str], model_name: str = "microsoft/codebert-base") -> List[torch.Tensor]:
        """Codifica un lote de snippets de código."""
        # Verificar caché primero
        cache_keys = [self._get_cache_key(code, model_name) for code in code_snippets]
        cached_results = []
        uncached_indices = []
        
        for i, cache_key in enumerate(cache_keys):
            cached = self.cache.get("embeddings", cache_key)
            if cached is not None:
                cached_results.append((i, cached))
            else:
                uncached_indices.append(i)
        
        # Procesar snippets no cacheados
        if uncached_indices:
            uncached_snippets = [code_snippets[i] for i in uncached_indices]
            new_embeddings = self._encode_uncached(uncached_snippets, model_name)
            
            # Guardar en caché
            for i, embedding in zip(uncached_indices, new_embeddings):
                cache_key = cache_keys[i]
                self.cache.set("embeddings", cache_key, embedding)
                cached_results.append((i, embedding))
        
        # Ordenar resultados
        cached_results.sort(key=lambda x: x[0])
        return [result[1] for result in cached_results]
    
    def _encode_uncached(self, code_snippets: List[str], model_name: str) -> List[torch.Tensor]:
        """Codifica snippets no cacheados."""
        # En una implementación real, aquí cargarías el modelo
        # Por ahora, simulamos embeddings
        embeddings = []
        for code in code_snippets:
            # Simulación de embedding
            embedding = torch.randn(768)
            embeddings.append(embedding)
        return embeddings
    
    def _get_cache_key(self, code: str, model_name: str) -> str:
        """Genera clave de caché para código."""
        content_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        return f"{model_name}:{content_hash}"
    
    def optimize_model_loading(self, model_name: str):
        """Optimiza carga de modelos."""
        if model_name not in self.model_cache:
            # Simular carga de modelo
            self.model_cache[model_name] = f"loaded_model_{model_name}"
            logger.info(f"Modelo {model_name} cargado y cacheado")


class MemoryManager:
    """Gestor de memoria optimizado."""
    
    def __init__(self):
        self.memory_threshold = 0.8  # 80% de memoria
        self.cleanup_interval = 300  # 5 minutos
        self.last_cleanup = time.time()
    
    def check_memory_usage(self) -> float:
        """Verifica uso de memoria."""
        return psutil.virtual_memory().percent / 100
    
    def should_cleanup(self) -> bool:
        """Determina si se debe limpiar memoria."""
        memory_usage = self.check_memory_usage()
        time_since_cleanup = time.time() - self.last_cleanup
        
        return (memory_usage > self.memory_threshold or 
                time_since_cleanup > self.cleanup_interval)
    
    def cleanup_memory(self):
        """Limpia memoria."""
        logger.info("Iniciando limpieza de memoria")
        
        # Forzar garbage collection
        gc.collect()
        
        # Limpiar caché de PyTorch si está disponible
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        self.last_cleanup = time.time()
        logger.info(f"Limpieza completada. Memoria disponible: {psutil.virtual_memory().percent}%")


class PerformanceProfiler:
    """Profiler de rendimiento."""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.active_profiles: Dict[str, Dict] = {}
    
    def start_profile(self, operation: str) -> str:
        """Inicia perfilado de operación."""
        profile_id = f"{operation}_{int(time.time() * 1000)}"
        
        self.active_profiles[profile_id] = {
            "operation": operation,
            "start_time": time.time(),
            "start_memory": psutil.Process().memory_info().rss / 1024 / 1024,  # MB
            "start_cpu": psutil.Process().cpu_percent()
        }
        
        return profile_id
    
    def end_profile(self, profile_id: str, cache_hits: int = 0, cache_misses: int = 0):
        """Termina perfilado de operación."""
        if profile_id not in self.active_profiles:
            return
        
        profile_data = self.active_profiles.pop(profile_id)
        end_time = time.time()
        
        metrics = PerformanceMetrics(
            operation=profile_data["operation"],
            start_time=profile_data["start_time"],
            end_time=end_time,
            duration=end_time - profile_data["start_time"],
            memory_usage=psutil.Process().memory_info().rss / 1024 / 1024 - profile_data["start_memory"],
            cpu_usage=psutil.Process().cpu_percent() - profile_data["start_cpu"],
            cache_hits=cache_hits,
            cache_misses=cache_misses
        )
        
        self.metrics.append(metrics)
        
        # Mantener solo las últimas 1000 métricas
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de rendimiento."""
        if not self.metrics:
            return {}
        
        operations = defaultdict(list)
        for metric in self.metrics:
            operations[metric.operation].append(metric)
        
        summary = {}
        for operation, metrics_list in operations.items():
            durations = [m.duration for m in metrics_list]
            memory_usage = [m.memory_usage for m in metrics_list]
            
            summary[operation] = {
                "count": len(metrics_list),
                "avg_duration": np.mean(durations),
                "max_duration": np.max(durations),
                "min_duration": np.min(durations),
                "avg_memory": np.mean(memory_usage),
                "avg_cache_hit_rate": np.mean([m.cache_hit_rate for m in metrics_list])
            }
        
        return summary


class ScalabilityManager:
    """Gestor de escalabilidad."""
    
    def __init__(self):
        self.load_balancers = {}
        self.auto_scaling_enabled = True
        self.max_instances = 10
        self.min_instances = 2
        self.scale_up_threshold = 0.8
        self.scale_down_threshold = 0.3
    
    def check_scaling_needs(self, current_load: float, active_instances: int) -> str:
        """Verifica necesidades de escalado."""
        if not self.auto_scaling_enabled:
            return "disabled"
        
        if current_load > self.scale_up_threshold and active_instances < self.max_instances:
            return "scale_up"
        elif current_load < self.scale_down_threshold and active_instances > self.min_instances:
            return "scale_down"
        else:
            return "no_change"
    
    def get_optimal_batch_size(self, available_memory: float, model_size: float) -> int:
        """Calcula tamaño óptimo de lote."""
        # Estimación basada en memoria disponible
        estimated_batch_size = int((available_memory * 0.7) / model_size)
        return max(1, min(estimated_batch_size, 64))  # Entre 1 y 64


# Decoradores de optimización
def cached(cache_name: str, ttl_seconds: Optional[int] = None):
    """Decorador para caché de funciones."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de caché
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Verificar caché
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get(cache_name, cache_key)
            
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función
            result = func(*args, **kwargs)
            
            # Guardar en caché
            cache_manager.set(cache_name, cache_key, result)
            
            return result
        return wrapper
    return decorator


def profile_performance(operation_name: str):
    """Decorador para perfilado de rendimiento."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = get_performance_profiler()
            profile_id = profiler.start_profile(operation_name)
            
            try:
                result = func(*args, **kwargs)
                profiler.end_profile(profile_id)
                return result
            except Exception as e:
                profiler.end_profile(profile_id)
                raise
        return wrapper
    return decorator


def async_batch_process(batch_size: int = 32):
    """Decorador para procesamiento por lotes asíncrono."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(items: List[Any], *args, **kwargs):
            results = []
            
            # Procesar en lotes
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                batch_results = await asyncio.gather(*[
                    func(item, *args, **kwargs) for item in batch
                ])
                results.extend(batch_results)
            
            return results
        return wrapper
    return decorator


# Instancias globales
_cache_manager = None
_task_queue = None
_embedding_optimizer = None
_memory_manager = None
_performance_profiler = None
_scalability_manager = None


def initialize_performance():
    """Inicializa el sistema de rendimiento."""
    global _cache_manager, _task_queue, _embedding_optimizer, _memory_manager, _performance_profiler, _scalability_manager
    
    _cache_manager = CacheManager()
    _task_queue = TaskQueue()
    _embedding_optimizer = EmbeddingOptimizer(_cache_manager)
    _memory_manager = MemoryManager()
    _performance_profiler = PerformanceProfiler()
    _scalability_manager = ScalabilityManager()
    
    # Iniciar task queue
    _task_queue.start()
    
    logger.info("Sistema de rendimiento inicializado")


def get_cache_manager() -> CacheManager:
    """Obtiene el gestor de caché."""
    return _cache_manager


def get_task_queue() -> TaskQueue:
    """Obtiene la cola de tareas."""
    return _task_queue


def get_embedding_optimizer() -> EmbeddingOptimizer:
    """Obtiene el optimizador de embeddings."""
    return _embedding_optimizer


def get_memory_manager() -> MemoryManager:
    """Obtiene el gestor de memoria."""
    return _memory_manager


def get_performance_profiler() -> PerformanceProfiler:
    """Obtiene el profiler de rendimiento."""
    return _performance_profiler


def get_scalability_manager() -> ScalabilityManager:
    """Obtiene el gestor de escalabilidad."""
    return _scalability_manager


def cleanup_resources():
    """Limpia recursos del sistema."""
    if _task_queue:
        _task_queue.stop()
    
    if _memory_manager:
        _memory_manager.cleanup_memory()
    
    logger.info("Recursos limpiados")
