from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class User(Base, AuditMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")


class Role(Base, AuditMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Permission(Base, AuditMixin):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class UserRole(Base, AuditMixin):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)


class Client(Base, AuditMixin):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    document: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(25))
    email: Mapped[str | None] = mapped_column(String(180))


class Vehicle(Base, AuditMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    plate: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)


class ServiceRequest(Base, AuditMixin):
    __tablename__ = "service_requests"
    __table_args__ = (
        Index("ix_service_requests_status", "status"),
        Index("ix_service_requests_requested_at", "requested_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    opened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    complaint: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Estimate(Base, AuditMixin):
    __tablename__ = "estimates"
    __table_args__ = (Index("ix_estimates_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )


class EstimateItem(Base, AuditMixin):
    __tablename__ = "estimate_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")


class WorkOrder(Base, AuditMixin):
    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_status", "status"),
        Index("ix_work_orders_opened_at", "opened_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.id"), nullable=False
    )
    estimate_id: Mapped[int | None] = mapped_column(ForeignKey("estimates.id"))
    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkOrderStage(Base, AuditMixin):
    __tablename__ = "work_order_stages"
    __table_args__ = (Index("ix_work_order_stages_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkOrderEvent(Base, AuditMixin):
    __tablename__ = "work_order_events"
    __table_args__ = (Index("ix_work_order_events_event_at", "event_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id"), nullable=False, index=True
    )
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("work_order_stages.id"))
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Part(Base, AuditMixin):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class Material(Base, AuditMixin):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class StockItem(Base, AuditMixin):
    __tablename__ = "stock_items"
    __table_args__ = (
        CheckConstraint(
            "(part_id IS NOT NULL AND material_id IS NULL) OR "
            "(part_id IS NULL AND material_id IS NOT NULL)",
            name="ck_stock_items_part_or_material",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"))
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )


class StockMovement(Base, AuditMixin):
    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_moved_at", "moved_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"))


class PurchaseRequest(Base, AuditMixin):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        Index("ix_purchase_requests_status", "status"),
        Index("ix_purchase_requests_requested_at", "requested_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PurchaseOrder(Base, AuditMixin):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_purchase_orders_status", "status"),
        Index("ix_purchase_orders_order_date", "order_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_request_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requests.id"))
    supplier_client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PurchaseOrderItem(Base, AuditMixin):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    stock_item_id: Mapped[int | None] = mapped_column(ForeignKey("stock_items.id"))
    description: Mapped[str | None] = mapped_column(String(240))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")


class AccountReceivable(Base, AuditMixin):
    __tablename__ = "accounts_receivable"
    __table_args__ = (
        Index("ix_accounts_receivable_status", "status"),
        Index("ix_accounts_receivable_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    service_request_id: Mapped[int | None] = mapped_column(ForeignKey("service_requests.id"))
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountPayable(Base, AuditMixin):
    __tablename__ = "accounts_payable"
    __table_args__ = (
        Index("ix_accounts_payable_status", "status"),
        Index("ix_accounts_payable_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CashSession(Base, AuditMixin):
    __tablename__ = "cash_sessions"
    __table_args__ = (Index("ix_cash_sessions_opened_at", "opened_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")


class CashEntry(Base, AuditMixin):
    __tablename__ = "cash_entries"
    __table_args__ = (Index("ix_cash_entries_entry_date", "entry_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_session_id: Mapped[int] = mapped_column(
        ForeignKey("cash_sessions.id"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(240))
    account_receivable_id: Mapped[int | None] = mapped_column(ForeignKey("accounts_receivable.id"))
    account_payable_id: Mapped[int | None] = mapped_column(ForeignKey("accounts_payable.id"))
    entry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Attachment(Base, AuditMixin):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AuditLog(Base, AuditMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)


class Notification(Base, AuditMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_status", "status"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unread")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
