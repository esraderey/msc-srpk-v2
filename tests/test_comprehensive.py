"""
Tests comprehensivos para MSC SRPK v2.0
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path

# Agregar el directorio padre al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from msc_srpk.srpk_v2 import (
    EnhancedSRPKManager, 
    EnhancedSRPKGraph, 
    CodeAnalyzer,
    TestRunner,
    TestFramework,
    CodeEmbeddingModel,
    EnhancedCodeKnowledgeNode
)
from msc_srpk.licensing import LicenseValidator, LicenseManager, LicenseType, LicenseStatus


class TestCodeAnalyzer:
    """Tests para el analizador de código."""
    
    def test_cyclomatic_complexity_simple(self):
        """Test complejidad ciclomática simple."""
        code = """
def simple_function(x):
    if x > 0:
        return x
    return -x
"""
        complexity = CodeAnalyzer.calculate_cyclomatic_complexity(code)
        assert complexity == 2  # 1 base + 1 if
    
    def test_security_issues_detection(self):
        """Test detección de problemas de seguridad."""
        code = """
def unsafe_function(user_input):
    eval(user_input)
    exec("import os; os.system('ls')")
    import pickle
    pickle.loads(user_input)
"""
        issues = CodeAnalyzer.detect_security_issues(code)
        assert len(issues) >= 3  # eval, exec, pickle
    
    def test_code_smells_detection(self):
        """Test detección de code smells."""
        code = """
def very_long_function(a, b, c, d, e, f, g):
    # Función muy larga con muchos parámetros
    result = a + b + c + d + e + f + g
    for i in range(100):
        for j in range(100):
            for k in range(100):
                result += i * j * k
    return result
"""
        smells = CodeAnalyzer.detect_code_smells(code)
        assert len(smells) > 0  # Debe detectar función larga y muchos parámetros


class TestCodeEmbeddingModel:
    """Tests para el modelo de embeddings."""
    
    def test_embedding_model_initialization(self):
        """Test inicialización del modelo."""
        model = CodeEmbeddingModel()
        assert model.embedding_dim == 768
        assert model.device is not None
    
    def test_encode_simple_code(self):
        """Test codificación de código simple."""
        model = CodeEmbeddingModel()
        code = "def hello(): return 'world'"
        embedding = model.encode(code)
        assert embedding.shape[0] == model.embedding_dim


class TestEnhancedSRPKGraph:
    """Tests para el grafo SRPK."""
    
    def test_graph_initialization(self):
        """Test inicialización del grafo."""
        graph = EnhancedSRPKGraph()
        assert len(graph.nodes) == 0
        assert graph.embedding_model is not None
        assert graph.test_runner is not None
    
    def test_analyze_simple_file(self):
        """Test análisis de archivo simple."""
        graph = EnhancedSRPKGraph()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
def simple_function():
    return "hello"

class SimpleClass:
    def method(self):
        return "world"
""")
            temp_file = f.name
        
        try:
            nodes_created = graph.analyze_code_file(temp_file)
            assert nodes_created > 0
            assert len(graph.nodes) > 0
        finally:
            os.unlink(temp_file)


class TestIntegration:
    """Tests de integración."""
    
    def test_full_analysis_workflow(self):
        """Test flujo completo de análisis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Crear archivo de prueba
            test_file = os.path.join(temp_dir, "test_module.py")
            with open(test_file, 'w') as f:
                f.write("""
def calculate_factorial(n):
    \"\"\"Calcula el factorial de n.\"\"\"
    if n <= 1:
        return 1
    return n * calculate_factorial(n - 1)

class MathUtils:
    def add(self, a, b):
        return a + b
""")
            
            # Crear manager y analizar
            manager = EnhancedSRPKManager()
            file_count = manager.analyze_project(temp_dir)
            
            assert file_count > 0
            assert len(manager.srpk.nodes) > 0


# Fixtures de pytest
@pytest.fixture
def sample_code():
    """Código de muestra para tests."""
    return """
def fibonacci(n):
    \"\"\"Calcula el n-ésimo número de Fibonacci.\"\"\"
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

class Calculator:
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
"""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
