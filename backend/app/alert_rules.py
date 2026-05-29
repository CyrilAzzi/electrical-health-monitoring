"""Moteur de règles d'alerte pour les mesures électriques.

Chaque règle retourne une liste d'alertes (dicts) si les conditions sont remplies.
Les seuils sont configurables par équipement via la dataclass AlertThresholds.
"""

from dataclasses import dataclass

from .schemas import MeasurementCreate


@dataclass
class AlertThresholds:
    """Seuils d'alerte configurables par équipement."""

    current_pct: float = 80.0
    temp_max: float = 60.0
    imbalance_pct: float = 10.0
    battery_min: float = 12.2
    voltage_deviation_pct: float = 10.0


def check_overcurrent(
    measurement: MeasurementCreate,
    nominal_current: float,
    threshold_pct: float = 80.0,
) -> list[dict]:
    """Courant dépassant le seuil configuré de la capacité nominale."""
    threshold = nominal_current * (threshold_pct / 100)
    alerts = []
    for phase, value in [
        ("A", measurement.current_a),
        ("B", measurement.current_b),
        ("C", measurement.current_c),
    ]:
        if value > threshold:
            pct = round(value / nominal_current * 100, 1)
            alerts.append({
                "rule_name": "overcurrent",
                "severity": "critical" if value > nominal_current else "warning",
                "message": (
                    f"Phase {phase} : courant {value:.1f} A "
                    f"({pct} % de la capacité nominale de {nominal_current} A, "
                    f"seuil : {threshold_pct} %)"
                ),
            })
    return alerts


def check_current_imbalance(
    measurement: MeasurementCreate,
    threshold_pct: float = 10.0,
) -> list[dict]:
    """Déséquilibre de courant entre phases dépassant le seuil configuré."""
    currents = [measurement.current_a, measurement.current_b, measurement.current_c]
    avg = sum(currents) / 3
    if avg == 0:
        return []

    max_deviation = max(abs(c - avg) for c in currents)
    imbalance_pct = (max_deviation / avg) * 100

    if imbalance_pct > threshold_pct:
        return [{
            "rule_name": "current_imbalance",
            "severity": "warning",
            "message": (
                f"Déséquilibre de courant : {imbalance_pct:.1f} % "
                f"(A={measurement.current_a:.1f}, "
                f"B={measurement.current_b:.1f}, "
                f"C={measurement.current_c:.1f} — "
                f"seuil : {threshold_pct} %)"
            ),
        }]
    return []


def check_high_temperature(
    measurement: MeasurementCreate,
    temp_max: float = 60.0,
) -> list[dict]:
    """Température dépassant le seuil configuré sur un capteur."""
    temp_critical = temp_max + 20  # critique = seuil + 20°C
    alerts = []
    for sensor, value in [
        ("1", measurement.temperature_1),
        ("2", measurement.temperature_2),
        ("3", measurement.temperature_3),
    ]:
        if value > temp_max:
            alerts.append({
                "rule_name": "high_temperature",
                "severity": "critical" if value > temp_critical else "warning",
                "message": (
                    f"Capteur {sensor} : température {value:.1f} °C "
                    f"(seuil : {temp_max} °C)"
                ),
            })
    return alerts


def check_temperature_trend(
    temperatures_history: list[list[float]],
) -> list[dict]:
    """Température en hausse continue sur les N dernières mesures.

    temperatures_history: liste de [temp1, temp2, temp3] des dernières mesures,
    ordonnées du plus ancien au plus récent. Minimum 4 mesures nécessaires.
    """
    if len(temperatures_history) < 4:
        return []

    averages = [sum(temps) / len(temps) for temps in temperatures_history]
    is_rising = all(averages[i] < averages[i + 1] for i in range(len(averages) - 1))

    if is_rising:
        delta = averages[-1] - averages[0]
        return [{
            "rule_name": "temperature_rising",
            "severity": "warning",
            "message": (
                f"Température en hausse continue sur {len(temperatures_history)} mesures "
                f"(+{delta:.1f} °C)"
            ),
        }]
    return []


def check_low_battery(
    measurement: MeasurementCreate,
    battery_min: float = 12.2,
) -> list[dict]:
    """Tension batterie sous le seuil configuré."""
    if measurement.battery_voltage is None:
        return []
    if measurement.battery_voltage < battery_min:
        battery_critical = battery_min - 0.7
        severity = "critical" if measurement.battery_voltage < battery_critical else "warning"
        return [{
            "rule_name": "low_battery",
            "severity": severity,
            "message": (
                f"Tension batterie basse : {measurement.battery_voltage:.1f} V "
                f"(seuil : {battery_min} V)"
            ),
        }]
    return []


def check_abnormal_voltage(
    measurement: MeasurementCreate,
    nominal_voltage: float,
    deviation_pct: float = 10.0,
) -> list[dict]:
    """Tension anormale sur une phase (écart vs nominal dépassant le seuil)."""
    if measurement.voltage_a is None:
        return []
    alerts = []
    threshold = nominal_voltage * (deviation_pct / 100)
    for phase, value in [
        ("A", measurement.voltage_a),
        ("B", measurement.voltage_b),
        ("C", measurement.voltage_c),
    ]:
        if value is None:
            continue
        deviation = abs(value - nominal_voltage)
        if deviation > threshold:
            pct = round(deviation / nominal_voltage * 100, 1)
            alerts.append({
                "rule_name": "abnormal_voltage",
                "severity": "critical" if pct > deviation_pct * 2 else "warning",
                "message": (
                    f"Phase {phase} : tension {value:.1f} V "
                    f"(écart de {pct} % vs nominal {nominal_voltage} V, "
                    f"seuil : {deviation_pct} %)"
                ),
            })
    return alerts


def check_sensor_fault(measurement: MeasurementCreate) -> list[dict]:
    """Détecte les capteurs défectueux ou débranchés.

    - CT débranché : courant = 0 sur une phase alors que les autres sont > 5A
    - Sonde température coupée : lecture aberrante (< -20°C ou > 150°C)
      Le DS18B20 retourne -127°C ou 85°C quand il est défaillant.
    """
    alerts = []

    # CT débranché : une phase à 0 alors que les autres sont actives
    currents = {
        "A": measurement.current_a,
        "B": measurement.current_b,
        "C": measurement.current_c,
    }
    active_phases = [v for v in currents.values() if v > 5.0]
    if len(active_phases) >= 2:
        for phase, value in currents.items():
            if value < 0.1:
                alerts.append({
                    "rule_name": "sensor_fault",
                    "severity": "critical",
                    "message": (
                        f"CT phase {phase} possiblement débranché : "
                        f"courant {value:.1f} A alors que les autres phases sont actives"
                    ),
                })

    # Sonde température défaillante : lecture aberrante
    temps = {
        "1": measurement.temperature_1,
        "2": measurement.temperature_2,
        "3": measurement.temperature_3,
    }
    for sensor, value in temps.items():
        if value < -20 or value > 150:
            alerts.append({
                "rule_name": "sensor_fault",
                "severity": "critical",
                "message": (
                    f"Sonde température {sensor} défaillante : "
                    f"lecture aberrante {value:.1f} °C"
                ),
            })

    return alerts


def check_door_open(measurement: MeasurementCreate) -> list[dict]:
    """Détecte l'ouverture de la porte du panneau électrique."""
    if measurement.door_open is None or not measurement.door_open:
        return []
    return [{
        "rule_name": "door_open",
        "severity": "warning",
        "message": "Porte du panneau électrique ouverte",
    }]


def evaluate_all_rules(
    measurement: MeasurementCreate,
    nominal_current: float = 100.0,
    nominal_voltage: float = 120.0,
    thresholds: AlertThresholds | None = None,
    temperatures_history: list[list[float]] | None = None,
) -> list[dict]:
    """Exécute toutes les règles et retourne la liste complète des alertes."""
    t = thresholds or AlertThresholds()

    alerts = []
    alerts.extend(check_overcurrent(measurement, nominal_current, t.current_pct))
    alerts.extend(check_current_imbalance(measurement, t.imbalance_pct))
    alerts.extend(check_high_temperature(measurement, t.temp_max))
    alerts.extend(check_low_battery(measurement, t.battery_min))
    alerts.extend(check_abnormal_voltage(measurement, nominal_voltage, t.voltage_deviation_pct))
    alerts.extend(check_sensor_fault(measurement))
    alerts.extend(check_door_open(measurement))

    if temperatures_history:
        alerts.extend(check_temperature_trend(temperatures_history))

    for alert in alerts:
        alert["equipment_id"] = measurement.equipment_id

    return alerts
