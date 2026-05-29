"""Routes pour les mesures de capteurs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Measurement
from ..schemas import MeasurementCreate, MeasurementRead
from ..alert_rules import evaluate_all_rules
from ..models import Alert, Equipment

router = APIRouter(tags=["measurements"])


def _process_measurement(db: Session, data: MeasurementCreate) -> Measurement:
    """Stocke une mesure et evalue les regles d'alerte. Reutilise par MQTT et API."""
    measurement = Measurement(**data.model_dump())
    db.add(measurement)
    db.flush()

    # Recuperer les parametres nominaux de l'equipement (si existant)
    equipment = (
        db.query(Equipment)
        .filter(Equipment.equipment_id == data.equipment_id)
        .first()
    )
    nominal_current = equipment.nominal_current if equipment else 100.0
    nominal_voltage = equipment.nominal_voltage if equipment else 120.0

    # Historique des temperatures pour la detection de tendance
    recent = (
        db.query(Measurement)
        .filter(Measurement.equipment_id == data.equipment_id)
        .order_by(desc(Measurement.timestamp))
        .limit(5)
        .all()
    )
    temps_history = [
        [m.temperature_1, m.temperature_2, m.temperature_3]
        for m in reversed(recent)
    ]

    # Evaluer les regles
    alerts = evaluate_all_rules(
        data,
        nominal_current=nominal_current,
        nominal_voltage=nominal_voltage,
        temperatures_history=temps_history,
    )

    # Stocker les alertes
    for alert_data in alerts:
        db.add(Alert(**alert_data))

    db.commit()
    db.refresh(measurement)
    return measurement


@router.post("/measurements", response_model=MeasurementRead)
def create_measurement(data: MeasurementCreate, db: Session = Depends(get_db)):
    """Recevoir et stocker une mesure via l'API REST."""
    return _process_measurement(db, data)


@router.get("/measurements/{equipment_id}", response_model=list[MeasurementRead])
def get_measurements(
    equipment_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Recuperer les dernieres mesures d'un equipement."""
    return (
        db.query(Measurement)
        .filter(Measurement.equipment_id == equipment_id)
        .order_by(desc(Measurement.timestamp))
        .limit(limit)
        .all()
    )
