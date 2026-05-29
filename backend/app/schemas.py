"""Schemas Pydantic v2 pour la validation des donnees API."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- Equipment ---

class EquipmentCreate(BaseModel):
    equipment_id: str = Field(..., examples=["PANEL-001"])
    name: str = Field(..., examples=["Panneau principal"])
    location: str | None = Field(None, examples=["Batiment A, Salle 12"])
    nominal_current: float = Field(100.0, gt=0, description="Courant nominal en amperes")
    nominal_voltage: float = Field(120.0, gt=0, description="Tension nominale en volts")


class EquipmentRead(EquipmentCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Measurement ---

class MeasurementCreate(BaseModel):
    equipment_id: str
    timestamp: datetime | None = None
    voltage_a: float
    voltage_b: float
    voltage_c: float
    current_a: float = Field(..., ge=0)
    current_b: float = Field(..., ge=0)
    current_c: float = Field(..., ge=0)
    temperature_1: float
    temperature_2: float
    temperature_3: float
    battery_voltage: float = Field(..., ge=0)


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
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Health Score ---

class HealthScoreResponse(BaseModel):
    equipment_id: str
    score: float = Field(..., ge=0, le=100)
    status: str  # excellent, normal, a_surveiller, critique
    details: dict[str, float]  # sous-scores individuels
