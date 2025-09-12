"""
Sistema de Facturación y Pagos para MSC SRPK v2.0
Maneja suscripciones, facturas, pagos y gestión de clientes.
"""

import json
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import os
import hashlib
import hmac
import time
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)


class SubscriptionStatus(Enum):
    """Estados de suscripción."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"
    EXPIRED = "expired"


class PaymentStatus(Enum):
    """Estados de pago."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentMethod(Enum):
    """Métodos de pago."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    STRIPE = "stripe"


class BillingCycle(Enum):
    """Ciclos de facturación."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class Customer:
    """Cliente del sistema."""
    customer_id: str
    email: str
    name: str
    company: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


@dataclass
class SubscriptionPlan:
    """Plan de suscripción."""
    plan_id: str
    name: str
    description: str
    price: Decimal
    billing_cycle: BillingCycle
    max_prod_environments: int
    max_nonprod_environments: int
    features: List[str]
    trial_days: int = 0
    active: bool = True
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['price'] = float(self.price)
        data['billing_cycle'] = self.billing_cycle.value
        return data


@dataclass
class Subscription:
    """Suscripción de un cliente."""
    subscription_id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    start_date: datetime
    end_date: datetime
    trial_end_date: Optional[datetime] = None
    auto_renew: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['status'] = self.status.value
        data['start_date'] = self.start_date.isoformat()
        data['end_date'] = self.end_date.isoformat()
        if self.trial_end_date:
            data['trial_end_date'] = self.trial_end_date.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


@dataclass
class Invoice:
    """Factura."""
    invoice_id: str
    customer_id: str
    subscription_id: str
    amount: Decimal
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    due_date: datetime = None
    paid_date: Optional[datetime] = None
    description: str = ""
    items: List[Dict[str, Any]] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.due_date is None:
            self.due_date = datetime.now() + timedelta(days=30)
        if self.items is None:
            self.items = []
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['amount'] = float(self.amount)
        data['status'] = self.status.value
        data['due_date'] = self.due_date.isoformat()
        if self.paid_date:
            data['paid_date'] = self.paid_date.isoformat()
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class Payment:
    """Pago."""
    payment_id: str
    invoice_id: str
    customer_id: str
    amount: Decimal
    currency: str = "USD"
    method: PaymentMethod = PaymentMethod.STRIPE
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_id: Optional[str] = None
    gateway_response: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data['amount'] = float(self.amount)
        data['method'] = self.method.value
        data['status'] = self.status.value
        if self.processed_at:
            data['processed_at'] = self.processed_at.isoformat()
        data['created_at'] = self.created_at.isoformat()
        return data


class BillingDatabase:
    """Base de datos para facturación."""
    
    def __init__(self, db_path: str = "billing.db"):
        self.db_path = db_path
        self._init_database()
        self._create_default_plans()
    
    def _init_database(self):
        """Inicializa la base de datos."""
        with sqlite3.connect(self.db_path) as conn:
            # Tabla de clientes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    company TEXT,
                    phone TEXT,
                    address TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Tabla de planes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscription_plans (
                    plan_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    billing_cycle TEXT NOT NULL,
                    max_prod_environments INTEGER NOT NULL,
                    max_nonprod_environments INTEGER NOT NULL,
                    features TEXT NOT NULL,
                    trial_days INTEGER DEFAULT 0,
                    active BOOLEAN DEFAULT 1
                )
            """)
            
            # Tabla de suscripciones
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    trial_end_date TEXT,
                    auto_renew BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                    FOREIGN KEY (plan_id) REFERENCES subscription_plans (plan_id)
                )
            """)
            
            # Tabla de facturas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    status TEXT DEFAULT 'pending',
                    due_date TEXT NOT NULL,
                    paid_date TEXT,
                    description TEXT,
                    items TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (subscription_id)
                )
            """)
            
            # Tabla de pagos
            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    method TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    transaction_id TEXT,
                    gateway_response TEXT,
                    processed_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (invoice_id) REFERENCES invoices (invoice_id),
                    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
                )
            """)
            
            conn.commit()
    
    def _create_default_plans(self):
        """Crea planes por defecto."""
        default_plans = [
            {
                "plan_id": "trial",
                "name": "Trial",
                "description": "Plan de prueba gratuito",
                "price": Decimal("0.00"),
                "billing_cycle": BillingCycle.MONTHLY,
                "max_prod_environments": 1,
                "max_nonprod_environments": 1,
                "features": ["basic_analysis", "basic_testing"],
                "trial_days": 30
            },
            {
                "plan_id": "startup",
                "name": "Startup",
                "description": "Plan para startups y proyectos pequeños",
                "price": Decimal("99.00"),
                "billing_cycle": BillingCycle.MONTHLY,
                "max_prod_environments": 1,
                "max_nonprod_environments": 2,
                "features": ["basic_analysis", "basic_testing", "advanced_metrics"],
                "trial_days": 14
            },
            {
                "plan_id": "enterprise",
                "name": "Enterprise",
                "description": "Plan empresarial con características avanzadas",
                "price": Decimal("990.00"),
                "billing_cycle": BillingCycle.MONTHLY,
                "max_prod_environments": 3,
                "max_nonprod_environments": 5,
                "features": ["basic_analysis", "basic_testing", "advanced_metrics", "security_analysis", "custom_reports"],
                "trial_days": 7
            }
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            for plan_data in default_plans:
                conn.execute("""
                    INSERT OR IGNORE INTO subscription_plans 
                    (plan_id, name, description, price, billing_cycle, 
                     max_prod_environments, max_nonprod_environments, 
                     features, trial_days, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan_data["plan_id"],
                    plan_data["name"],
                    plan_data["description"],
                    float(plan_data["price"]),
                    plan_data["billing_cycle"].value,
                    plan_data["max_prod_environments"],
                    plan_data["max_nonprod_environments"],
                    json.dumps(plan_data["features"]),
                    plan_data["trial_days"],
                    1
                ))
            conn.commit()


class BillingManager:
    """Gestor principal de facturación."""
    
    def __init__(self, db_path: str = "billing.db"):
        self.db = BillingDatabase(db_path)
        self.webhook_secret = os.getenv('BILLING_WEBHOOK_SECRET', 'default_secret')
    
    def create_customer(self, 
                       email: str, 
                       name: str,
                       company: Optional[str] = None,
                       phone: Optional[str] = None,
                       address: Optional[Dict[str, str]] = None) -> Customer:
        """Crea un nuevo cliente."""
        customer_id = str(uuid.uuid4())
        customer = Customer(
            customer_id=customer_id,
            email=email,
            name=name,
            company=company,
            phone=phone,
            address=address
        )
        
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("""
                INSERT INTO customers 
                (customer_id, email, name, company, phone, address, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer.customer_id,
                customer.email,
                customer.name,
                customer.company,
                customer.phone,
                json.dumps(customer.address) if customer.address else None,
                customer.created_at.isoformat(),
                customer.updated_at.isoformat()
            ))
            conn.commit()
        
        logger.info(f"Cliente creado: {customer_id}")
        return customer
    
    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Obtiene un cliente por ID."""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM customers WHERE customer_id = ?
            """, (customer_id,))
            row = cursor.fetchone()
            
            if row:
                return Customer(
                    customer_id=row[0],
                    email=row[1],
                    name=row[2],
                    company=row[3],
                    phone=row[4],
                    address=json.loads(row[5]) if row[5] else None,
                    created_at=datetime.fromisoformat(row[6]),
                    updated_at=datetime.fromisoformat(row[7])
                )
        return None
    
    def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """Obtiene un cliente por email."""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM customers WHERE email = ?
            """, (email,))
            row = cursor.fetchone()
            
            if row:
                return Customer(
                    customer_id=row[0],
                    email=row[1],
                    name=row[2],
                    company=row[3],
                    phone=row[4],
                    address=json.loads(row[5]) if row[5] else None,
                    created_at=datetime.fromisoformat(row[6]),
                    updated_at=datetime.fromisoformat(row[7])
                )
        return None
    
    def get_subscription_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Obtiene un plan de suscripción."""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM subscription_plans WHERE plan_id = ? AND active = 1
            """, (plan_id,))
            row = cursor.fetchone()
            
            if row:
                return SubscriptionPlan(
                    plan_id=row[0],
                    name=row[1],
                    description=row[2],
                    price=Decimal(str(row[3])),
                    billing_cycle=BillingCycle(row[4]),
                    max_prod_environments=row[5],
                    max_nonprod_environments=row[6],
                    features=json.loads(row[7]),
                    trial_days=row[8],
                    active=bool(row[9])
                )
        return None
    
    def create_subscription(self, 
                          customer_id: str,
                          plan_id: str,
                          start_date: Optional[datetime] = None) -> Subscription:
        """Crea una nueva suscripción."""
        plan = self.get_subscription_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan no encontrado: {plan_id}")
        
        subscription_id = str(uuid.uuid4())
        
        if start_date is None:
            start_date = datetime.now()
        
        # Calcular fecha de fin basada en el ciclo de facturación
        if plan.billing_cycle == BillingCycle.MONTHLY:
            end_date = start_date + timedelta(days=30)
        elif plan.billing_cycle == BillingCycle.QUARTERLY:
            end_date = start_date + timedelta(days=90)
        elif plan.billing_cycle == BillingCycle.YEARLY:
            end_date = start_date + timedelta(days=365)
        else:
            end_date = start_date + timedelta(days=30)
        
        # Calcular fecha de fin de prueba
        trial_end_date = None
        if plan.trial_days > 0:
            trial_end_date = start_date + timedelta(days=plan.trial_days)
        
        subscription = Subscription(
            subscription_id=subscription_id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIAL if trial_end_date else SubscriptionStatus.ACTIVE,
            start_date=start_date,
            end_date=end_date,
            trial_end_date=trial_end_date
        )
        
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("""
                INSERT INTO subscriptions 
                (subscription_id, customer_id, plan_id, status, start_date, 
                 end_date, trial_end_date, auto_renew, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subscription.subscription_id,
                subscription.customer_id,
                subscription.plan_id,
                subscription.status.value,
                subscription.start_date.isoformat(),
                subscription.end_date.isoformat(),
                subscription.trial_end_date.isoformat() if subscription.trial_end_date else None,
                subscription.auto_renew,
                subscription.created_at.isoformat(),
                subscription.updated_at.isoformat()
            ))
            conn.commit()
        
        logger.info(f"Suscripción creada: {subscription_id}")
        return subscription
    
    def get_active_subscription(self, customer_id: str) -> Optional[Subscription]:
        """Obtiene la suscripción activa de un cliente."""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM subscriptions 
                WHERE customer_id = ? AND status IN ('active', 'trial')
                ORDER BY created_at DESC
                LIMIT 1
            """, (customer_id,))
            row = cursor.fetchone()
            
            if row:
                return Subscription(
                    subscription_id=row[0],
                    customer_id=row[1],
                    plan_id=row[2],
                    status=SubscriptionStatus(row[3]),
                    start_date=datetime.fromisoformat(row[4]),
                    end_date=datetime.fromisoformat(row[5]),
                    trial_end_date=datetime.fromisoformat(row[6]) if row[6] else None,
                    auto_renew=bool(row[7]),
                    created_at=datetime.fromisoformat(row[8]),
                    updated_at=datetime.fromisoformat(row[9])
                )
        return None
    
    def create_invoice(self, 
                      customer_id: str,
                      subscription_id: str,
                      amount: Decimal,
                      description: str = "",
                      due_date: Optional[datetime] = None) -> Invoice:
        """Crea una nueva factura."""
        invoice_id = str(uuid.uuid4())
        
        if due_date is None:
            due_date = datetime.now() + timedelta(days=30)
        
        invoice = Invoice(
            invoice_id=invoice_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            amount=amount,
            due_date=due_date,
            description=description
        )
        
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("""
                INSERT INTO invoices 
                (invoice_id, customer_id, subscription_id, amount, currency, 
                 status, due_date, description, items, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice.invoice_id,
                invoice.customer_id,
                invoice.subscription_id,
                float(invoice.amount),
                invoice.currency,
                invoice.status.value,
                invoice.due_date.isoformat(),
                invoice.description,
                json.dumps(invoice.items),
                invoice.created_at.isoformat()
            ))
            conn.commit()
        
        logger.info(f"Factura creada: {invoice_id}")
        return invoice
    
    def process_payment(self, 
                       invoice_id: str,
                       payment_method: PaymentMethod,
                       amount: Decimal,
                       transaction_id: Optional[str] = None) -> Payment:
        """Procesa un pago."""
        payment_id = str(uuid.uuid4())
        
        payment = Payment(
            payment_id=payment_id,
            invoice_id=invoice_id,
            customer_id="",  # Se obtendrá de la factura
            amount=amount,
            method=payment_method,
            transaction_id=transaction_id
        )
        
        # Simular procesamiento de pago
        # En producción, esto integraría con Stripe, PayPal, etc.
        payment.status = PaymentStatus.COMPLETED
        payment.processed_at = datetime.now()
        
        with sqlite3.connect(self.db.db_path) as conn:
            # Obtener customer_id de la factura
            cursor = conn.execute("""
                SELECT customer_id FROM invoices WHERE invoice_id = ?
            """, (invoice_id,))
            row = cursor.fetchone()
            if row:
                payment.customer_id = row[0]
            
            # Insertar pago
            conn.execute("""
                INSERT INTO payments 
                (payment_id, invoice_id, customer_id, amount, currency, 
                 method, status, transaction_id, gateway_response, 
                 processed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payment.payment_id,
                payment.invoice_id,
                payment.customer_id,
                float(payment.amount),
                payment.currency,
                payment.method.value,
                payment.status.value,
                payment.transaction_id,
                json.dumps(payment.gateway_response) if payment.gateway_response else None,
                payment.processed_at.isoformat(),
                payment.created_at.isoformat()
            ))
            
            # Actualizar estado de la factura
            conn.execute("""
                UPDATE invoices 
                SET status = ?, paid_date = ?
                WHERE invoice_id = ?
            """, (
                payment.status.value,
                payment.processed_at.isoformat(),
                invoice_id
            ))
            
            conn.commit()
        
        logger.info(f"Pago procesado: {payment_id}")
        return payment
    
    def generate_license_key(self, customer_id: str, plan_id: str) -> str:
        """Genera una clave de licencia."""
        timestamp = int(time.time())
        data = f"{customer_id}:{plan_id}:{timestamp}"
        signature = hmac.new(
            self.webhook_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{plan_id.upper()}{signature[:8]}{timestamp}"
    
    def validate_license_key(self, license_key: str) -> Optional[Dict[str, Any]]:
        """Valida una clave de licencia."""
        try:
            # Extraer información de la clave
            if license_key.startswith("TRIAL"):
                plan_id = "trial"
                signature = license_key[5:13]
                timestamp = int(license_key[13:])
            elif license_key.startswith("STARTUP"):
                plan_id = "startup"
                signature = license_key[7:15]
                timestamp = int(license_key[15:])
            elif license_key.startswith("ENTERPRISE"):
                plan_id = "enterprise"
                signature = license_key[10:18]
                timestamp = int(license_key[18:])
            else:
                return None
            
            # Verificar que la clave no sea muy antigua (30 días)
            if time.time() - timestamp > 2592000:  # 30 días
                return None
            
            # En producción, aquí verificarías la suscripción en la base de datos
            return {
                "plan_id": plan_id,
                "signature": signature,
                "timestamp": timestamp,
                "valid": True
            }
        except (ValueError, IndexError):
            return None
    
    def get_customer_usage_stats(self, customer_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de uso de un cliente."""
        subscription = self.get_active_subscription(customer_id)
        if not subscription:
            return {"error": "No hay suscripción activa"}
        
        plan = self.get_subscription_plan(subscription.plan_id)
        if not plan:
            return {"error": "Plan no encontrado"}
        
        # En producción, esto consultaría métricas reales de uso
        return {
            "subscription": subscription.to_dict(),
            "plan": plan.to_dict(),
            "usage": {
                "prod_environments": 1,  # Simulado
                "nonprod_environments": 2,  # Simulado
                "max_prod_environments": plan.max_prod_environments,
                "max_nonprod_environments": plan.max_nonprod_environments
            },
            "billing": {
                "next_billing_date": subscription.end_date.isoformat(),
                "auto_renew": subscription.auto_renew
            }
        }


# Instancia global del gestor de facturación
_billing_manager = None


def initialize_billing(db_path: str = "billing.db"):
    """Inicializa el sistema de facturación."""
    global _billing_manager
    _billing_manager = BillingManager(db_path)
    logger.info("Sistema de facturación inicializado")


def get_billing_manager() -> BillingManager:
    """Obtiene el gestor de facturación."""
    return _billing_manager
