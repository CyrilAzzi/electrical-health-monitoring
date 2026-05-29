"""Modeles SQLAlchemy pour les tables PostgreSQL."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Equipment(Base):
    """Un equipement electrique surveille (panneau, transfo, etc.)."""

    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nominal_current: Mapped[float] = mapped_column(Float, default=100.0)
    nominal_voltage: Mapped[float] = mapped_column(Float, default=120.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Measurement(Base):
    """Une mesure de capteurs a un instant donne."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    voltage_a: Mapped[float] = mapped_column(Float)
    voltage_b: Mapped[float] = mapped_column(Float)
    voltage_c: Mapped[float] = mapped_column(Float)
    current_a: Mapped[float] = mapped_column(Float)
    current_b: Mapped[float] = mapped_column(Float)
    current_c: Mapped[float] = mapped_column(Float)
    temperature_1: Mapped[float] = mapped_column(Float)
    temperature_2: Mapped[float] = mapped_column(Float)
    temperature_3: Mapped[float] = mapped_column(Float)
    battery_voltage: Mapped[float] = mapped_column(Float)


class Alert(Base):
    """Alerte generee par le moteur de regles."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(String(100), index=True)
    rule_name: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))  # info, warning, critical
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
