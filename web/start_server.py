#!/usr/bin/env python3
"""
Script para iniciar el servidor web de MSC SRPK v2.0
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Iniciar servidor web MSC SRPK v2.0")
    parser.add_argument("--host", default="0.0.0.0", help="Host del servidor")
    parser.add_argument("--port", type=int, default=8000, help="Puerto del servidor")
    parser.add_argument("--reload", action="store_true", help="Recargar automáticamente en cambios")
    parser.add_argument("--workers", type=int, default=1, help="Número de workers")
    
    args = parser.parse_args()
    
    # Verificar que estamos en el directorio correcto
    web_dir = Path(__file__).parent
    backend_dir = web_dir / "backend"
    
    if not backend_dir.exists():
        print("❌ Error: Directorio backend no encontrado")
        print(f"   Buscando en: {backend_dir}")
        sys.exit(1)
    
    # Cambiar al directorio del backend
    os.chdir(backend_dir)
    
    # Verificar dependencias
    try:
        import uvicorn
        import fastapi
    except ImportError:
        print("❌ Error: Dependencias faltantes")
        print("Instala con: pip install fastapi uvicorn")
        sys.exit(1)
    
    print("🚀 Iniciando servidor web MSC SRPK v2.0...")
    print(f"   Host: {args.host}")
    print(f"   Puerto: {args.port}")
    print(f"   Recarga automática: {'Sí' if args.reload else 'No'}")
    print(f"   Directorio de trabajo: {os.getcwd()}")
    print()
    print("📱 Accede a: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("📊 Dashboard: http://localhost:8000/dashboard")
    print()
    
    # Iniciar servidor
    try:
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido")
    except Exception as e:
        print(f"❌ Error iniciando servidor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
