"""Routes pour les mesures de capteurs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..alert_rules import AlertThresholds, evaluate_all_rules
from ..database import get_db
from ..models import Alert, Equipment, Measurement
from ..schemas import MeasurementCreate, MeasurementRead

router = APIRouter(tags=["measurements"])


def _get_thresholds(equipment: Equipment | None) -> AlertThresholds:
    """Construit les seuils d'alerte depuis l'équipement ou les valeurs par défaut."""
    if not equipment:
        return AlertThresholds()
    return AlertThresholds(
        current_pct=equipment.alert_current_pct,
        temp_max=equipment.alert_temp_max,
        imbalance_pct=equipment.alert_imbalance_pct,
        battery_min=equipment.alert_battery_min,
        voltage_deviation_pct=equipment.alert_voltage_deviation_pct,
    )


def _process_measurement(db: Session, data: MeasurementCreate) -> Measurement:
    """Stocke une mesure, évalue les règles d'alerte et déduplique."""
    measurement = Measurement(**data.model_dump())
    db.add(measurement)
    db.flush()

    # Récupérer les paramètres de l'équipement
    equipment = (
        db.query(Equipment)
        .filter(Equipment.equipment_id == data.equipment_id)
        .first()
    )
    nominal_current = equipment.nominal_current if equipment else 100.0
    nominal_voltage = equipment.nominal_voltage if equipment else 120.0
    thresholds = _get_thresholds(equipment)

    # Historique des températures pour la détection de tendance
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

    # Évaluer les règles
    new_alerts = evaluate_all_rules(
        data,
        nominal_current=nominal_current,
        nominal_voltage=nominal_voltage,
        thresholds=thresholds,
        temperatures_history=temps_history,
    )

    # Alertes actives existantes pour cet équipement
    active_rules = set(
        r for (r,) in db.query(Alert.rule_name)
        .filter(Alert.equipment_id == data.equipment_id, Alert.is_active == True)
        .all()
    )

    # Désactiver les alertes dont la condition n'est plus remplie
    new_rule_names = {a["rule_name"] for a in new_alerts}
    rules_to_resolve = active_rules - new_rule_names
    if rules_to_resolve:
        db.query(Alert).filter(
            Alert.equipment_id == data.equipment_id,
            Alert.is_active == True,
            Alert.rule_name.in_(rules_to_resolve),
        ).update({"is_active": False}, synchronize_session="fetch")

    # Ne créer que les alertes pour des règles pas encore actives
    for alert_data in new_alerts:
        if alert_data["rule_name"] not in active_rules:
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
    """Récupérer les dernières mesures d'un équipement."""
    return (
        db.query(Measurement)
        .filter(Measurement.equipment_id == equipment_id)
        .order_by(desc(Measurement.timestamp))
        .limit(limit)
        .all()
    )
