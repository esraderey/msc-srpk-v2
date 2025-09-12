# Tutorial de Uso - MSC SRPK v2.0

## Introducción

Este tutorial te guiará a través de las funcionalidades principales de MSC SRPK v2.0, desde el análisis básico hasta el uso avanzado de embeddings y métricas.

## Configuración Inicial

### 1. Preparar un Proyecto de Ejemplo

```bash
# Crear directorio de trabajo
mkdir mi-proyecto-ejemplo
cd mi-proyecto-ejemplo

# Crear archivos Python de ejemplo
cat > calculadora.py << 'EOF'
"""
Calculadora básica con operaciones matemáticas.
"""
import math

class Calculadora:
    """Calculadora con operaciones básicas y avanzadas."""
    
    def __init__(self):
        self.historial = []
    
    def sumar(self, a, b):
        """Suma dos números."""
        resultado = a + b
        self.historial.append(f"{a} + {b} = {resultado}")
        return resultado
    
    def restar(self, a, b):
        """Resta dos números."""
        resultado = a - b
        self.historial.append(f"{a} - {b} = {resultado}")
        return resultado
    
    def multiplicar(self, a, b):
        """Multiplica dos números."""
        resultado = a * b
        self.historial.append(f"{a} * {b} = {resultado}")
        return resultado
    
    def dividir(self, a, b):
        """Divide dos números."""
        if b == 0:
            raise ValueError("No se puede dividir por cero")
        resultado = a / b
        self.historial.append(f"{a} / {b} = {resultado}")
        return resultado
    
    def potencia(self, base, exponente):
        """Calcula la potencia de un número."""
        resultado = math.pow(base, exponente)
        self.historial.append(f"{base}^{exponente} = {resultado}")
        return resultado
    
    def obtener_historial(self):
        """Retorna el historial de operaciones."""
        return self.historial.copy()
EOF

cat > test_calculadora.py << 'EOF'
"""Tests para la calculadora."""
import unittest
from calculadora import Calculadora

class TestCalculadora(unittest.TestCase):
    """Tests unitarios para la clase Calculadora."""
    
    def setUp(self):
        """Configuración inicial para cada test."""
        self.calc = Calculadora()
    
    def test_sumar(self):
        """Test de suma básica."""
        resultado = self.calc.sumar(2, 3)
        self.assertEqual(resultado, 5)
    
    def test_restar(self):
        """Test de resta básica."""
        resultado = self.calc.restar(5, 3)
        self.assertEqual(resultado, 2)
    
    def test_multiplicar(self):
        """Test de multiplicación básica."""
        resultado = self.calc.multiplicar(4, 5)
        self.assertEqual(resultado, 20)
    
    def test_dividir(self):
        """Test de división básica."""
        resultado = self.calc.dividir(10, 2)
        self.assertEqual(resultado, 5)
    
    def test_dividir_por_cero(self):
        """Test de división por cero."""
        with self.assertRaises(ValueError):
            self.calc.dividir(10, 0)
    
    def test_potencia(self):
        """Test de potencia."""
        resultado = self.calc.potencia(2, 3)
        self.assertEqual(resultado, 8)
    
    def test_historial(self):
        """Test del historial."""
        self.calc.sumar(1, 2)
        self.calc.restar(5, 3)
        historial = self.calc.obtener_historial()
        self.assertEqual(len(historial), 2)
        self.assertIn("1 + 2 = 3", historial)
EOF
```

## Análisis Básico

### 1. Analizar el Proyecto

```bash
# Analizar el proyecto completo
msc-srpk analyze .

# Verificar que se creó el archivo de estado
ls -la srpk_v2_state.json
```

### 2. Ver los Resultados del Análisis

```bash
# Generar reporte de calidad
msc-srpk report --out mi_reporte.json

# Ver el reporte en formato legible
cat mi_reporte.md
```

## Testing Automatizado

### 1. Ejecutar Tests con unittest

```bash
# Ejecutar tests usando unittest
msc-srpk test --framework unittest

# Salida esperada:
# Total: 7
# Passed: 7
# Failed: 0
# Coverage: 100.0%
```

### 2. Ejecutar Tests con pytest (si está instalado)

```bash
# Instalar pytest si no está instalado
pip install pytest

# Ejecutar con pytest
msc-srpk test --framework pytest
```

## Búsqueda de Código Similar

### 1. Buscar Métodos Similares

```bash
# Buscar métodos de suma
msc-srpk find "def sumar"

# Buscar operaciones matemáticas
msc-srpk find "def multiplicar"
```

### 2. Buscar Patrones Específicos

```bash
# Buscar manejo de errores
msc-srpk find "raise ValueError"

# Buscar métodos con historial
msc-srpk find "self.historial"
```

## Análisis Avanzado

### 1. Crear Archivo con Código Complejo

```bash
cat > algoritmos.py << 'EOF'
"""Algoritmos de ordenamiento y búsqueda."""
import random
from typing import List, Optional

def bubble_sort(arr: List[int]) -> List[int]:
    """Ordena una lista usando bubble sort."""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def quick_sort(arr: List[int]) -> List[int]:
    """Ordena una lista usando quick sort."""
    if len(arr) <= 1:
        return arr
    
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    return quick_sort(left) + middle + quick_sort(right)

def binary_search(arr: List[int], target: int) -> Optional[int]:
    """Busca un elemento en una lista ordenada."""
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    return None

class AlgoritmosComplejos:
    """Clase con algoritmos complejos."""
    
    def __init__(self):
        self.cache = {}
    
    def fibonacci_recursive(self, n: int) -> int:
        """Fibonacci recursivo (ineficiente)."""
        if n <= 1:
            return n
        return self.fibonacci_recursive(n - 1) + self.fibonacci_recursive(n - 2)
    
    def fibonacci_memoized(self, n: int) -> int:
        """Fibonacci con memoización."""
        if n in self.cache:
            return self.cache[n]
        
        if n <= 1:
            result = n
        else:
            result = self.fibonacci_memoized(n - 1) + self.fibonacci_memoized(n - 2)
        
        self.cache[n] = result
        return result
EOF
```

### 2. Re-analizar con Código Complejo

```bash
# Re-analizar el proyecto
msc-srpk analyze .

# Generar nuevo reporte
msc-srpk report --out reporte_completo.json
```

### 3. Examinar Métricas de Complejidad

```bash
# Ver el reporte generado
cat reporte_completo.md
```

## Uso de la API Python

### 1. Script de Análisis Personalizado

```python
# analisis_personalizado.py
from msc_srpk.srpk_v2 import EnhancedSRPKManager

def main():
    # Crear manager
    manager = EnhancedSRPKManager("mi_estado.json")
    
    # Analizar proyecto
    archivos = manager.analyze_project(".")
    print(f"Archivos analizados: {archivos}")
    
    # Ejecutar tests
    resultados = manager.run_tests("unittest")
    print(f"Tests ejecutados: {resultados['total_tests']}")
    print(f"Tests exitosos: {resultados['passed']}")
    
    # Generar reporte
    manager.generate_quality_report("mi_analisis.json")
    
    # Buscar código similar
    similares = manager.srpk.find_similar_code("def fibonacci", threshold=0.8)
    print(f"Código similar encontrado: {len(similares)}")
    
    for code_id, similitud, nodo in similares:
        print(f"- {code_id}: {similitud:.2%}")

if __name__ == "__main__":
    main()
```

### 2. Ejecutar Script Personalizado

```bash
python analisis_personalizado.py
```

## Interpretación de Resultados

### 1. Métricas de Calidad

- **Complejidad Ciclomática**: Mide la complejidad del flujo de control
- **Complejidad Cognitiva**: Mide qué tan difícil es entender el código
- **Índice de Mantenibilidad**: Score del 0-100 (mayor es mejor)
- **Ratio de Comentarios**: Porcentaje de líneas comentadas

### 2. Code Smells Detectados

- Funciones muy largas (>50 líneas)
- Demasiados parámetros (>5)
- Clases muy grandes (>20 métodos)
- Imports no utilizados
- Código duplicado

### 3. Problemas de Seguridad

- Uso de `eval()` o `exec()`
- Deserialización con pickle
- Vulnerabilidades de inyección
- Credenciales hardcodeadas

## Mejores Prácticas

### 1. Análisis Regular

```bash
# Crear script de análisis diario
cat > analisis_diario.sh << 'EOF'
#!/bin/bash
echo "=== Análisis Diario de Código ==="
msc-srpk analyze .
msc-srpk test --framework pytest
msc-srpk report --out "reportes/$(date +%Y%m%d)_calidad.json"
echo "Análisis completado: $(date)"
EOF

chmod +x analisis_diario.sh
```

### 2. Integración con CI/CD

```yaml
# .github/workflows/quality-check.yml
name: Quality Check
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install MSC SRPK
        run: pip install msc-srpk
      - name: Analyze code
        run: msc-srpk analyze .
      - name: Run tests
        run: msc-srpk test --framework pytest
      - name: Generate report
        run: msc-srpk report --out quality_report.json
      - name: Upload report
        uses: actions/upload-artifact@v2
        with:
          name: quality-report
          path: quality_report.json
```

## Próximos Pasos

- [API Reference](api.md) - Documentación completa de la API
- [Casos de Uso](use-cases.md) - Ejemplos avanzados
- [Configuración Avanzada](configuration.md) - Personalización del sistema
