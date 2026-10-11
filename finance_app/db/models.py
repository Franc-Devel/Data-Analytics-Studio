"""
Nexo Analytics - Modelos de Datos del Núcleo Empresarial (SQLAlchemy 2.0 ORM)
Incluye Usuarios/RBAC, Ficha 360 de Clientes, Pipeline, Tareas, Auditoría y Cola de WhatsApp.
"""

from __future__ import annotations
import datetime
from typing import List, Optional, Any, Dict
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
    Enum as SQLEnum,
    event,
)
from sqlalchemy.orm import declarative_base, relationship, validates
from finance_app.db.crypto import (
    EncryptedString,
    EncryptedText,
    compute_blind_index,
    compute_name_tokens_index,
    compute_phone_tokens_index,
)
from finance_app.db.session import Base


def utc_now() -> datetime.datetime:
    """Retorna la fecha/hora UTC actual naive para compatibilidad con bases de datos y Python 3.12+."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class User(Base):
    """Modelo de Usuario corporativo con roles de acceso (RBAC)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="closer")  # admin, manager, closer, viewer
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Seguridad y bloqueo por fuerza bruta
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False, nullable=False)
    # Campos heredados de MFA: se conservan para compatibilidad con bases existentes.
    mfa_secret = Column(EncryptedString, nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_recovery_codes_hash = Column(EncryptedText, nullable=True)
    last_totp_code_used = Column(String(10), nullable=True)
    session_token_version = Column(Integer, default=1, nullable=False)
    password_changed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Relaciones
    assigned_customers = relationship("Customer", back_populates="assigned_user", foreign_keys="Customer.assigned_user_id")
    assigned_opportunities = relationship("Opportunity", back_populates="assigned_closer", foreign_keys="Opportunity.assigned_closer_id")
    assigned_tasks = relationship("Task", back_populates="assigned_user", foreign_keys="Task.assigned_user_id")
    activity_logs = relationship("ActivityLog", back_populates="user")
    assignment_rules = relationship("AssignmentRule", back_populates="assigned_user")

    @property
    def is_locked(self) -> bool:
        """Determina si la cuenta de usuario se encuentra actualmente bloqueada por fuerza bruta."""
        if not self.locked_until:
            return False
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        return self.locked_until > now

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Customer(Base):
    """Ficha 360° del Cliente y Prospecto Comercial (PII Cifrada con AES-256-GCM)."""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    remote_id = Column(String(50), nullable=True, index=True)  # ID en Excel / sistema externo
    full_name = Column(EncryptedString, nullable=False)
    name_blind_index = Column(String(64), index=True, nullable=True)
    name_tokens_index = Column(Text, index=True, nullable=True)
    phone = Column(EncryptedString, nullable=False)
    phone_blind_index = Column(String(64), index=True, nullable=True)
    phone_tokens_index = Column(Text, index=True, nullable=True)
    email = Column(EncryptedString, nullable=True)
    company = Column(EncryptedString, nullable=True)
    document_id = Column(EncryptedString, nullable=True)  # CUIT / DNI Cifrado

    # Geomarketing y Segmentación
    province = Column(String(80), nullable=True, index=True)
    locality = Column(String(100), nullable=True)
    region = Column(String(80), nullable=True, index=True)
    product_line = Column(String(80), nullable=True, index=True)
    lead_score = Column(Integer, default=50, nullable=False)
    segment = Column(String(30), default="WARM", nullable=False)  # HOT, WARM, COLD, REACTIVADO, DERIVADO
    status = Column(String(40), default="NUEVO", nullable=False, index=True)  # NUEVO, EN_SEGUIMIENTO, CALIFICADO, COTIZADO, GANADO, PERDIDO, DESCARTADO

    # Asignación y Cadencia
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    first_contact_at = Column(DateTime, nullable=True)
    last_contact_at = Column(DateTime, nullable=True)
    next_follow_up_at = Column(DateTime, nullable=True)
    total_contacts = Column(Integer, default=1, nullable=False)
    notes = Column(EncryptedText, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    @validates("phone")
    def _validate_phone(self, key: str, value: Any) -> Any:
        if value and isinstance(value, str):
            clean = value.strip()
            if not clean.startswith("aesgcm:"):
                self.phone_blind_index = compute_blind_index(clean, is_phone=True)
                self.phone_tokens_index = compute_phone_tokens_index(clean)
        return value

    @validates("full_name")
    def _validate_full_name(self, key: str, value: Any) -> Any:
        if value and isinstance(value, str):
            clean = value.strip()
            if not clean.startswith("aesgcm:"):
                self.name_blind_index = compute_blind_index(clean, is_phone=False)
                self.name_tokens_index = compute_name_tokens_index(clean, self.company)
        return value

    @validates("company")
    def _validate_company(self, key: str, value: Any) -> Any:
        if value and isinstance(value, str):
            clean = value.strip()
            if not clean.startswith("aesgcm:"):
                self.name_tokens_index = compute_name_tokens_index(self.full_name, clean)
        return value

    # Relaciones
    assigned_user = relationship("User", back_populates="assigned_customers", foreign_keys=[assigned_user_id])
    opportunities = relationship("Opportunity", back_populates="customer", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="customer", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="customer", cascade="all, delete-orphan", order_by="desc(ActivityLog.created_at)")
    queued_messages = relationship("WhatsAppQueueMessage", back_populates="customer", cascade="all, delete-orphan")
    search_tokens = relationship("CustomerSearchToken", back_populates="customer", cascade="all, delete-orphan")
    pending_proposals = relationship("PendingCRMProposal", back_populates="customer", cascade="all, delete-orphan", order_by="desc(PendingCRMProposal.created_at)")

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name='{self.full_name}', phone='{self.phone}', score={self.lead_score})>"


class CustomerSearchToken(Base):
    """Índice HMAC normalizado para búsquedas parciales sin exponer datos personales."""
    __tablename__ = "customer_search_tokens"
    __table_args__ = (
        UniqueConstraint("customer_id", "token_type", "token_hash", name="uq_customer_search_token"),
        Index("ix_customer_search_token_lookup", "token_type", "token_hash", "customer_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    token_type = Column(String(16), nullable=False)
    token_hash = Column(String(64), nullable=False)
    customer = relationship("Customer", back_populates="search_tokens")


class Opportunity(Base):
    """Oportunidad de Venta y Pipeline Comercial."""
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    product = Column(String(80), nullable=False)
    amount_ars = Column(Float, default=0.0, nullable=False)
    stage = Column(String(50), default="PROSPECCION", nullable=False, index=True)  # PROSPECCION, CONTACTADO, REUNION_AGENDADA, PROPUESTA_ENVIADA, NEGOCIACION, CERRADO_GANADO, CERRADO_PERDIDO
    probability_pct = Column(Integer, default=20, nullable=False)
    expected_close_date = Column(Date, nullable=True)
    assigned_closer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = Column(EncryptedText, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relaciones
    customer = relationship("Customer", back_populates="opportunities")
    assigned_closer = relationship("User", back_populates="assigned_opportunities", foreign_keys=[assigned_closer_id])
    tasks = relationship("Task", back_populates="opportunity")

    def __repr__(self) -> str:
        return f"<Opportunity(id={self.id}, title='{self.title}', amount={self.amount_ars}, stage='{self.stage}')>"


class Task(Base):
    """Tarea Operativa de Seguimiento y Vencimiento."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    title = Column(String(150), nullable=False)
    task_type = Column(String(40), default="WHATSAPP", nullable=False)  # WHATSAPP, LLAMADA, REUNION, PRESUPUESTO, EMAIL
    priority = Column(String(20), default="MEDIA", nullable=False)  # BAJA, MEDIA, ALTA, URGENTE
    status = Column(String(20), default="PENDIENTE", nullable=False, index=True)  # PENDIENTE, EN_PROGRESO, COMPLETADA, CANCELADA
    due_date = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relaciones
    customer = relationship("Customer", back_populates="tasks")
    opportunity = relationship("Opportunity", back_populates="tasks")
    assigned_user = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_user_id])

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', due='{self.due_date}', status='{self.status}')>"


class ActivityLog(Base):
    """Historial Cronológico de Interacciones Multicanal (Llamadas, WhatsApp, Notas)."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    channel = Column(String(30), default="WHATSAPP", nullable=False)  # WHATSAPP, CALL, MEETING, EMAIL, NOTE, SYSTEM
    direction = Column(String(10), default="OUTBOUND", nullable=False)  # INBOUND, OUTBOUND
    summary = Column(String(255), nullable=False)
    content = Column(EncryptedText, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    # Relaciones
    customer = relationship("Customer", back_populates="activities")
    user = relationship("User", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog(id={self.id}, channel='{self.channel}', summary='{self.summary}')>"


class AuditLog(Base):
    """Registro Inmutable de Auditoría y Trazabilidad Corporativa con Hash Chaining."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=False, default="system")
    action = Column(String(50), nullable=False, index=True)  # LOGIN, CREATE, UPDATE, DELETE, EXPORT, IMPORT, SYNC
    entity_type = Column(String(50), nullable=False, index=True)  # Customer, Opportunity, Task, User, Config
    entity_id = Column(String(50), nullable=True)
    old_data_json = Column(Text, nullable=True)
    new_data_json = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Encadenamiento Criptográfico para Integridad e Inmutabilidad (SHA-256)
    prev_hash = Column(String(64), nullable=True, index=True)
    entry_hash = Column(String(64), nullable=True, index=True)

    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user='{self.username}', action='{self.action}', entity='{self.entity_type}')>"


class AssignmentRule(Base):
    """Reglas de Asignación Automática de Leads a Closers."""
    __tablename__ = "assignment_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    product_line = Column(String(80), nullable=True)
    province_or_region = Column(String(80), nullable=True)
    min_lead_score = Column(Integer, default=0, nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    priority_order = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    assigned_user = relationship("User", back_populates="assignment_rules")

    def __repr__(self) -> str:
        return f"<AssignmentRule(id={self.id}, name='{self.name}', priority={self.priority_order})>"


class WhatsAppQueueMessage(Base):
    """Cola de Mensajería Saliente de WhatsApp con Reintentos y Backoff."""
    __tablename__ = "whatsapp_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    phone = Column(EncryptedString, nullable=False, index=True)
    message_text = Column(EncryptedText, nullable=False)
    media_path = Column(String(255), nullable=True)
    priority = Column(Integer, default=5, nullable=False)  # 1 (máxima) a 10 (mínima)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, PROCESSING, SENT, FAILED, CANCELLED
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    customer = relationship("Customer", back_populates="queued_messages")

    def __repr__(self) -> str:
        return f"<WhatsAppQueueMessage(id={self.id}, phone='{self.phone}', status='{self.status}', attempts={self.attempts})>"


class PendingCRMProposal(Base):
    """
    Propuestas de actualización generadas por la IA local (Patrón Lightfield CRM).
    Permite validar cambios de etapa, compromisos/tareas y riesgos sugeridos antes de aplicarlos (Human-in-the-Loop).
    """
    __tablename__ = "pending_crm_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_log_id = Column(Integer, ForeignKey("activity_logs.id", ondelete="SET NULL"), nullable=True)

    proposal_type = Column(String(50), nullable=False)  # STAGE_UPDATE, COMMITMENT_TASK, DEAL_RISK
    current_value = Column(String(255), nullable=True)
    suggested_value = Column(String(255), nullable=False)

    rationale = Column(Text, nullable=False)
    source_quote = Column(Text, nullable=False)
    confidence_score = Column(Float, default=1.0)

    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime, default=utc_now, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    # Relaciones
    customer = relationship("Customer", back_populates="pending_proposals")
    activity_log = relationship("ActivityLog")

    def __repr__(self) -> str:
        return f"<PendingCRMProposal(id={self.id}, type='{self.proposal_type}', status='{self.status}')>"

