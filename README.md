# MSC SRPK v2.0 🚀

**Grafo de Conocimiento de Código** con análisis inteligente, embeddings semánticos y métricas de calidad empresarial.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/msc-srpk.svg)](https://badge.fury.io/py/msc-srpk)

## 🎯 ¿Qué es MSC SRPK?

MSC SRPK (Self-Referencing Proprietary Knowledge) es una plataforma avanzada de análisis de código que combina:

- **🧠 Embeddings semánticos** para detección de similitud y patrones
- **🧪 Testing real** con pytest, unittest y doctest
- **📊 Métricas de calidad** empresarial (complejidad, mantenibilidad, seguridad)
- **🔍 Búsqueda inteligente** de código similar y duplicado
- **📈 Reportes** listos para compliance y auditoría

## ⚡ Instalación Rápida

```bash
# Instalación básica
pip install msc-srpk

# O desde fuente
git clone https://github.com/raulcruzacosta/msc-srpk.git
cd msc-srpk
pip install -e .
```

## 🌐 Despliegue de Landing Page

Para desplegar la landing page y la interfaz web:

```bash
# Instalar dependencias web
pip install -r requirements.txt -r web/requirements.txt

# Desplegar con script automático
./deploy_landing.sh

# O manualmente
cd web/backend
python main.py
```

La landing page estará disponible en:
- **Landing Page:** http://localhost:8000
- **Dashboard:** http://localhost:8000/dashboard
- **API Docs:** http://localhost:8000/docs
- **Monitoreo:** http://localhost:8000/monitoring

## 🚀 Uso Básico

### Análisis de Proyecto
```bash
# Analizar todo un proyecto
msc-srpk analyze ./mi_proyecto

# Con archivo de estado personalizado
msc-srpk analyze ./mi_proyecto --state mi_estado.json
```

### Testing Automatizado
```bash
# Ejecutar tests con pytest
msc-srpk test --framework pytest

# Con unittest
msc-srpk test --framework unittest

# Con doctest
msc-srpk test --framework doctest
```

### Generación de Reportes
```bash
# Reporte completo de calidad
msc-srpk report --out quality_report.json

# Los reportes se generan en JSON y Markdown
```

### Búsqueda de Código Similar
```bash
# Buscar código similar
msc-srpk find "def calcular_total(precio, cantidad):"
```

## 📊 Características Principales

### 🧠 Embeddings Semánticos
- Modelos CodeBERT/GraphCodeBERT para análisis profundo
- Fallback interno para entornos sin GPU
- Detección de patrones y duplicidad

### 🧪 Testing Real
- Integración nativa con frameworks populares
- Cobertura de código por nodo del grafo
- Ejecución en entornos aislados y seguros

### 📈 Métricas Avanzadas
- **Complejidad ciclomática** y cognitiva
- **Índice de mantenibilidad** (MI)
- **Detección de code smells**
- **Análisis de seguridad** básico
- **Score de documentación**

### 🔍 Análisis Inteligente
- Detección automática de patrones de diseño
- Análisis de dependencias entre funciones
- Mapeo de impacto de cambios

## 📋 Requisitos del Sistema

- **Python:** 3.9 o superior
- **Memoria:** Mínimo 4GB RAM (8GB recomendado)
- **GPU:** Opcional (acelera embeddings)
- **Espacio:** 2GB para modelos base

## 🏢 Planes Comerciales

| Plan | Precio | Entornos | Soporte |
|------|--------|----------|---------|
| **Startup** | $99/mes | 1 prod + 2 no-prod | 48h |
| **Empresa** | $990/mes | 3 prod + 5 no-prod | 8h |
| **Enterprise** | Personalizado | Ilimitado | 24/5 |

## 📚 Documentación Completa

- [Guía de Instalación](docs/installation.md)
- [Tutorial de Uso](docs/tutorial.md)
- [API Reference](docs/api.md)
- [Casos de Uso](docs/use-cases.md)
- [EULA Comercial](commercial/EULA_COMERCIAL.md)
- [SLA de Soporte](commercial/SLA_Soporte.md)

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](LICENSE) para más detalles.

## 👨‍💻 Autor

**Raúl Cruz Acosta**
- GitHub: [@raulcruzacosta](https://github.com/raulcruzacosta)
- Email: [contacto@mscsrpk.com](mailto:contacto@mscsrpk.com)

## 🆘 Soporte

- **Documentación:** [docs.mscsrpk.com](https://docs.mscsrpk.com)
- **Issues:** [GitHub Issues](https://github.com/raulcruzacosta/msc-srpk/issues)
- **Comercial:** [contacto@mscsrpk.com](mailto:contacto@mscsrpk.com)

---

⭐ **¡Dale una estrella al proyecto si te resulta útil!**
