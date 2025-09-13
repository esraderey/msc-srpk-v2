"""
Backend API para MSC SRPK v2.0
Interfaz web moderna con FastAPI y WebSocket para análisis en tiempo real.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import json
import asyncio
import logging
import os
import tempfile
import zipfile
import sqlite3
from pathlib import Path
import sys
from datetime import datetime

# Agregar el directorio padre al path para importar msc_srpk
sys.path.append(str(Path(__file__).parent.parent.parent))

# Configuración de rutas
BASE_DIR = Path(__file__).parent.parent.parent
COMMERCIAL_LANDING_PATH = BASE_DIR / "commercial" / "landing" / "index.html"
WEB_FRONTEND_PATH = BASE_DIR / "web" / "frontend"
STATIC_DIR = BASE_DIR / "web" / "frontend" / "static"

from msc_srpk.srpk_v2 import EnhancedSRPKManager
from msc_srpk.licensing import initialize_license, get_license_info, LicenseError, license_manager
from msc_srpk.monitoring import (
    initialize_monitoring, get_monitoring_logger, get_health_status,
    get_metrics, get_alerts, monitor_performance, track_user_activity
)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MSC SRPK v2.0 API",
    description="API para análisis de código con embeddings semánticos",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios exactos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class LicenseRequest(BaseModel):
    license_key: str

class AnalysisRequest(BaseModel):
    project_path: str
    license_key: Optional[str] = None

class TestRequest(BaseModel):
    framework: str = "pytest"
    license_key: Optional[str] = None

class ReportRequest(BaseModel):
    output_path: str = "quality_report.json"
    license_key: Optional[str] = None

class FindCodeRequest(BaseModel):
    code_snippet: str
    threshold: float = 0.7
    license_key: Optional[str] = None

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]

# Gestor de conexiones WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Cliente conectado. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Cliente desconectado. Total: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error en broadcast: {e}")

manager = ConnectionManager()

# Instancia global del SRPK Manager
srpk_manager: Optional[EnhancedSRPKManager] = None

def get_srpk_manager() -> EnhancedSRPKManager:
    global srpk_manager
    if srpk_manager is None:
        srpk_manager = EnhancedSRPKManager("web_srpk_state.json")
    return srpk_manager

def validate_license(license_key: str) -> bool:
    """Valida la licencia."""
    try:
        return initialize_license(license_key)
    except Exception as e:
        logger.warning(f"Error validando licencia: {e}")
        return False

# Rutas de la API
@app.get("/")
async def root():
    """Página principal - Sirve la landing page comercial."""
    try:
        if COMMERCIAL_LANDING_PATH.exists():
            with open(COMMERCIAL_LANDING_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content)
        else:
            # Fallback a landing page básica
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>MSC SRPK v2.0</title>
                <style>
                    body { font-family: -apple-system, sans-serif; text-align: center; padding: 50px; }
                    .container { max-width: 600px; margin: 0 auto; }
                    h1 { color: #667eea; }
                    .btn { background: #667eea; color: white; padding: 12px 24px; border: none; border-radius: 6px; text-decoration: none; display: inline-block; margin: 10px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>MSC SRPK v2.0</h1>
                    <p>Análisis de Código con IA</p>
                    <a href="/dashboard" class="btn">Dashboard</a>
                    <a href="/docs" class="btn">API Docs</a>
                </div>
            </body>
            </html>
            """)
    except Exception as e:
        logger.error(f"Error sirviendo landing page: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página principal")

@app.post("/api/license/validate")
async def validate_license_endpoint(request: LicenseRequest):
    """Valida una licencia."""
    try:
        if validate_license(request.license_key):
            license_info = get_license_info()
            return {
                "valid": True,
                "license_info": license_info
            }
        else:
            return {
                "valid": False,
                "error": "Licencia inválida o expirada"
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/analysis/start")
async def start_analysis(request: AnalysisRequest):
    """Inicia análisis de un proyecto."""
    try:
        # Validar licencia si se proporciona
        if request.license_key and not validate_license(request.license_key):
            raise HTTPException(status_code=403, detail="Licencia inválida")
        
        # Verificar que el path existe
        if not os.path.exists(request.project_path):
            raise HTTPException(status_code=404, detail="Ruta del proyecto no encontrada")
        
        # Obtener manager
        manager = get_srpk_manager()
        
        # Iniciar análisis en background
        asyncio.create_task(run_analysis_async(request.project_path, manager))
        
        return {"status": "started", "message": "Análisis iniciado"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_analysis_async(project_path: str, manager: EnhancedSRPKManager):
    """Ejecuta análisis de forma asíncrona."""
    try:
        # Notificar inicio
        await manager.broadcast(json.dumps({
            "type": "analysis_started",
            "data": {"message": "Iniciando análisis..."}
        }))
        
        # Ejecutar análisis
        file_count = manager.analyze_project(project_path)
        
        # Notificar progreso
        await manager.broadcast(json.dumps({
            "type": "analysis_progress",
            "data": {"files_processed": file_count}
        }))
        
        # Generar métricas
        metrics = manager.srpk.global_metrics
        
        # Notificar finalización
        await manager.broadcast(json.dumps({
            "type": "analysis_completed",
            "data": {
                "files_processed": file_count,
                "metrics": metrics
            }
        }))
        
    except Exception as e:
        logger.error(f"Error en análisis: {e}")
        await manager.broadcast(json.dumps({
            "type": "analysis_error",
            "data": {"error": str(e)}
        }))

@app.post("/api/tests/run")
async def run_tests(request: TestRequest):
    """Ejecuta tests del proyecto."""
    try:
        # Validar licencia si se proporciona
        if request.license_key and not validate_license(request.license_key):
            raise HTTPException(status_code=403, detail="Licencia inválida")
        
        manager = get_srpk_manager()
        results = manager.run_tests(request.framework)
        
        return {"status": "completed", "results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reports/generate")
async def generate_report(request: ReportRequest):
    """Genera reporte de calidad."""
    try:
        # Validar licencia si se proporciona
        if request.license_key and not validate_license(request.license_key):
            raise HTTPException(status_code=403, detail="Licencia inválida")
        
        manager = get_srpk_manager()
        success = manager.generate_quality_report(request.output_path)
        
        if success:
            return {"status": "completed", "output_path": request.output_path}
        else:
            raise HTTPException(status_code=500, detail="Error generando reporte")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/code/find")
async def find_similar_code(request: FindCodeRequest):
    """Busca código similar."""
    try:
        # Validar licencia si se proporciona
        if request.license_key and not validate_license(request.license_key):
            raise HTTPException(status_code=403, detail="Licencia inválida")
        
        manager = get_srpk_manager()
        results = manager.srpk.find_similar_code(
            request.code_snippet, 
            threshold=request.threshold
        )
        
        # Convertir resultados a formato serializable
        serializable_results = []
        for code_id, similarity, node in results:
            serializable_results.append({
                "code_id": code_id,
                "similarity": float(similarity),
                "purpose": node.purpose,
                "metrics": {
                    "cyclomatic_complexity": node.metrics.cyclomatic_complexity,
                    "lines_of_code": node.metrics.lines_of_code,
                    "maintainability_index": node.metrics.maintainability_index
                }
            })
        
        return {"status": "completed", "results": serializable_results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/project/upload")
async def upload_project(file: UploadFile = File(...)):
    """Sube un proyecto como archivo ZIP."""
    try:
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp()
        
        # Guardar archivo
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Extraer ZIP
        extract_dir = os.path.join(temp_dir, "extracted")
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        return {"status": "uploaded", "extract_path": extract_dir}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Obtiene estado del sistema."""
    try:
        manager = get_srpk_manager()
        metrics = getattr(manager.srpk, 'global_metrics', {})
        
        return {
            "status": "running",
            "version": "2.0.0",
            "metrics": metrics,
            "active_connections": len(manager.active_connections) if hasattr(manager, 'active_connections') else 0
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {
            "status": "running",
            "version": "2.0.0",
            "metrics": {},
            "active_connections": 0,
            "error": str(e)
        }

@app.get("/api/metrics/overview")
async def get_metrics_overview():
    """Obtiene resumen de métricas."""
    try:
        # Importar dashboard de métricas
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.metrics import get_dashboard
        
        dashboard = get_dashboard()
        if dashboard:
            return dashboard.generate_report(hours=24)
        else:
            return {
                "error": "Sistema de métricas no disponible",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/metrics/quality")
async def get_quality_metrics(hours: int = 24):
    """Obtiene métricas de calidad."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.metrics import get_dashboard
        
        dashboard = get_dashboard()
        if dashboard:
            return dashboard.get_quality_overview(hours)
        else:
            return {"error": "Sistema de métricas no disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metrics/performance")
async def get_performance_metrics(hours: int = 24):
    """Obtiene métricas de rendimiento."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.metrics import get_dashboard
        
        dashboard = get_dashboard()
        if dashboard:
            return dashboard.get_performance_overview(hours)
        else:
            return {"error": "Sistema de métricas no disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metrics/testing")
async def get_testing_metrics(hours: int = 24):
    """Obtiene métricas de testing."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.metrics import get_dashboard
        
        dashboard = get_dashboard()
        if dashboard:
            return dashboard.get_testing_overview(hours)
        else:
            return {"error": "Sistema de métricas no disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/metrics/usage")
async def get_usage_metrics(hours: int = 24):
    """Obtiene métricas de uso."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.metrics import get_dashboard
        
        dashboard = get_dashboard()
        if dashboard:
            return dashboard.get_usage_overview(hours)
        else:
            return {"error": "Sistema de métricas no disponible"}
    except Exception as e:
        return {"error": str(e)}

# Endpoints de facturación
@app.get("/api/billing/plans")
async def get_subscription_plans():
    """Obtiene planes de suscripción disponibles."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.billing import get_billing_manager
        
        billing_manager = get_billing_manager()
        if billing_manager:
            # Obtener planes de la base de datos
            with sqlite3.connect(billing_manager.db.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM subscription_plans WHERE active = 1
                """)
                plans = []
                for row in cursor.fetchall():
                    plan = {
                        "plan_id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "price": row[3],
                        "billing_cycle": row[4],
                        "max_prod_environments": row[5],
                        "max_nonprod_environments": row[6],
                        "features": json.loads(row[7]),
                        "trial_days": row[8]
                    }
                    plans.append(plan)
                return plans
        else:
            return {"error": "Sistema de facturación no disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/billing/subscription")
async def get_current_subscription():
    """Obtiene la suscripción actual del usuario."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.billing import get_billing_manager
        
        billing_manager = get_billing_manager()
        if billing_manager:
            # Simular usuario actual (en producción vendría de autenticación)
            customer_id = "demo_customer_id"
            subscription = billing_manager.get_active_subscription(customer_id)
            
            if subscription:
                plan = billing_manager.get_subscription_plan(subscription.plan_id)
                usage_stats = billing_manager.get_customer_usage_stats(customer_id)
                
                return {
                    "subscription": subscription.to_dict(),
                    "plan": plan.to_dict() if plan else None,
                    "usage": usage_stats.get("usage", {}),
                    "billing": usage_stats.get("billing", {})
                }
            else:
                return {"error": "No hay suscripción activa"}
        else:
            return {"error": "Sistema de facturación no disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/billing/invoices")
async def get_customer_invoices():
    """Obtiene facturas del cliente."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.billing import get_billing_manager
        
        billing_manager = get_billing_manager()
        if billing_manager:
            customer_id = "demo_customer_id"  # Simulado
            
            with sqlite3.connect(billing_manager.db.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM invoices 
                    WHERE customer_id = ? 
                    ORDER BY created_at DESC
                """, (customer_id,))
                
                invoices = []
                for row in cursor.fetchall():
                    invoice = {
                        "invoice_id": row[0],
                        "customer_id": row[1],
                        "subscription_id": row[2],
                        "amount": row[3],
                        "currency": row[4],
                        "status": row[5],
                        "due_date": row[6],
                        "paid_date": row[7],
                        "description": row[8],
                        "created_at": row[10]
                    }
                    invoices.append(invoice)
                
                return invoices
        else:
            return {"error": "Sistema de facturación no disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/billing/subscribe")
async def create_subscription(request: Dict[str, Any]):
    """Crea una nueva suscripción."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.billing import get_billing_manager
        
        billing_manager = get_billing_manager()
        if not billing_manager:
            return {"success": False, "error": "Sistema de facturación no disponible"}
        
        plan_id = request.get("plan_id")
        customer_info = request.get("customer_info", {})
        
        if not plan_id:
            return {"success": False, "error": "Plan ID requerido"}
        
        # Crear o obtener cliente
        customer = billing_manager.get_customer_by_email(customer_info.get("email", ""))
        if not customer:
            customer = billing_manager.create_customer(
                email=customer_info.get("email", ""),
                name=customer_info.get("name", ""),
                company=customer_info.get("company"),
                phone=customer_info.get("phone")
            )
        
        # Crear suscripción
        subscription = billing_manager.create_subscription(
            customer_id=customer.customer_id,
            plan_id=plan_id
        )
        
        # Generar clave de licencia
        license_key = billing_manager.generate_license_key(
            customer.customer_id,
            plan_id
        )
        
        return {
            "success": True,
            "subscription": subscription.to_dict(),
            "license_key": license_key,
            "customer": customer.to_dict()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/billing/cancel")
async def cancel_subscription():
    """Cancela la suscripción actual."""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from msc_srpk.billing import get_billing_manager
        
        billing_manager = get_billing_manager()
        if not billing_manager:
            return {"success": False, "error": "Sistema de facturación no disponible"}
        
        customer_id = "demo_customer_id"  # Simulado
        subscription = billing_manager.get_active_subscription(customer_id)
        
        if not subscription:
            return {"success": False, "error": "No hay suscripción activa"}
        
        # Actualizar estado de suscripción
        with sqlite3.connect(billing_manager.db.db_path) as conn:
            conn.execute("""
                UPDATE subscriptions 
                SET status = 'cancelled', updated_at = ?
                WHERE subscription_id = ?
            """, (datetime.now().isoformat(), subscription.subscription_id))
            conn.commit()
        
        return {"success": True, "message": "Suscripción cancelada"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Esperar mensajes del cliente
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Procesar mensaje según tipo
            if message["type"] == "ping":
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": asyncio.get_event_loop().time()}),
                    websocket
                )
            elif message["type"] == "get_status":
                status = await get_status()
                await manager.send_personal_message(
                    json.dumps({"type": "status", "data": status}),
                    websocket
                )
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        manager.disconnect(websocket)

# Servir archivos estáticos y páginas frontend
try:
    # Crear directorio static si no existe
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
    
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except Exception as e:
    logger.warning(f"No se pudo montar directorio static: {e}")

# Endpoints para páginas del frontend
@app.get("/dashboard")
async def dashboard():
    """Dashboard de la aplicación."""
    try:
        dashboard_path = WEB_FRONTEND_PATH / "dashboard.html"
        if dashboard_path.exists():
            with open(dashboard_path, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content)
        else:
            raise HTTPException(status_code=404, detail="Dashboard no encontrado")
    except Exception as e:
        logger.error(f"Error sirviendo dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error cargando dashboard")

@app.get("/monitoring")
async def monitoring_page():
    """Página de monitoreo."""
    try:
        monitoring_path = WEB_FRONTEND_PATH / "monitoring.html"
        if monitoring_path.exists():
            with open(monitoring_path, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content)
        else:
            raise HTTPException(status_code=404, detail="Página de monitoreo no encontrada")
    except Exception as e:
        logger.error(f"Error sirviendo página de monitoreo: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página de monitoreo")

@app.get("/billing")
async def billing_page():
    """Página de facturación."""
    try:
        billing_path = WEB_FRONTEND_PATH / "billing.html"
        if billing_path.exists():
            with open(billing_path, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content)
        else:
            raise HTTPException(status_code=404, detail="Página de facturación no encontrada")
    except Exception as e:
        logger.error(f"Error sirviendo página de facturación: {e}")
        raise HTTPException(status_code=500, detail="Error cargando página de facturación")

# Endpoints de Monitoreo
@app.get("/api/monitoring/health")
async def monitoring_health():
    """Obtiene estado de salud del sistema."""
    try:
        health_status = get_health_status()
        return {"status": "success", "data": health_status}
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado de salud")

@app.get("/api/monitoring/metrics")
async def monitoring_metrics():
    """Obtiene métricas del sistema."""
    try:
        metrics = get_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo métricas")

@app.get("/api/monitoring/alerts")
async def monitoring_alerts():
    """Obtiene alertas activas."""
    try:
        alerts = get_alerts()
        return {"status": "success", "data": alerts}
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo alertas")

@app.get("/api/monitoring/logs")
async def monitoring_logs(
    level: Optional[str] = None,
    time_range: str = "1h",
    search: Optional[str] = None,
    limit: int = 100
):
    """Obtiene logs del sistema."""
    try:
        # En una implementación real, esto consultaría la base de datos de logs
        # Por ahora, simulamos logs
        logs = [
            {
                "timestamp": "2024-12-20T10:30:00Z",
                "level": "INFO",
                "message": "Sistema iniciado correctamente",
                "module": "main.py",
                "function": "startup",
                "line": 45
            },
            {
                "timestamp": "2024-12-20T10:31:00Z",
                "level": "INFO",
                "message": "Usuario inició sesión",
                "module": "auth.py",
                "function": "login",
                "line": 123
            },
            {
                "timestamp": "2024-12-20T10:32:00Z",
                "level": "WARNING",
                "message": "Alto uso de CPU detectado",
                "module": "monitoring.py",
                "function": "check_alerts",
                "line": 89
            }
        ]
        
        # Filtrar por nivel si se especifica
        if level:
            logs = [log for log in logs if log["level"] == level.upper()]
        
        # Filtrar por búsqueda si se especifica
        if search:
            logs = [log for log in logs if search.lower() in log["message"].lower()]
        
        return {"status": "success", "data": logs[:limit]}
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo logs")

@app.get("/api/monitoring/dashboard")
async def monitoring_dashboard():
    """Obtiene datos completos para el dashboard de monitoreo."""
    try:
        health = get_health_status()
        metrics = get_metrics()
        alerts = get_alerts()
        
        return {
            "status": "success",
            "data": {
                "health": health,
                "metrics": metrics,
                "alerts": alerts,
                "timestamp": "2024-12-20T10:30:00Z"
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo datos del dashboard")

# Inicializar sistema de monitoreo
@app.on_event("startup")
async def startup_event():
    """Inicializa sistemas al arrancar la aplicación."""
    try:
        # Inicializar sistema de monitoreo
        try:
            initialize_monitoring(port=8001)
            logger.info("Sistema de monitoreo inicializado")
        except Exception as e:
            logger.warning(f"No se pudo inicializar monitoreo: {e}")
        
        # Inicializar sistema de métricas si está disponible
        try:
            from msc_srpk.metrics import initialize_metrics
            initialize_metrics()
            logger.info("Sistema de métricas inicializado")
        except (ImportError, Exception) as e:
            logger.warning(f"Sistema de métricas no disponible: {e}")
        
        # Inicializar sistema de billing si está disponible
        try:
            from msc_srpk.billing import initialize_billing
            initialize_billing()
            logger.info("Sistema de billing inicializado")
        except (ImportError, Exception) as e:
            logger.warning(f"Sistema de billing no disponible: {e}")
            
    except Exception as e:
        logger.warning(f"Algunos sistemas no se pudieron inicializar: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
