#!/bin/bash
# Script para desplegar la landing page de MSC SRPK v2.0

echo "🚀 Desplegando MSC SRPK v2.0 Landing Page..."
echo

# Verificar que estamos en el directorio correcto
if [ ! -f "commercial/landing/index.html" ]; then
    echo "❌ Error: No se encuentra la landing page comercial"
    echo "   Ejecutar desde el directorio raíz del proyecto"
    exit 1
fi

# Verificar dependencias
if ! python -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "❌ Error: Dependencias faltantes"
    echo "   Instalar con: pip install -r requirements.txt -r web/requirements.txt"
    exit 1
fi

echo "✅ Landing page comercial encontrada"
echo "✅ Dependencias verificadas"
echo

# Cambiar al directorio del backend
cd web/backend

echo "📂 Cambiando al directorio backend: $(pwd)"
echo

# Configurar variables de entorno
export MSC_SRPK_ENV=production
export MSC_SRPK_LOG_LEVEL=INFO

echo "🌐 Iniciando servidor web..."
echo "   URL principal: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Dashboard: http://localhost:8000/dashboard"
echo "   Monitoreo: http://localhost:8000/monitoring"
echo

# Iniciar servidor
python main.py