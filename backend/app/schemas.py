"""Schemas Pydantic v2 pour la validation des donnees API."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- Equipment ---

class EquipmentCreate(BaseModel):
    equipment_id: str = Field(..., examples=["PANEL-001"])
    name: str = Field(..., examples=["Panneau principal"])
    location: str | None = Field(None, examples=["Bâtiment A, Salle 12"])
    nominal_current: float = Field(100.0, gt=0, description="Courant nominal en ampères")
    nominal_voltage: float = Field(120.0, gt=0, description="Tension nominale en volts")
    # Seuils d'alerte configurables
    alert_current_pct: float = Field(80.0, gt=0, le=100, description="Seuil de surcourant (% du nominal)")
    alert_temp_max: float = Field(60.0, gt=0, description="Température max avant alerte (°C)")
    alert_imbalance_pct: float = Field(10.0, gt=0, le=100, description="Seuil de déséquilibre entre phases (%)")
    alert_battery_min: float = Field(12.2, gt=0, description="Tension batterie minimale (V)")
    alert_voltage_deviation_pct: float = Field(10.0, gt=0, le=100, description="Écart de tension max vs nominal (%)")


class EquipmentRead(EquipmentCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Measurement ---

class MeasurementCreate(BaseModel):
    equipment_id: str
    timestamp: datetime | None = None
    # Courant (obligatoire)
    current_a: float = Field(..., ge=0)
    current_b: float = Field(..., ge=0)
    current_c: float = Field(..., ge=0)
    # Température (obligatoire)
    temperature_1: float
    temperature_2: float
    temperature_3: float
    # Tension (optionnel — absent si pas de capteurs de tension)
    voltage_a: float | None = None
    voltage_b: float | None = None
    voltage_c: float | None = None
    # Batterie (optionnel — absent si pas d'UPS)
    battery_voltage: float | None = Field(None, ge=0)


class MeasurementRead(MeasurementCreate):
    id: int
    timestamp: datetime

    model_config = {"from_attributes": True}


# --- Alert ---

class AlertRead(BaseModel):
    id: int
    equipment_id: str
    rule_name: str
    severity: str
    message: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Health Score ---

class HealthScoreResponse(BaseModel):
    equipment_id: str
    score: float = Field(..., ge=0, le=100)
    status: str  # Excellent, Normal, À surveiller, Critique
    details: dict[str, float]  # sous-scores individuels
