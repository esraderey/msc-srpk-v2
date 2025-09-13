#!/usr/bin/env python3
"""
Tests de verificación para el despliegue de la landing page
"""

import os
import requests
import subprocess
import time
import signal
import sys
from pathlib import Path

def test_landing_page_exists():
    """Verifica que la landing page comercial existe"""
    landing_path = Path("commercial/landing/index.html")
    assert landing_path.exists(), f"Landing page no encontrada en {landing_path}"
    print("✅ Landing page comercial existe")

def test_backend_module_loads():
    """Verifica que el módulo backend se puede importar"""
    original_cwd = os.getcwd()
    original_path = sys.path.copy()
    try:
        backend_dir = os.path.join(os.getcwd(), "web", "backend")
        os.chdir(backend_dir)
        sys.path.insert(0, backend_dir)
        import main
        assert hasattr(main, 'app'), "FastAPI app no encontrada"
        print("✅ Módulo backend se carga correctamente")
    finally:
        os.chdir(original_cwd)
        sys.path = original_path

def test_deployment_script_exists():
    """Verifica que el script de despliegue existe y es ejecutable"""
    script_path = Path("deploy_landing.sh")
    assert script_path.exists(), "Script de despliegue no encontrado"
    assert os.access(script_path, os.X_OK), "Script de despliegue no es ejecutable"
    print("✅ Script de despliegue existe y es ejecutable")

def test_dependencies_installed():
    """Verifica que las dependencias están instaladas"""
    try:
        import fastapi
        import uvicorn
        print("✅ Dependencias web instaladas")
    except ImportError as e:
        raise AssertionError(f"Dependencias faltantes: {e}")

def test_server_starts_and_serves_landing():
    """Test completo de inicio de servidor y servicio de landing page"""
    # Cambiar al directorio backend
    original_cwd = os.getcwd()
    server_process = None
    
    try:
        os.chdir("web/backend")
        
        # Iniciar servidor en background
        server_process = subprocess.Popen([
            sys.executable, "main.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Esperar a que el servidor inicie
        time.sleep(5)
        
        # Verificar que el servidor está corriendo
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            raise AssertionError(f"Servidor falló al iniciar: {stderr.decode()}")
        
        # Probar endpoints
        base_url = "http://127.0.0.1:8000"
        
        # Test landing page
        response = requests.get(base_url, timeout=10)
        assert response.status_code == 200, f"Landing page falló: {response.status_code}"
        assert "MSC SRPK v2.0" in response.text, "Contenido de landing page incorrecto"
        print("✅ Landing page sirve correctamente")
        
        # Test API status
        response = requests.get(f"{base_url}/api/status", timeout=10)
        assert response.status_code == 200, f"API status falló: {response.status_code}"
        data = response.json()
        assert data["status"] == "running", "Estado del servidor incorrecto"
        print("✅ API responde correctamente")
        
        # Test API docs
        response = requests.get(f"{base_url}/docs", timeout=10)
        assert response.status_code == 200, f"API docs falló: {response.status_code}"
        print("✅ API docs accesible")
        
    except Exception as e:
        print(f"❌ Test de servidor falló: {e}")
        raise
    finally:
        # Limpiar
        if server_process and server_process.poll() is None:
            server_process.terminate()
            time.sleep(2)
            if server_process.poll() is None:
                server_process.kill()
        os.chdir(original_cwd)

def main():
    """Ejecuta todos los tests"""
    print("🧪 Ejecutando tests de despliegue de landing page...")
    print()
    
    tests = [
        test_landing_page_exists,
        test_backend_module_loads,
        test_deployment_script_exists,
        test_dependencies_installed,
        test_server_starts_and_serves_landing,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ {test.__name__} falló: {e}")
            return False
    
    print()
    print("🎉 Todos los tests pasaron! La landing page está correctamente desplegada.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)