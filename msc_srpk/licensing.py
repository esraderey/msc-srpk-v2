"""
Sistema de Licencias y Autenticación para MSC SRPK v2.0
Maneja licencias comerciales, validación y límites de uso.
"""

import hashlib
import hmac
import json
import time
import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import os
import platform
import getpass

logger = logging.getLogger(__name__)


class LicenseType(Enum):
    """Tipos de licencia disponibles."""
    TRIAL = "trial"
    STARTUP = "startup"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class LicenseStatus(Enum):
    """Estados de la licencia."""
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    REVOKED = "revoked"
    TRIAL_EXPIRED = "trial_expired"


@dataclass
class LicenseInfo:
    """Información de la licencia."""
    license_id: str
    license_type: LicenseType
    customer_id: str
    customer_name: str
    email: str
    issued_at: datetime
    expires_at: Optional[datetime]
    max_prod_environments: int
    max_nonprod_environments: int
    features: List[str]
    machine_fingerprint: str
    version: str = "2.0.0"
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['license_type'] = self.license_type.value
        data['issued_at'] = self.issued_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LicenseInfo':
        """Crea desde diccionario."""
        data = data.copy()
        data['license_type'] = LicenseType(data['license_type'])
        data['issued_at'] = datetime.fromisoformat(data['issued_at'])
        if data.get('expires_at'):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)


class MachineFingerprint:
    """Genera huella digital única de la máquina."""
    
    @staticmethod
    def generate() -> str:
        """Genera huella digital de la máquina."""
        components = [
            platform.system(),
            platform.release(),
            platform.version(),
            platform.machine(),
            platform.processor(),
            getpass.getuser(),
            os.getenv('COMPUTERNAME', ''),
            os.getenv('HOSTNAME', ''),
        ]
        
        # Filtrar valores vacíos y crear hash
        fingerprint_data = ''.join(filter(None, components))
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


class LicenseValidator:
    """Validador de licencias con verificación local y remota."""
    
    def __init__(self, license_server_url: str = "https://licenses.mscsrpk.com"):
        self.license_server_url = license_server_url
        self.secret_key = os.getenv('MSC_SRPK_LICENSE_KEY', 'default_key_change_in_production')
        self.cache_file = os.path.expanduser('~/.msc-srpk/license_cache.json')
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Asegura que el directorio de cache existe."""
        cache_dir = os.path.dirname(self.cache_file)
        os.makedirs(cache_dir, exist_ok=True)
    
    def generate_license_request(self, license_key: str) -> Dict:
        """Genera solicitud de licencia."""
        machine_fp = MachineFingerprint.generate()
        timestamp = int(time.time())
        
        request_data = {
            'license_key': license_key,
            'machine_fingerprint': machine_fp,
            'timestamp': timestamp,
            'version': '2.0.0',
            'platform': platform.system(),
        }
        
        # Firmar la solicitud
        signature = self._sign_data(request_data)
        request_data['signature'] = signature
        
        return request_data
    
    def _sign_data(self, data: Dict) -> str:
        """Firma datos con HMAC."""
        # Crear string ordenado para firma
        sorted_data = sorted(data.items())
        data_string = json.dumps(sorted_data, separators=(',', ':'))
        return hmac.new(
            self.secret_key.encode(),
            data_string.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def validate_license(self, license_key: str, force_remote: bool = False) -> Tuple[LicenseStatus, Optional[LicenseInfo]]:
        """Valida una licencia."""
        try:
            # Verificar cache primero (si no se fuerza remoto)
            if not force_remote:
                cached_license = self._load_cached_license()
                if cached_license and self._is_cache_valid(cached_license):
                    status = self._validate_license_info(cached_license)
                    if status == LicenseStatus.VALID:
                        logger.info("Licencia validada desde cache")
                        return status, cached_license
            
            # Validación remota
            logger.info("Validando licencia con servidor remoto")
            return self._validate_remote_license(license_key)
            
        except Exception as e:
            logger.error(f"Error validando licencia: {e}")
            return LicenseStatus.INVALID, None
    
    def _load_cached_license(self) -> Optional[LicenseInfo]:
        """Carga licencia desde cache."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    return LicenseInfo.from_dict(data)
        except Exception as e:
            logger.warning(f"Error cargando cache de licencia: {e}")
        return None
    
    def _save_cached_license(self, license_info: LicenseInfo):
        """Guarda licencia en cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(license_info.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Error guardando cache de licencia: {e}")
    
    def _is_cache_valid(self, license_info: LicenseInfo) -> bool:
        """Verifica si el cache es válido."""
        # Cache válido por 24 horas
        cache_age = time.time() - os.path.getmtime(self.cache_file)
        return cache_age < 86400
    
    def _validate_remote_license(self, license_key: str) -> Tuple[LicenseStatus, Optional[LicenseInfo]]:
        """Valida licencia con servidor remoto."""
        try:
            request_data = self.generate_license_request(license_key)
            
            # En producción, esto sería una llamada HTTPS real
            # Por ahora, simulamos la respuesta
            response = self._simulate_license_server(request_data)
            
            if response.get('valid'):
                license_info = LicenseInfo.from_dict(response['license'])
                
                # Verificar huella digital
                current_fp = MachineFingerprint.generate()
                if license_info.machine_fingerprint != current_fp:
                    logger.warning("Huella digital de máquina no coincide")
                    return LicenseStatus.INVALID, None
                
                # Guardar en cache
                self._save_cached_license(license_info)
                
                status = self._validate_license_info(license_info)
                return status, license_info
            else:
                return LicenseStatus.INVALID, None
                
        except Exception as e:
            logger.error(f"Error en validación remota: {e}")
            return LicenseStatus.INVALID, None
    
    def _simulate_license_server(self, request_data: Dict) -> Dict:
        """Simula respuesta del servidor de licencias."""
        # En producción, esto sería una llamada real al servidor
        license_key = request_data['license_key']
        
        # Simular diferentes tipos de licencia basado en la clave
        if license_key.startswith('TRIAL'):
            return {
                'valid': True,
                'license': {
                    'license_id': str(uuid.uuid4()),
                    'license_type': 'trial',
                    'customer_id': 'trial_user',
                    'customer_name': 'Usuario de Prueba',
                    'email': 'trial@example.com',
                    'issued_at': datetime.now().isoformat(),
                    'expires_at': (datetime.now() + timedelta(days=30)).isoformat(),
                    'max_prod_environments': 1,
                    'max_nonprod_environments': 1,
                    'features': ['basic_analysis', 'basic_testing'],
                    'machine_fingerprint': request_data['machine_fingerprint'],
                    'version': '2.0.0'
                }
            }
        elif license_key.startswith('STARTUP'):
            return {
                'valid': True,
                'license': {
                    'license_id': str(uuid.uuid4()),
                    'license_type': 'startup',
                    'customer_id': 'startup_customer',
                    'customer_name': 'Cliente Startup',
                    'email': 'startup@example.com',
                    'issued_at': datetime.now().isoformat(),
                    'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),
                    'max_prod_environments': 1,
                    'max_nonprod_environments': 2,
                    'features': ['basic_analysis', 'basic_testing', 'advanced_metrics'],
                    'machine_fingerprint': request_data['machine_fingerprint'],
                    'version': '2.0.0'
                }
            }
        elif license_key.startswith('ENTERPRISE'):
            return {
                'valid': True,
                'license': {
                    'license_id': str(uuid.uuid4()),
                    'license_type': 'enterprise',
                    'customer_id': 'enterprise_customer',
                    'customer_name': 'Cliente Enterprise',
                    'email': 'enterprise@example.com',
                    'issued_at': datetime.now().isoformat(),
                    'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),
                    'max_prod_environments': 3,
                    'max_nonprod_environments': 5,
                    'features': ['basic_analysis', 'basic_testing', 'advanced_metrics', 'security_analysis', 'custom_reports'],
                    'machine_fingerprint': request_data['machine_fingerprint'],
                    'version': '2.0.0'
                }
            }
        else:
            return {'valid': False, 'error': 'Invalid license key'}
    
    def _validate_license_info(self, license_info: LicenseInfo) -> LicenseStatus:
        """Valida información de licencia."""
        now = datetime.now()
        
        # Verificar expiración
        if license_info.expires_at and now > license_info.expires_at:
            if license_info.license_type == LicenseType.TRIAL:
                return LicenseStatus.TRIAL_EXPIRED
            else:
                return LicenseStatus.EXPIRED
        
        return LicenseStatus.VALID


class LicenseManager:
    """Gestor principal de licencias."""
    
    def __init__(self):
        self.validator = LicenseValidator()
        self.current_license: Optional[LicenseInfo] = None
        self.license_key: Optional[str] = None
    
    def set_license_key(self, license_key: str):
        """Establece la clave de licencia."""
        self.license_key = license_key
    
    def validate_and_load(self, license_key: str = None) -> bool:
        """Valida y carga la licencia."""
        if license_key:
            self.license_key = license_key
        
        if not self.license_key:
            logger.error("No hay clave de licencia establecida")
            return False
        
        status, license_info = self.validator.validate_license(self.license_key)
        
        if status == LicenseStatus.VALID:
            self.current_license = license_info
            logger.info(f"Licencia válida: {license_info.license_type.value} para {license_info.customer_name}")
            return True
        else:
            logger.error(f"Licencia inválida: {status.value}")
            return False
    
    def check_feature_access(self, feature: str) -> bool:
        """Verifica acceso a una característica."""
        if not self.current_license:
            return False
        
        return feature in self.current_license.features
    
    def check_environment_limit(self, environment_type: str) -> bool:
        """Verifica límites de entornos."""
        if not self.current_license:
            return False
        
        # En una implementación real, esto verificaría entornos activos
        if environment_type == 'prod':
            return True  # Simplificado para demo
        elif environment_type == 'nonprod':
            return True  # Simplificado para demo
        
        return False
    
    def get_license_info(self) -> Optional[Dict]:
        """Obtiene información de la licencia actual."""
        if self.current_license:
            return self.current_license.to_dict()
        return None
    
    def refresh_license(self) -> bool:
        """Refresca la licencia desde el servidor."""
        if not self.license_key:
            return False
        
        return self.validate_and_load(force_remote=True)


# Instancia global del gestor de licencias
license_manager = LicenseManager()


def require_license(license_key: str = None):
    """Decorador para requerir licencia válida."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not license_manager.validate_and_load(license_key):
                raise LicenseError("Licencia inválida o expirada")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_feature(feature: str):
    """Decorador para requerir característica específica."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not license_manager.check_feature_access(feature):
                raise LicenseError(f"Característica '{feature}' no disponible en tu plan")
            return func(*args, **kwargs)
        return wrapper
    return decorator


class LicenseError(Exception):
    """Excepción para errores de licencia."""
    pass


def initialize_license(license_key: str) -> bool:
    """Inicializa el sistema de licencias."""
    try:
        return license_manager.validate_and_load(license_key)
    except Exception as e:
        logger.error(f"Error inicializando licencia: {e}")
        return False


def get_license_info() -> Optional[Dict]:
    """Obtiene información de la licencia actual."""
    return license_manager.get_license_info()


def check_license_status() -> LicenseStatus:
    """Verifica el estado actual de la licencia."""
    if not license_manager.current_license:
        return LicenseStatus.INVALID
    
    return license_manager.validator._validate_license_info(license_manager.current_license)
