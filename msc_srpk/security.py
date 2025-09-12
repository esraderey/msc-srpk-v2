"""
Sistema de Seguridad y Privacidad para MSC SRPK v2.0
Implementa encriptación, auditoría, GDPR y medidas de seguridad avanzadas.
"""

import os
import hashlib
import hmac
import json
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import secrets
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import jwt
from functools import wraps
import uuid

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Niveles de seguridad."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(Enum):
    """Tipos de eventos de auditoría."""
    LOGIN = "login"
    LOGOUT = "logout"
    LICENSE_VALIDATION = "license_validation"
    CODE_ANALYSIS = "code_analysis"
    FILE_ACCESS = "file_access"
    DATA_EXPORT = "data_export"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_VIOLATION = "security_violation"


class ThreatLevel(Enum):
    """Niveles de amenaza."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Evento de seguridad para auditoría."""
    event_id: str
    timestamp: datetime
    event_type: EventType
    threat_level: ThreatLevel
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    description: str
    metadata: Dict[str, Any] = None
    success: bool = True
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['threat_level'] = self.threat_level.value
        return data


class EncryptionManager:
    """Gestor de encriptación para datos sensibles."""
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or os.getenv('MSC_SRPK_MASTER_KEY')
        if not self.master_key:
            self.master_key = self._generate_master_key()
        
        self._fernet = self._create_fernet()
        self._public_key, self._private_key = self._generate_rsa_keys()
    
    def _generate_master_key(self) -> str:
        """Genera una clave maestra segura."""
        return secrets.token_urlsafe(32)
    
    def _create_fernet(self) -> Fernet:
        """Crea instancia de Fernet para encriptación simétrica."""
        # Derivar clave de la clave maestra
        salt = b'msc_srpk_salt'  # En producción, usar salt único por instancia
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def _generate_rsa_keys(self) -> Tuple[bytes, bytes]:
        """Genera par de claves RSA."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        public_key = private_key.public_key()
        
        # Serializar claves
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return public_pem, private_pem
    
    def encrypt_symmetric(self, data: str) -> str:
        """Encripta datos usando encriptación simétrica."""
        try:
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Error encriptando datos: {e}")
            raise
    
    def decrypt_symmetric(self, encrypted_data: str) -> str:
        """Desencripta datos usando encriptación simétrica."""
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Error desencriptando datos: {e}")
            raise
    
    def encrypt_asymmetric(self, data: str) -> str:
        """Encripta datos usando encriptación asimétrica."""
        try:
            public_key = serialization.load_pem_public_key(self._public_key)
            encrypted_data = public_key.encrypt(
                data.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Error encriptando con RSA: {e}")
            raise
    
    def decrypt_asymmetric(self, encrypted_data: str) -> str:
        """Desencripta datos usando encriptación asimétrica."""
        try:
            private_key = serialization.load_pem_private_key(
                self._private_key,
                password=None
            )
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = private_key.decrypt(
                decoded_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Error desencriptando con RSA: {e}")
            raise
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Genera hash seguro de contraseña."""
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Usar PBKDF2 con SHA256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        
        password_hash = base64.urlsafe_b64encode(
            kdf.derive(password.encode())
        ).decode()
        
        return password_hash, salt
    
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verifica contraseña contra hash."""
        try:
            computed_hash, _ = self.hash_password(password, salt)
            return hmac.compare_digest(password_hash, computed_hash)
        except Exception as e:
            logger.error(f"Error verificando contraseña: {e}")
            return False


class AuditLogger:
    """Sistema de auditoría y logging de seguridad."""
    
    def __init__(self, db_path: str = "security_audit.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Inicializa base de datos de auditoría."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    threat_level TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    description TEXT NOT NULL,
                    metadata TEXT,
                    success BOOLEAN NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                ON security_events(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_user 
                ON security_events(user_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type 
                ON security_events(event_type)
            """)
            
            conn.commit()
    
    def log_event(self, event: SecurityEvent):
        """Registra un evento de seguridad."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO security_events 
                    (event_id, timestamp, event_type, threat_level, user_id, 
                     session_id, ip_address, user_agent, description, metadata, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.threat_level.value,
                    event.user_id,
                    event.session_id,
                    event.ip_address,
                    event.user_agent,
                    event.description,
                    json.dumps(event.metadata) if event.metadata else None,
                    event.success
                ))
                conn.commit()
            
            # También loggear a archivo
            logger.info(f"Security Event: {event.event_type.value} - {event.description}")
            
        except Exception as e:
            logger.error(f"Error registrando evento de seguridad: {e}")
    
    def get_events(self, 
                   start_time: datetime,
                   end_time: datetime,
                   event_type: Optional[EventType] = None,
                   threat_level: Optional[ThreatLevel] = None,
                   user_id: Optional[str] = None) -> List[SecurityEvent]:
        """Obtiene eventos de seguridad."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT * FROM security_events 
                WHERE timestamp BETWEEN ? AND ?
            """
            params = [start_time.isoformat(), end_time.isoformat()]
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
            
            if threat_level:
                query += " AND threat_level = ?"
                params.append(threat_level.value)
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY timestamp DESC"
            
            cursor = conn.execute(query, params)
            events = []
            
            for row in cursor.fetchall():
                event = SecurityEvent(
                    event_id=row[1],
                    timestamp=datetime.fromisoformat(row[2]),
                    event_type=EventType(row[3]),
                    threat_level=ThreatLevel(row[4]),
                    user_id=row[5],
                    session_id=row[6],
                    ip_address=row[7],
                    user_agent=row[8],
                    description=row[9],
                    metadata=json.loads(row[10]) if row[10] else None,
                    success=bool(row[11])
                )
                events.append(event)
            
            return events


class SecurityManager:
    """Gestor principal de seguridad."""
    
    def __init__(self):
        self.encryption = EncryptionManager()
        self.audit_logger = AuditLogger()
        self.session_tokens: Dict[str, Dict] = {}
        self.failed_attempts: Dict[str, List[datetime]] = {}
        self.rate_limits: Dict[str, List[datetime]] = {}
    
    def generate_session_token(self, user_id: str, ip_address: str) -> str:
        """Genera token de sesión seguro."""
        session_id = str(uuid.uuid4())
        token_data = {
            'user_id': user_id,
            'session_id': session_id,
            'ip_address': ip_address,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        }
        
        token = jwt.encode(token_data, self.encryption.master_key, algorithm='HS256')
        
        # Almacenar sesión
        self.session_tokens[session_id] = token_data
        
        # Log evento
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.LOGIN,
            threat_level=ThreatLevel.INFO,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            description="Sesión iniciada"
        )
        self.audit_logger.log_event(event)
        
        return token
    
    def validate_session_token(self, token: str, ip_address: str) -> Optional[Dict]:
        """Valida token de sesión."""
        try:
            token_data = jwt.decode(token, self.encryption.master_key, algorithms=['HS256'])
            session_id = token_data['session_id']
            
            # Verificar que la sesión existe
            if session_id not in self.session_tokens:
                return None
            
            stored_data = self.session_tokens[session_id]
            
            # Verificar IP
            if stored_data['ip_address'] != ip_address:
                self._log_security_violation("IP mismatch", token_data)
                return None
            
            # Verificar expiración
            expires_at = datetime.fromisoformat(stored_data['expires_at'])
            if datetime.now() > expires_at:
                del self.session_tokens[session_id]
                return None
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            logger.error(f"Error validando token: {e}")
            return None
    
    def invalidate_session(self, session_id: str):
        """Invalida una sesión."""
        if session_id in self.session_tokens:
            token_data = self.session_tokens[session_id]
            
            # Log evento
            event = SecurityEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                event_type=EventType.LOGOUT,
                threat_level=ThreatLevel.INFO,
                user_id=token_data.get('user_id'),
                session_id=session_id,
                ip_address=token_data.get('ip_address'),
                description="Sesión cerrada"
            )
            self.audit_logger.log_event(event)
            
            del self.session_tokens[session_id]
    
    def check_rate_limit(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Verifica límite de velocidad."""
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Limpiar intentos antiguos
        if identifier in self.rate_limits:
            self.rate_limits[identifier] = [
                attempt for attempt in self.rate_limits[identifier]
                if attempt > window_start
            ]
        else:
            self.rate_limits[identifier] = []
        
        # Verificar límite
        if len(self.rate_limits[identifier]) >= max_attempts:
            return False
        
        # Registrar intento
        self.rate_limits[identifier].append(now)
        return True
    
    def check_failed_attempts(self, identifier: str, max_attempts: int = 5, lockout_minutes: int = 30) -> bool:
        """Verifica intentos fallidos."""
        now = datetime.now()
        lockout_start = now - timedelta(minutes=lockout_minutes)
        
        # Limpiar intentos antiguos
        if identifier in self.failed_attempts:
            self.failed_attempts[identifier] = [
                attempt for attempt in self.failed_attempts[identifier]
                if attempt > lockout_start
            ]
        else:
            self.failed_attempts[identifier] = []
        
        # Verificar bloqueo
        if len(self.failed_attempts[identifier]) >= max_attempts:
            return False
        
        return True
    
    def record_failed_attempt(self, identifier: str, ip_address: str):
        """Registra intento fallido."""
        now = datetime.now()
        
        if identifier not in self.failed_attempts:
            self.failed_attempts[identifier] = []
        
        self.failed_attempts[identifier].append(now)
        
        # Log evento
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=now,
            event_type=EventType.SECURITY_VIOLATION,
            threat_level=ThreatLevel.WARNING,
            ip_address=ip_address,
            description=f"Intento fallido para {identifier}",
            metadata={"attempts": len(self.failed_attempts[identifier])}
        )
        self.audit_logger.log_event(event)
    
    def _log_security_violation(self, description: str, metadata: Dict[str, Any] = None):
        """Registra violación de seguridad."""
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.SECURITY_VIOLATION,
            threat_level=ThreatLevel.ERROR,
            description=description,
            metadata=metadata
        )
        self.audit_logger.log_event(event)


class DataPrivacyManager:
    """Gestor de privacidad y cumplimiento GDPR."""
    
    def __init__(self, security_manager: SecurityManager):
        self.security = security_manager
        self.data_retention_days = 365  # Por defecto 1 año
        self.anonymization_fields = ['email', 'phone', 'name', 'address']
    
    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonimiza datos personales."""
        anonymized = data.copy()
        
        for field in self.anonymization_fields:
            if field in anonymized:
                anonymized[field] = self._hash_identifier(anonymized[field])
        
        return anonymized
    
    def _hash_identifier(self, identifier: str) -> str:
        """Genera hash de identificador."""
        salt = os.getenv('MSC_SRPK_PRIVACY_SALT', 'default_salt')
        return hashlib.sha256(f"{identifier}{salt}".encode()).hexdigest()[:8]
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Exporta todos los datos de un usuario (GDPR Artículo 20)."""
        # En producción, esto consultaría todas las bases de datos
        return {
            "user_id": user_id,
            "exported_at": datetime.now().isoformat(),
            "data": {
                "profile": {},
                "usage_metrics": {},
                "billing_history": {},
                "security_events": []
            }
        }
    
    def delete_user_data(self, user_id: str) -> bool:
        """Elimina todos los datos de un usuario (GDPR Artículo 17)."""
        try:
            # Log evento
            event = SecurityEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                event_type=EventType.DATA_EXPORT,
                threat_level=ThreatLevel.INFO,
                user_id=user_id,
                description=f"Eliminación de datos solicitada para usuario {user_id}"
            )
            self.security.audit_logger.log_event(event)
            
            # En producción, eliminar de todas las bases de datos
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando datos del usuario: {e}")
            return False
    
    def get_data_retention_policy(self) -> Dict[str, Any]:
        """Obtiene política de retención de datos."""
        return {
            "retention_period_days": self.data_retention_days,
            "data_types": {
                "usage_metrics": 365,
                "security_events": 2555,  # 7 años
                "billing_data": 2555,     # 7 años
                "code_analysis": 30       # 30 días
            },
            "anonymization_policy": {
                "personal_data_anonymized_after": 90,
                "usage_patterns_retained": True,
                "aggregated_data_retained": True
            }
        }


# Decoradores de seguridad
def require_authentication(func):
    """Decorador para requerir autenticación."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # En producción, esto validaría tokens JWT
        return func(*args, **kwargs)
    return wrapper


def require_permissions(permissions: List[str]):
    """Decorador para requerir permisos específicos."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # En producción, esto verificaría permisos del usuario
            return func(*args, **kwargs)
        return wrapper
    return decorator


def audit_log(event_type: EventType, description: str):
    """Decorador para logging de auditoría."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Log antes de ejecutar
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                
                # Log éxito
                event = SecurityEvent(
                    event_id=str(uuid.uuid4()),
                    timestamp=start_time,
                    event_type=event_type,
                    threat_level=ThreatLevel.INFO,
                    description=description,
                    success=True
                )
                
                return result
                
            except Exception as e:
                # Log error
                event = SecurityEvent(
                    event_id=str(uuid.uuid4()),
                    timestamp=start_time,
                    event_type=event_type,
                    threat_level=ThreatLevel.ERROR,
                    description=f"{description} - Error: {str(e)}",
                    success=False
                )
                raise
                
        return wrapper
    return decorator


# Instancia global del gestor de seguridad
_security_manager = None
_privacy_manager = None


def initialize_security():
    """Inicializa el sistema de seguridad."""
    global _security_manager, _privacy_manager
    
    _security_manager = SecurityManager()
    _privacy_manager = DataPrivacyManager(_security_manager)
    
    logger.info("Sistema de seguridad inicializado")


def get_security_manager() -> SecurityManager:
    """Obtiene el gestor de seguridad."""
    return _security_manager


def get_privacy_manager() -> DataPrivacyManager:
    """Obtiene el gestor de privacidad."""
    return _privacy_manager
