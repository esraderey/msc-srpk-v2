"""
MSC SRPK (Self-Referencing Proprietary Knowledge) Graph v2.0
Sistema avanzado de análisis, gestión y actualización de código Python
con testing real y embeddings semánticos.

Mejoras en v2:
- Integración con pytest y unittest para testing real
- Uso de modelos de embeddings reales para código (CodeBERT/GraphCodeBERT)
- Análisis de complejidad ciclomática
- Detección de patrones de diseño
- Análisis de seguridad básico
- Métricas de calidad de código
"""

import inspect
import ast
import re
import logging
import hashlib
import json
import os
import time
import torch
import torch.nn as nn
from torch.nn import functional as F
import numpy as np
from collections import defaultdict
import subprocess
import tempfile
import importlib.util
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import warnings
from contextlib import contextmanager

# Intentar importar transformers para modelos de embeddings reales
try:
    from transformers import AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    warnings.warn("transformers library not available. Using fallback embedding model.")

# Intentar importar herramientas de testing
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    warnings.warn("pytest not available. Test execution will be limited.")

try:
    import unittest
    UNITTEST_AVAILABLE = True
except ImportError:
    UNITTEST_AVAILABLE = False
    warnings.warn("unittest not available. Test execution will be limited.")

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importar métricas si están disponibles
try:
    from .metrics import (
        initialize_metrics, get_quality_metrics, get_performance_metrics,
        get_testing_metrics, get_usage_metrics, MetricType
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Sistema de métricas no disponible")


@contextmanager
def track_performance(operation_name: str, metadata: Dict[str, Any] = None):
    """Context manager para trackear rendimiento."""
    if not METRICS_AVAILABLE:
        yield
        return
    
    start_time = time.time()
    try:
        yield
    finally:
        execution_time = time.time() - start_time
        try:
            performance_metrics = get_performance_metrics()
            if performance_metrics:
                performance_metrics.collector.record_metric(
                    MetricType.PERFORMANCE,
                    f"{operation_name}_time",
                    execution_time,
                    metadata=metadata or {}
                )
        except Exception as e:
            logger.debug(f"Error registrando métricas de rendimiento: {e}")


class TestFramework(Enum):
    """Enumeración de frameworks de testing soportados."""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    DOCTEST = "doctest"
    CUSTOM = "custom"


@dataclass
class TestResult:
    """Resultado de una prueba ejecutada."""
    test_name: str
    passed: bool
    execution_time: float
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    coverage: Optional[float] = None


@dataclass
class CodeMetrics:
    """Métricas de calidad de código."""
    cyclomatic_complexity: int
    lines_of_code: int
    comment_ratio: float
    maintainability_index: float
    cognitive_complexity: int
    security_issues: List[str] = field(default_factory=list)
    code_smells: List[str] = field(default_factory=list)


class CodeEmbeddingModel:
    """Modelo de embeddings para código usando CodeBERT o alternativas."""
    
    def __init__(self, model_name: str = "microsoft/codebert-base"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.embedding_dim = 768
        
        if TRANSFORMERS_AVAILABLE:
            try:
                logger.info(f"Loading embedding model: {model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModel.from_pretrained(model_name).to(self.device)
                self.model.eval()
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load transformer model: {e}")
                self._init_fallback_model()
        else:
            self._init_fallback_model()
    
    def _init_fallback_model(self):
        """Inicializa un modelo de embeddings alternativo más simple."""
        logger.info("Using fallback embedding model")
        
        class SimpleCodeEmbedder(nn.Module):
            def __init__(self, vocab_size=10000, embedding_dim=768):
                super().__init__()
                self.embedding = nn.Embedding(vocab_size, embedding_dim)
                self.lstm = nn.LSTM(embedding_dim, embedding_dim // 2, 
                                   bidirectional=True, batch_first=True)
                self.pooling = nn.AdaptiveAvgPool1d(1)
            
            def forward(self, input_ids):
                x = self.embedding(input_ids)
                x, _ = self.lstm(x)
                x = x.transpose(1, 2)
                x = self.pooling(x).squeeze(-1)
                return x
        
        self.model = SimpleCodeEmbedder().to(self.device)
        self.tokenizer = self._simple_tokenizer
    
    def _simple_tokenizer(self, text: str) -> Dict[str, torch.Tensor]:
        """Tokenizador simple para el modelo alternativo."""
        # Tokenización básica basada en caracteres y palabras
        tokens = re.findall(r'\w+|\W', text[:512])  # Limitar longitud
        token_ids = [hash(token) % 10000 for token in tokens]
        return {
            'input_ids': torch.tensor([token_ids], device=self.device)
        }
    
    def encode(self, code: str) -> torch.Tensor:
        """Genera embedding para un fragmento de código."""
        try:
            with torch.no_grad():
                if self.tokenizer == self._simple_tokenizer:
                    inputs = self.tokenizer(code)
                else:
                    inputs = self.tokenizer(code, return_tensors="pt", 
                                          max_length=512, truncation=True, 
                                          padding=True).to(self.device)
                
                if hasattr(self.model, 'forward'):
                    outputs = self.model(**inputs)
                    if hasattr(outputs, 'last_hidden_state'):
                        # Para modelos transformer
                        embedding = outputs.last_hidden_state.mean(dim=1)
                    else:
                        # Para nuestro modelo simple
                        embedding = outputs
                else:
                    # Fallback final
                    embedding = torch.randn(1, self.embedding_dim, device=self.device)
                
                return embedding.cpu().squeeze(0)
        
        except Exception as e:
            logger.error(f"Error encoding code: {e}")
            return torch.randn(self.embedding_dim)


class TestRunner:
    """Ejecutor de pruebas con soporte para múltiples frameworks."""
    
    def __init__(self):
        self.supported_frameworks = []
        if PYTEST_AVAILABLE:
            self.supported_frameworks.append(TestFramework.PYTEST)
        if UNITTEST_AVAILABLE:
            self.supported_frameworks.append(TestFramework.UNITTEST)
        self.supported_frameworks.append(TestFramework.DOCTEST)
        self.supported_frameworks.append(TestFramework.CUSTOM)
    
    def run_tests(self, code: str, test_cases: List[Dict], 
                  framework: TestFramework = TestFramework.PYTEST) -> List[TestResult]:
        """Ejecuta pruebas para un fragmento de código."""
        if framework == TestFramework.PYTEST and PYTEST_AVAILABLE:
            return self._run_pytest(code, test_cases)
        elif framework == TestFramework.UNITTEST and UNITTEST_AVAILABLE:
            return self._run_unittest(code, test_cases)
        elif framework == TestFramework.DOCTEST:
            return self._run_doctest(code)
        else:
            return self._run_custom_tests(code, test_cases)
    
    def _run_pytest(self, code: str, test_cases: List[Dict]) -> List[TestResult]:
        """Ejecuta pruebas usando pytest."""
        results = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Escribir el código a probar
            code_file = os.path.join(tmpdir, "code_to_test.py")
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Escribir las pruebas
            test_file = os.path.join(tmpdir, "test_code.py")
            with open(test_file, 'w') as f:
                f.write("import sys\n")
                f.write(f"sys.path.insert(0, '{tmpdir}')\n")
                f.write("from code_to_test import *\n\n")
                
                for i, test_case in enumerate(test_cases):
                    test_name = f"test_{i}_{test_case.get('description', 'case').replace(' ', '_')}"
                    f.write(f"def {test_name}():\n")
                    f.write(f"    {test_case.get('test_code', 'pass')}\n\n")
            
            # Ejecutar pytest
            try:
                start_time = time.time()
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                    capture_output=True, text=True, timeout=30
                )
                execution_time = time.time() - start_time
                
                # Parsear resultados
                if result.returncode == 0:
                    for test_case in test_cases:
                        results.append(TestResult(
                            test_name=test_case.get('description', 'test'),
                            passed=True,
                            execution_time=execution_time / len(test_cases)
                        ))
                else:
                    # Parsear errores
                    error_lines = result.stdout.split('\n') + result.stderr.split('\n')
                    for test_case in test_cases:
                        results.append(TestResult(
                            test_name=test_case.get('description', 'test'),
                            passed=False,
                            execution_time=execution_time / len(test_cases),
                            error_message="Test failed",
                            stack_trace='\n'.join(error_lines[-20:])  # Últimas 20 líneas
                        ))
            
            except subprocess.TimeoutExpired:
                for test_case in test_cases:
                    results.append(TestResult(
                        test_name=test_case.get('description', 'test'),
                        passed=False,
                        execution_time=30.0,
                        error_message="Test timeout"
                    ))
            except Exception as e:
                for test_case in test_cases:
                    results.append(TestResult(
                        test_name=test_case.get('description', 'test'),
                        passed=False,
                        execution_time=0.0,
                        error_message=str(e)
                    ))
        
        return results
    
    def _run_unittest(self, code: str, test_cases: List[Dict]) -> List[TestResult]:
        """Ejecuta pruebas usando unittest."""
        results = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Escribir el código
            code_file = os.path.join(tmpdir, "code_to_test.py")
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Escribir pruebas unittest
            test_file = os.path.join(tmpdir, "test_unittest.py")
            with open(test_file, 'w') as f:
                f.write("import unittest\n")
                f.write("import sys\n")
                f.write(f"sys.path.insert(0, '{tmpdir}')\n")
                f.write("from code_to_test import *\n\n")
                f.write("class TestCode(unittest.TestCase):\n")
                
                for i, test_case in enumerate(test_cases):
                    test_name = f"test_{i}_{test_case.get('description', 'case').replace(' ', '_')}"
                    f.write(f"    def {test_name}(self):\n")
                    f.write(f"        {test_case.get('test_code', 'pass')}\n\n")
                
                f.write("if __name__ == '__main__':\n")
                f.write("    unittest.main()\n")
            
            # Ejecutar unittest
            try:
                start_time = time.time()
                result = subprocess.run(
                    [sys.executable, test_file],
                    capture_output=True, text=True, timeout=30
                )
                execution_time = time.time() - start_time
                
                # Parsear resultados
                output = result.stdout + result.stderr
                for test_case in test_cases:
                    passed = "OK" in output or result.returncode == 0
                    results.append(TestResult(
                        test_name=test_case.get('description', 'test'),
                        passed=passed,
                        execution_time=execution_time / len(test_cases),
                        error_message=None if passed else "Test failed",
                        stack_trace=output if not passed else None
                    ))
            
            except Exception as e:
                for test_case in test_cases:
                    results.append(TestResult(
                        test_name=test_case.get('description', 'test'),
                        passed=False,
                        execution_time=0.0,
                        error_message=str(e)
                    ))
        
        return results
    
    def _run_doctest(self, code: str) -> List[TestResult]:
        """Ejecuta doctests en el código."""
        import doctest
        results = []
        
        try:
            # Crear un módulo temporal
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Cargar el módulo
            spec = importlib.util.spec_from_file_location("temp_module", temp_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Ejecutar doctests
            start_time = time.time()
            test_results = doctest.testmod(module, verbose=False)
            execution_time = time.time() - start_time
            
            results.append(TestResult(
                test_name="doctests",
                passed=(test_results.failed == 0),
                execution_time=execution_time,
                error_message=f"{test_results.failed} tests failed" if test_results.failed > 0 else None
            ))
            
            os.unlink(temp_file)
        
        except Exception as e:
            results.append(TestResult(
                test_name="doctests",
                passed=False,
                execution_time=0.0,
                error_message=str(e)
            ))
        
        return results
    
    def _run_custom_tests(self, code: str, test_cases: List[Dict]) -> List[TestResult]:
        """Ejecuta pruebas personalizadas usando eval (con precaución)."""
        results = []
        
        # Crear un namespace seguro para ejecutar el código
        safe_namespace = {
            '__builtins__': {
                'print': print,
                'len': len,
                'range': range,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'bool': bool,
                'True': True,
                'False': False,
                'None': None,
            }
        }
        
        try:
            # Ejecutar el código en el namespace seguro
            exec(code, safe_namespace)
            
            for test_case in test_cases:
                try:
                    start_time = time.time()
                    
                    # Preparar input
                    if 'input' in test_case:
                        for key, value in test_case['input'].items():
                            safe_namespace[key] = value
                    
                    # Ejecutar el test
                    if 'test_code' in test_case:
                        exec(test_case['test_code'], safe_namespace)
                        result = safe_namespace.get('result', None)
                    else:
                        result = None
                    
                    execution_time = time.time() - start_time
                    
                    # Verificar resultado esperado
                    expected = test_case.get('expected_output')
                    passed = (result == expected) if expected is not None else True
                    
                    results.append(TestResult(
                        test_name=test_case.get('description', 'custom test'),
                        passed=passed,
                        execution_time=execution_time,
                        error_message=None if passed else f"Expected {expected}, got {result}"
                    ))
                
                except Exception as e:
                    results.append(TestResult(
                        test_name=test_case.get('description', 'custom test'),
                        passed=False,
                        execution_time=0.0,
                        error_message=str(e)
                    ))
        
        except Exception as e:
            for test_case in test_cases:
                results.append(TestResult(
                    test_name=test_case.get('description', 'custom test'),
                    passed=False,
                    execution_time=0.0,
                    error_message=f"Code execution failed: {e}"
                ))
        
        return results


class CodeAnalyzer:
    """Analizador avanzado de código para métricas de calidad."""
    
    @staticmethod
    def calculate_cyclomatic_complexity(code: str) -> int:
        """Calcula la complejidad ciclomática del código."""
        try:
            tree = ast.parse(code)
            complexity = 1  # Base complexity
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            return complexity
        except:
            return 0
    
    @staticmethod
    def calculate_cognitive_complexity(code: str) -> int:
        """Calcula la complejidad cognitiva (más precisa que ciclomática)."""
        try:
            tree = ast.parse(code)
            
            class ComplexityVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.complexity = 0
                    self.nesting_level = 0
                
                def visit_If(self, node):
                    self.complexity += 1 + self.nesting_level
                    self.nesting_level += 1
                    self.generic_visit(node)
                    self.nesting_level -= 1
                
                def visit_While(self, node):
                    self.complexity += 1 + self.nesting_level
                    self.nesting_level += 1
                    self.generic_visit(node)
                    self.nesting_level -= 1
                
                def visit_For(self, node):
                    self.complexity += 1 + self.nesting_level
                    self.nesting_level += 1
                    self.generic_visit(node)
                    self.nesting_level -= 1
                
                def visit_ExceptHandler(self, node):
                    self.complexity += 1 + self.nesting_level
                    self.nesting_level += 1
                    self.generic_visit(node)
                    self.nesting_level -= 1
                
                def visit_BoolOp(self, node):
                    self.complexity += len(node.values) - 1
                    self.generic_visit(node)
            
            visitor = ComplexityVisitor()
            visitor.visit(tree)
            return visitor.complexity
        
        except:
            return 0
    
    @staticmethod
    def detect_security_issues(code: str) -> List[str]:
        """Detecta problemas de seguridad comunes en el código."""
        issues = []
        
        security_patterns = [
            (r'\beval\s*\(', "Use of eval() is dangerous"),
            (r'\bexec\s*\(', "Use of exec() is dangerous"),
            (r'pickle\.loads?\s*\(', "Pickle deserialization can be unsafe"),
            (r'subprocess\.\w+\(.*shell=True', "Shell injection vulnerability possible"),
            (r'os\.system\s*\(', "os.system() can be vulnerable to injection"),
            (r'__import__\s*\(', "Dynamic imports can be risky"),
            (r'(password|secret|token|key)\s*=\s*["\'].*["\']', "Hardcoded credentials detected"),
            (r'http://', "Using HTTP instead of HTTPS"),
            (r'\.format\(.*request\.|f["\'].*request\.', "Possible format string vulnerability"),
        ]
        
        for pattern, message in security_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(message)
        
        return issues
    
    @staticmethod
    def detect_code_smells(code: str) -> List[str]:
        """Detecta code smells comunes."""
        smells = []
        
        try:
            tree = ast.parse(code)
            
            # Detectar funciones muy largas
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if len(node.body) > 50:
                        smells.append(f"Function '{node.name}' is too long ({len(node.body)} lines)")
                    
                    # Detectar demasiados parámetros
                    if len(node.args.args) > 5:
                        smells.append(f"Function '{node.name}' has too many parameters ({len(node.args.args)})")
            
            # Detectar clases muy grandes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                    if len(methods) > 20:
                        smells.append(f"Class '{node.name}' has too many methods ({len(methods)})")
            
            # Detectar imports no utilizados (simplificado)
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
            
            # Verificar uso básico
            code_without_imports = re.sub(r'^(import|from).*$', '', code, flags=re.MULTILINE)
            for imp in imports:
                if imp not in code_without_imports:
                    smells.append(f"Possibly unused import: {imp}")
        
        except:
            pass
        
        # Detectar código duplicado (muy básico)
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if len(line.strip()) > 20:  # Solo líneas significativas
                count = lines.count(line)
                if count > 2:
                    smells.append(f"Duplicated code detected at line {i+1}")
                    break
        
        return smells
    
    @staticmethod
    def analyze_code(code: str) -> CodeMetrics:
        """Análisis completo del código."""
        lines = code.split('\n')
        loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
        comments = len([l for l in lines if l.strip().startswith('#')])
        comment_ratio = comments / max(len(lines), 1)
        
        cyclomatic = CodeAnalyzer.calculate_cyclomatic_complexity(code)
        cognitive = CodeAnalyzer.calculate_cognitive_complexity(code)
        
        # Índice de mantenibilidad (simplificado)
        # MI = 171 - 5.2 * ln(HV) - 0.23 * CC - 16.2 * ln(LOC)
        import math
        mi = max(0, min(100, 171 - 5.2 * math.log(max(cyclomatic, 1)) - 
                       0.23 * cyclomatic - 16.2 * math.log(max(loc, 1))))
        
        return CodeMetrics(
            cyclomatic_complexity=cyclomatic,
            lines_of_code=loc,
            comment_ratio=comment_ratio,
            maintainability_index=mi,
            cognitive_complexity=cognitive,
            security_issues=CodeAnalyzer.detect_security_issues(code),
            code_smells=CodeAnalyzer.detect_code_smells(code)
        )


class EnhancedCodeKnowledgeNode:
    """Nodo mejorado que representa conocimiento sobre una parte del código."""
    
    def __init__(self, code_id: str, code_segment: str, 
                 dependencies: Optional[List[str]] = None,
                 purpose: Optional[str] = None,
                 test_cases: Optional[List[Dict]] = None):
        self.code_id = code_id
        self.code_segment = code_segment
        self.code_hash = hashlib.sha256(code_segment.encode()).hexdigest()
        self.dependencies = dependencies or []
        self.purpose = purpose or "No documented purpose"
        self.test_cases = test_cases or []
        self.creation_timestamp = time.time()
        self.update_timestamp = time.time()
        self.functional_state = 1.0
        self.change_history = []
        
        # Nuevos campos para v2
        self.metrics = CodeAnalyzer.analyze_code(code_segment)
        self.test_results: List[TestResult] = []
        self.last_test_run: Optional[float] = None
        self.test_coverage: float = 0.0
        self.embedding: Optional[torch.Tensor] = None
        self.design_patterns: List[str] = []
        self.documentation_score: float = 0.0
    
    def update_code(self, new_code_segment: str, reason: str = "") -> bool:
        """Actualiza el código preservando el historial."""
        old_hash = self.code_hash
        self.change_history.append({
            "old_hash": old_hash,
            "old_code": self.code_segment,
            "old_metrics": self.metrics,
            "timestamp": time.time(),
            "reason": reason
        })
        
        self.code_segment = new_code_segment
        self.code_hash = hashlib.sha256(new_code_segment.encode()).hexdigest()
        self.update_timestamp = time.time()
        
        # Recalcular métricas
        self.metrics = CodeAnalyzer.analyze_code(new_code_segment)
        
        # Invalidar resultados de pruebas
        self.test_results = []
        self.last_test_run = None
        
        return old_hash != self.code_hash
    
    def run_tests(self, test_runner: TestRunner, 
                  framework: TestFramework = TestFramework.PYTEST) -> List[TestResult]:
        """Ejecuta las pruebas asociadas a este nodo."""
        if not self.test_cases:
            return []
        
        self.test_results = test_runner.run_tests(
            self.code_segment, self.test_cases, framework
        )
        self.last_test_run = time.time()
        
        # Calcular cobertura básica
        passed = sum(1 for r in self.test_results if r.passed)
        self.test_coverage = passed / len(self.test_results) if self.test_results else 0.0
        
        # Actualizar estado funcional basado en pruebas
        self.functional_state = self.test_coverage
        
        return self.test_results
    
    def calculate_documentation_score(self) -> float:
        """Calcula un score de documentación del código."""
        score = 0.0
        
        # Verificar docstrings
        try:
            tree = ast.parse(self.code_segment)
            total_functions = 0
            documented_functions = 0
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    total_functions += 1
                    if ast.get_docstring(node):
                        documented_functions += 1
            
            if total_functions > 0:
                score = documented_functions / total_functions
        except:
            pass
        
        # Ajustar por ratio de comentarios
        score = (score + self.metrics.comment_ratio) / 2
        
        self.documentation_score = min(1.0, score)
        return self.documentation_score
    
    def detect_design_patterns(self) -> List[str]:
        """Detecta patrones de diseño en el código."""
        patterns = []
        
        try:
            tree = ast.parse(self.code_segment)
            
            # Detectar Singleton
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    has_instance = any(
                        isinstance(n, ast.Assign) and 
                        any(t.id == '_instance' for t in n.targets if hasattr(t, 'id'))
                        for n in node.body
                    )
                    has_new = any(
                        isinstance(n, ast.FunctionDef) and n.name == '__new__'
                        for n in node.body
                    )
                    if has_instance or has_new:
                        patterns.append("Singleton")
            
            # Detectar Factory
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if 'create' in node.name.lower() or 'factory' in node.name.lower():
                        patterns.append("Factory")
                        break
            
            # Detectar Observer (buscar subscribe/notify)
            code_lower = self.code_segment.lower()
            if 'subscribe' in code_lower or 'observer' in code_lower or 'notify' in code_lower:
                patterns.append("Observer")
            
            # Detectar Decorator
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.decorator_list:
                    patterns.append("Decorator")
                    break
        
        except:
            pass
        
        self.design_patterns = list(set(patterns))
        return self.design_patterns
    
    def to_json(self) -> Dict[str, Any]:
        """Convierte el nodo a formato JSON."""
        return {
            "code_id": self.code_id,
            "code_hash": self.code_hash,
            "dependencies": self.dependencies,
            "purpose": self.purpose,
            "creation_timestamp": self.creation_timestamp,
            "update_timestamp": self.update_timestamp,
            "functional_state": self.functional_state,
            "test_cases": self.test_cases,
            "change_history_count": len(self.change_history),
            "metrics": {
                "cyclomatic_complexity": self.metrics.cyclomatic_complexity,
                "lines_of_code": self.metrics.lines_of_code,
                "comment_ratio": self.metrics.comment_ratio,
                "maintainability_index": self.metrics.maintainability_index,
                "cognitive_complexity": self.metrics.cognitive_complexity,
                "security_issues": self.metrics.security_issues,
                "code_smells": self.metrics.code_smells
            },
            "test_coverage": self.test_coverage,
            "last_test_run": self.last_test_run,
            "documentation_score": self.documentation_score,
            "design_patterns": self.design_patterns
        }


class EnhancedSRPKGraph:
    """Grafo mejorado de conocimiento sobre el código del MSC Framework."""
    
    def __init__(self):
        self.nodes: Dict[str, EnhancedCodeKnowledgeNode] = {}
        self.function_map: Dict[str, str] = {}
        self.class_map: Dict[str, str] = {}
        self.module_map: Dict[str, List[str]] = defaultdict(list)
        self.impact_map: Dict[str, List[str]] = defaultdict(list)
        
        # Componentes v2
        self.embedding_model = CodeEmbeddingModel()
        self.test_runner = TestRunner()
        self.code_embeddings: Dict[str, torch.Tensor] = {}
        
        # Métricas globales
        self.global_metrics = {
            "total_nodes": 0,
            "total_loc": 0,
            "average_complexity": 0.0,
            "average_maintainability": 0.0,
            "total_security_issues": 0,
            "test_coverage": 0.0
        }
    
    def analyze_code_file(self, file_path: str) -> int:
        """Analiza un archivo de código y extrae nodos de conocimiento."""
        with track_performance("file_analysis", {"file_path": file_path}):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                # Crear nodo para el archivo
                file_id = f"file:{os.path.basename(file_path)}"
                file_node = EnhancedCodeKnowledgeNode(
                    code_id=file_id,
                    code_segment=content,
                    purpose=f"File: {file_path}"
                )
                
                # Generar embedding
                file_node.embedding = self.embedding_model.encode(content)
                self.code_embeddings[file_id] = file_node.embedding
                
                # Detectar patrones de diseño
                file_node.detect_design_patterns()
                
                # Calcular score de documentación
                file_node.calculate_documentation_score()
                
                self.nodes[file_id] = file_node
                
                # Extraer clases y funciones
                nodes_created = 1
                nodes_created += self._extract_classes(tree, content, file_id, file_path)
                nodes_created += self._extract_functions(tree, content, file_id, file_path)
                
                # Analizar dependencias
                self._analyze_function_dependencies()
                
                # Actualizar métricas globales
                self._update_global_metrics()
                
                logger.info(f"Analyzed {file_path}: {nodes_created} nodes created")
                return nodes_created
            
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {e}")
                return 0
    
    def _extract_classes(self, tree: ast.AST, content: str, 
                        file_id: str, file_path: str) -> int:
        """Extrae clases del AST."""
        nodes_created = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                try:
                    class_code = ast.get_source_segment(content, node)
                    class_id = f"class:{node.name}"
                    
                    class_node = EnhancedCodeKnowledgeNode(
                        code_id=class_id,
                        code_segment=class_code,
                        dependencies=[file_id],
                        purpose=f"Class: {node.name}"
                    )
                    
                    # Generar embedding
                    class_node.embedding = self.embedding_model.encode(class_code)
                    self.code_embeddings[class_id] = class_node.embedding
                    
                    # Análisis adicional
                    class_node.detect_design_patterns()
                    class_node.calculate_documentation_score()
                    
                    self.nodes[class_id] = class_node
                    self.class_map[node.name] = class_id
                    
                    module_name = os.path.basename(file_path).replace('.py', '')
                    self.module_map[module_name].append(class_id)
                    self.impact_map[file_id].append(class_id)
                    
                    nodes_created += 1
                    
                    # Extraer métodos de la clase
                    nodes_created += self._extract_methods(node, content, class_id)
                
                except Exception as e:
                    logger.error(f"Error extracting class {node.name}: {e}")
        
        return nodes_created
    
    def _extract_methods(self, class_node: ast.ClassDef, content: str, 
                        class_id: str) -> int:
        """Extrae métodos de una clase."""
        nodes_created = 0
        
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                try:
                    method_code = ast.get_source_segment(content, node)
                    method_id = f"method:{class_node.name}.{node.name}"
                    
                    method_node = EnhancedCodeKnowledgeNode(
                        code_id=method_id,
                        code_segment=method_code,
                        dependencies=[class_id],
                        purpose=f"Method: {class_node.name}.{node.name}"
                    )
                    
                    # Generar embedding
                    method_node.embedding = self.embedding_model.encode(method_code)
                    self.code_embeddings[method_id] = method_node.embedding
                    
                    self.nodes[method_id] = method_node
                    self.function_map[f"{class_node.name}.{node.name}"] = method_id
                    self.impact_map[class_id].append(method_id)
                    
                    nodes_created += 1
                
                except Exception as e:
                    logger.error(f"Error extracting method {node.name}: {e}")
        
        return nodes_created
    
    def _extract_functions(self, tree: ast.AST, content: str, 
                          file_id: str, file_path: str) -> int:
        """Extrae funciones standalone del AST."""
        nodes_created = 0
        
        # Encontrar funciones que no están dentro de clases
        module_body = tree.body if hasattr(tree, 'body') else []
        
        for node in module_body:
            if isinstance(node, ast.FunctionDef):
                try:
                    func_code = ast.get_source_segment(content, node)
                    func_id = f"func:{node.name}"
                    
                    func_node = EnhancedCodeKnowledgeNode(
                        code_id=func_id,
                        code_segment=func_code,
                        dependencies=[file_id],
                        purpose=f"Function: {node.name}"
                    )
                    
                    # Generar embedding
                    func_node.embedding = self.embedding_model.encode(func_code)
                    self.code_embeddings[func_id] = func_node.embedding
                    
                    # Análisis adicional
                    func_node.calculate_documentation_score()
                    
                    self.nodes[func_id] = func_node
                    self.function_map[node.name] = func_id
                    
                    module_name = os.path.basename(file_path).replace('.py', '')
                    self.module_map[module_name].append(func_id)
                    self.impact_map[file_id].append(func_id)
                    
                    nodes_created += 1
                
                except Exception as e:
                    logger.error(f"Error extracting function {node.name}: {e}")
        
        return nodes_created
    
    def _analyze_function_dependencies(self):
        """Analiza las dependencias entre funciones basado en llamadas."""
        function_names = set(self.function_map.keys())
        
        for func_id, func_node in self.nodes.items():
            if not (func_id.startswith("func:") or func_id.startswith("method:")):
                continue
            
            for func_name in function_names:
                pattern = r'\b' + re.escape(func_name.split('.')[-1]) + r'\s*\('
                if re.search(pattern, func_node.code_segment):
                    callee_id = self.function_map.get(func_name)
                    if callee_id and callee_id != func_id:
                        func_node.add_dependency(callee_id)
                        self.impact_map[callee_id].append(func_id)
    
    def _update_global_metrics(self):
        """Actualiza las métricas globales del grafo."""
        self.global_metrics["total_nodes"] = len(self.nodes)
        
        total_loc = 0
        total_complexity = 0
        total_maintainability = 0
        total_security = 0
        total_coverage = 0
        nodes_with_tests = 0
        
        for node in self.nodes.values():
            total_loc += node.metrics.lines_of_code
            total_complexity += node.metrics.cyclomatic_complexity
            total_maintainability += node.metrics.maintainability_index
            total_security += len(node.metrics.security_issues)
            
            if node.test_cases:
                total_coverage += node.test_coverage
                nodes_with_tests += 1
        
        n = max(len(self.nodes), 1)
        self.global_metrics["total_loc"] = total_loc
        self.global_metrics["average_complexity"] = total_complexity / n
        self.global_metrics["average_maintainability"] = total_maintainability / n
        self.global_metrics["total_security_issues"] = total_security
        self.global_metrics["test_coverage"] = (
            total_coverage / nodes_with_tests if nodes_with_tests > 0 else 0.0
        )
    
    def find_similar_code(self, code_segment: str, threshold: float = 0.8) -> List[Tuple]:
        """Encuentra fragmentos de código similares basado en embeddings."""
        query_embedding = self.embedding_model.encode(code_segment)
        results = []
        
        for code_id, embedding in self.code_embeddings.items():
            similarity = F.cosine_similarity(
                query_embedding.unsqueeze(0),
                embedding.unsqueeze(0)
            ).item()
            
            if similarity >= threshold:
                results.append((
                    code_id,
                    similarity,
                    self.nodes[code_id]
                ))
        
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def run_all_tests(self, framework: TestFramework = TestFramework.PYTEST) -> Dict:
        """Ejecuta todas las pruebas en el grafo."""
        results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "coverage": 0.0,
            "details": {}
        }
        
        for node_id, node in self.nodes.items():
            if node.test_cases:
                test_results = node.run_tests(self.test_runner, framework)
                
                results["details"][node_id] = test_results
                results["total_tests"] += len(test_results)
                results["passed"] += sum(1 for r in test_results if r.passed)
                results["failed"] += sum(1 for r in test_results if not r.passed)
        
        if results["total_tests"] > 0:
            results["coverage"] = results["passed"] / results["total_tests"]
        
        # Actualizar métricas globales
        self._update_global_metrics()
        
        return results
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """Genera un reporte completo de calidad del código."""
        report = {
            "summary": self.global_metrics,
            "high_risk_nodes": [],
            "security_vulnerabilities": [],
            "code_smells": [],
            "low_documentation": [],
            "high_complexity": [],
            "recommendations": []
        }
        
        for node_id, node in self.nodes.items():
            # Nodos de alto riesgo (baja mantenibilidad y alta complejidad)
            if (node.metrics.maintainability_index < 50 and 
                node.metrics.cyclomatic_complexity > 10):
                report["high_risk_nodes"].append({
                    "node_id": node_id,
                    "maintainability": node.metrics.maintainability_index,
                    "complexity": node.metrics.cyclomatic_complexity
                })
            
            # Vulnerabilidades de seguridad
            if node.metrics.security_issues:
                report["security_vulnerabilities"].append({
                    "node_id": node_id,
                    "issues": node.metrics.security_issues
                })
            
            # Code smells
            if node.metrics.code_smells:
                report["code_smells"].append({
                    "node_id": node_id,
                    "smells": node.metrics.code_smells
                })
            
            # Baja documentación
            if node.documentation_score < 0.3:
                report["low_documentation"].append({
                    "node_id": node_id,
                    "score": node.documentation_score
                })
            
            # Alta complejidad
            if node.metrics.cognitive_complexity > 15:
                report["high_complexity"].append({
                    "node_id": node_id,
                    "cognitive_complexity": node.metrics.cognitive_complexity,
                    "cyclomatic_complexity": node.metrics.cyclomatic_complexity
                })
        
        # Generar recomendaciones
        if report["security_vulnerabilities"]:
            report["recommendations"].append(
                f"CRITICAL: Fix {len(report['security_vulnerabilities'])} security vulnerabilities"
            )
        
        if report["high_risk_nodes"]:
            report["recommendations"].append(
                f"HIGH: Refactor {len(report['high_risk_nodes'])} high-risk components"
            )
        
        if len(report["low_documentation"]) > len(self.nodes) * 0.3:
            report["recommendations"].append(
                "MEDIUM: Improve documentation coverage (currently below 30%)"
            )
        
        if self.global_metrics["average_complexity"] > 10:
            report["recommendations"].append(
                "MEDIUM: Reduce average code complexity"
            )
        
        return report
    
    def save_state(self, file_path: str) -> bool:
        """Guarda el estado del SRPK en un archivo JSON."""
        try:
            state = {
                "nodes": {k: v.to_json() for k, v in self.nodes.items()},
                "function_map": self.function_map,
                "class_map": self.class_map,
                "module_map": dict(self.module_map),
                "impact_map": dict(self.impact_map),
                "global_metrics": self.global_metrics,
                "timestamp": time.time()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            
            # Guardar embeddings
            embeddings_path = file_path.replace('.json', '_embeddings.pt')
            torch.save(self.code_embeddings, embeddings_path)
            
            logger.info(f"SRPK state saved to {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving SRPK state: {e}")
            return False
    
    def load_state(self, file_path: str) -> bool:
        """Carga el estado del SRPK desde un archivo JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Reconstruir nodos
            self.nodes = {}
            for code_id, node_data in state["nodes"].items():
                # Aquí deberías reconstruir los nodos con todos sus datos
                # Por simplicidad, creamos nuevos nodos básicos
                node = EnhancedCodeKnowledgeNode(
                    code_id=code_id,
                    code_segment="",  # Necesitarías guardar esto también
                    dependencies=node_data.get("dependencies", []),
                    purpose=node_data.get("purpose", "")
                )
                self.nodes[code_id] = node
            
            self.function_map = state.get("function_map", {})
            self.class_map = state.get("class_map", {})
            self.module_map = defaultdict(list, state.get("module_map", {}))
            self.impact_map = defaultdict(list, state.get("impact_map", {}))
            self.global_metrics = state.get("global_metrics", {})
            
            # Cargar embeddings
            embeddings_path = file_path.replace('.json', '_embeddings.pt')
            if os.path.exists(embeddings_path):
                self.code_embeddings = torch.load(embeddings_path)
            
            logger.info(f"SRPK state loaded from {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading SRPK state: {e}")
            return False


# CLI Manager actualizado
class EnhancedSRPKManager:
    """Interfaz mejorada para gestionar el SRPK v2."""
    
    def __init__(self, state_file: Optional[str] = None):
        self.srpk = EnhancedSRPKGraph()
        if state_file and os.path.exists(state_file):
            self.srpk.load_state(state_file)
        self.state_file = state_file or "srpk_v2_state.json"
    
    def analyze_project(self, project_path: str) -> int:
        """Analiza todo un proyecto de Python."""
        file_count = 0
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    logger.info(f"Analyzing {file_path}...")
                    nodes = self.srpk.analyze_code_file(file_path)
                    if nodes > 0:
                        file_count += 1
        
        self.srpk.save_state(self.state_file)
        return file_count
    
    def run_tests(self, framework: str = "pytest") -> Dict:
        """Ejecuta todas las pruebas del proyecto."""
        framework_enum = TestFramework.PYTEST
        if framework == "unittest":
            framework_enum = TestFramework.UNITTEST
        elif framework == "doctest":
            framework_enum = TestFramework.DOCTEST
        elif framework == "custom":
            framework_enum = TestFramework.CUSTOM
        
        return self.srpk.run_all_tests(framework_enum)
    
    def generate_quality_report(self, output_path: str) -> bool:
        """Genera un reporte de calidad del código."""
        try:
            report = self.srpk.generate_quality_report()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            
            # También crear versión markdown
            md_path = output_path.replace('.json', '.md')
            self._generate_markdown_report(report, md_path)
            
            logger.info(f"Quality report generated: {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return False
    
    def _generate_markdown_report(self, report: Dict, output_path: str):
        """Genera versión markdown del reporte."""
        md_lines = [
            "# Code Quality Report",
            f"Generated by SRPK v2",
            "",
            "## Summary",
            f"- Total Nodes: {report['summary']['total_nodes']}",
            f"- Total Lines of Code: {report['summary']['total_loc']}",
            f"- Average Complexity: {report['summary']['average_complexity']:.2f}",
            f"- Average Maintainability: {report['summary']['average_maintainability']:.2f}",
            f"- Security Issues: {report['summary']['total_security_issues']}",
            f"- Test Coverage: {report['summary']['test_coverage']:.1%}",
            "",
            "## Recommendations",
        ]
        
        for rec in report['recommendations']:
            md_lines.append(f"- {rec}")
        
        if report['security_vulnerabilities']:
            md_lines.extend([
                "",
                "## Security Vulnerabilities",
                ""
            ])
            for vuln in report['security_vulnerabilities']:
                md_lines.append(f"### {vuln['node_id']}")
                for issue in vuln['issues']:
                    md_lines.append(f"- {issue}")
        
        if report['high_risk_nodes']:
            md_lines.extend([
                "",
                "## High Risk Components",
                ""
            ])
            for node in report['high_risk_nodes']:
                md_lines.append(
                    f"- **{node['node_id']}**: "
                    f"Maintainability={node['maintainability']:.1f}, "
                    f"Complexity={node['complexity']}"
                )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))


# Punto de entrada principal
if __name__ == "__main__":
    import sys
    
    print("=== MSC SRPK v2.0 - Enhanced Code Knowledge Graph ===")
    print("Features: Real testing, semantic embeddings, quality metrics")
    print()
    
    # Crear instancia del gestor
    manager = EnhancedSRPKManager("srpk_v2_state.json")
    
    # Verificar argumentos de línea de comandos
    if len(sys.argv) < 2:
        print("Usage: python msc_srpk_v2.py <command> [options]")
        print("\nCommands:")
        print("  analyze <path>    - Analyze a Python project")
        print("  test [framework]  - Run tests (pytest/unittest/doctest)")
        print("  report <output>   - Generate quality report")
        print("  find <code>       - Find similar code fragments")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "analyze":
        if len(sys.argv) < 3:
            print("Error: Please specify project path")
            sys.exit(1)
        
        project_path = sys.argv[2]
        if not os.path.exists(project_path):
            print(f"Error: Path '{project_path}' does not exist")
            sys.exit(1)
        
        print(f"Analyzing project: {project_path}")
        file_count = manager.analyze_project(project_path)
        print(f"✓ Analysis complete: {file_count} files processed")
        print(f"✓ State saved to: {manager.state_file}")
    
    elif command == "test":
        framework = sys.argv[2] if len(sys.argv) > 2 else "pytest"
        print(f"Running tests with {framework}...")
        
        results = manager.run_tests(framework)
        print(f"\n=== Test Results ===")
        print(f"Total: {results['total_tests']}")
        print(f"Passed: {results['passed']} ✓")
        print(f"Failed: {results['failed']} ✗")
        print(f"Coverage: {results['coverage']:.1%}")
    
    elif command == "report":
        if len(sys.argv) < 3:
            output_path = "quality_report.json"
        else:
            output_path = sys.argv[2]
        
        print(f"Generating quality report: {output_path}")
        if manager.generate_quality_report(output_path):
            print(f"✓ Report generated successfully")
            print(f"  JSON: {output_path}")
            print(f"  Markdown: {output_path.replace('.json', '.md')}")
        else:
            print("✗ Failed to generate report")
    
    elif command == "find":
        if len(sys.argv) < 3:
            print("Error: Please provide code snippet to search")
            sys.exit(1)
        
        code_snippet = sys.argv[2]
        print(f"Searching for similar code...")
        
        results = manager.srpk.find_similar_code(code_snippet, threshold=0.7)
        if results:
            print(f"\nFound {len(results)} similar fragments:")
            for code_id, similarity, node in results[:5]:
                print(f"  - {code_id}: {similarity:.2%} similarity")
                print(f"    Purpose: {node.purpose}")
        else:
            print("No similar code found")
    
    else:
        print(f"Error: Unknown command '{command}'")
        sys.exit(1)
    
    print("\n=== SRPK v2 Process Complete ===")
