# Multi-stage build para MSC SRPK v2.0
FROM python:3.11-slim as base

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash mscsrpk

# Stage de desarrollo
FROM base as development

WORKDIR /app

# Copiar requirements
COPY requirements.txt web/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r web/requirements.txt

# Instalar dependencias de desarrollo
RUN pip install --no-cache-dir \
    pytest pytest-cov pytest-xdist \
    black flake8 mypy bandit \
    jupyter notebook

# Copiar código fuente
COPY . .

# Cambiar a usuario no-root
USER mscsrpk

# Comando por defecto
CMD ["python", "-m", "msc_srpk.cli", "--help"]

# Stage de producción
FROM base as production

WORKDIR /app

# Copiar requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar solo el código necesario
COPY msc_srpk/ ./msc_srpk/
COPY setup.py pyproject.toml ./

# Instalar el paquete
RUN pip install --no-cache-dir .

# Cambiar a usuario no-root
USER mscsrpk

# Variables de entorno
ENV MSC_SRPK_LOG_LEVEL=INFO
ENV MSC_SRPK_CACHE_DIR=/app/cache

# Crear directorio de cache
RUN mkdir -p /app/cache

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import msc_srpk; print('OK')" || exit 1

# Comando por defecto
CMD ["msc-srpk", "--help"]

# Stage para la aplicación web
FROM base as web

WORKDIR /app

# Copiar requirements
COPY requirements.txt web/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r web/requirements.txt

# Copiar código fuente
COPY msc_srpk/ ./msc_srpk/
COPY web/ ./web/
COPY setup.py pyproject.toml ./

# Instalar el paquete
RUN pip install --no-cache-dir .

# Cambiar a usuario no-root
USER mscsrpk

# Variables de entorno para web
ENV MSC_SRPK_WEB_HOST=0.0.0.0
ENV MSC_SRPK_WEB_PORT=8000

# Exponer puerto
EXPOSE 8000

# Health check para web
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

# Comando para iniciar servidor web
CMD ["python", "web/start_server.py", "--host", "0.0.0.0", "--port", "8000"]
