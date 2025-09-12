# Guía de Instalación - MSC SRPK v2.0

## Requisitos del Sistema

### Requisitos Mínimos
- **Python:** 3.9 o superior
- **RAM:** 4GB mínimo (8GB recomendado)
- **Espacio en disco:** 2GB libres
- **Sistema operativo:** Windows 10+, macOS 10.14+, Linux Ubuntu 18.04+

### Requisitos Recomendados
- **Python:** 3.11+
- **RAM:** 16GB
- **GPU:** NVIDIA con CUDA (opcional, para acelerar embeddings)
- **Espacio en disco:** 10GB libres

## Instalación

### 1. Instalación desde PyPI (Recomendado)

```bash
# Instalación básica
pip install msc-srpk

# Con dependencias opcionales para GPU
pip install msc-srpk[gpu]

# Actualizar a la última versión
pip install --upgrade msc-srpk
```

### 2. Instalación desde Código Fuente

```bash
# Clonar el repositorio
git clone https://github.com/raulcruzacosta/msc-srpk.git
cd msc-srpk

# Instalación en modo desarrollo
pip install -e .

# O instalación normal
pip install .
```

### 3. Instalación con Conda

```bash
# Crear entorno conda
conda create -n msc-srpk python=3.11
conda activate msc-srpk

# Instalar dependencias
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
pip install msc-srpk
```

## Verificación de la Instalación

```bash
# Verificar instalación
msc-srpk --version

# Probar funcionalidad básica
msc-srpk analyze --help
```

## Configuración Inicial

### Variables de Entorno

```bash
# Configurar modelo de embeddings (opcional)
export MSC_SRPK_MODEL="microsoft/codebert-base"

# Configurar directorio de cache
export MSC_SRPK_CACHE_DIR="$HOME/.msc-srpk/cache"

# Habilitar logs detallados
export MSC_SRPK_LOG_LEVEL="DEBUG"
```

### Configuración de GPU (Opcional)

```bash
# Verificar disponibilidad de CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Configurar GPU específica
export CUDA_VISIBLE_DEVICES=0
```

## Solución de Problemas

### Error: "No module named 'transformers'"

```bash
# Instalar dependencias faltantes
pip install transformers torch
```

### Error: "CUDA out of memory"

```bash
# Usar CPU en lugar de GPU
export MSC_SRPK_FORCE_CPU=true
```

### Error de permisos en Windows

```bash
# Ejecutar como administrador o instalar para usuario
pip install --user msc-srpk
```

## Desinstalación

```bash
# Desinstalar completamente
pip uninstall msc-srpk

# Limpiar cache
rm -rf ~/.msc-srpk
```

## Próximos Pasos

Después de la instalación exitosa, consulta:

- [Tutorial de Uso](tutorial.md)
- [API Reference](api.md)
- [Casos de Uso](use-cases.md)
