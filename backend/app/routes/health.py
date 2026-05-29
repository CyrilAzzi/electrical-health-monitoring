"""Route pour le score de sante d'un equipement."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..health_score import compute_health_score
from ..models import Equipment, Measurement
from ..schemas import HealthScoreResponse, MeasurementCreate

router = APIRouter(tags=["health"])


@router.get("/health-score/{equipment_id}", response_model=HealthScoreResponse)
def get_health_score(equipment_id: str, db: Session = Depends(get_db)):
    """Calculer le score de sante a partir de la derniere mesure."""
    # Derniere mesure
    last = (
        db.query(Measurement)
        .filter(Measurement.equipment_id == equipment_id)
        .order_by(desc(Measurement.timestamp))
        .first()
    )
    if not last:
        raise HTTPException(status_code=404, detail="Aucune mesure trouvee")

    # Parametres nominaux
    equipment = (
        db.query(Equipment)
        .filter(Equipment.equipment_id == equipment_id)
        .first()
    )
    nominal_current = equipment.nominal_current if equipment else 100.0

    # Historique temperatures (5 dernieres mesures)
    recent = (
        db.query(Measurement)
        .filter(Measurement.equipment_id == equipment_id)
        .order_by(desc(Measurement.timestamp))
        .limit(5)
        .all()
    )
    temps_history = [
        [m.temperature_1, m.temperature_2, m.temperature_3]
        for m in reversed(recent)
    ]

    # Construire un schema a partir du modele DB
    measurement_data = MeasurementCreate(
        equipment_id=last.equipment_id,
        voltage_a=last.voltage_a,
        voltage_b=last.voltage_b,
        voltage_c=last.voltage_c,
        current_a=last.current_a,
        current_b=last.current_b,
        current_c=last.current_c,
        temperature_1=last.temperature_1,
        temperature_2=last.temperature_2,
        temperature_3=last.temperature_3,
        battery_voltage=last.battery_voltage,
    )

    result = compute_health_score(
        measurement_data,
        nominal_current=nominal_current,
        temperatures_history=temps_history,
    )
    return HealthScoreResponse(equipment_id=equipment_id, **result)
