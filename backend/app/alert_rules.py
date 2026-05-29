"""Moteur de regles d'alerte pour les mesures electriques.

Chaque regle retourne une liste d'alertes (dicts) si les conditions sont remplies.
"""

from .schemas import MeasurementCreate


def check_overcurrent(
    measurement: MeasurementCreate, nominal_current: float
) -> list[dict]:
    """Courant > 80% de la capacite nominale sur n'importe quelle phase."""
    threshold = nominal_current * 0.8
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
                    f"Phase {phase}: courant {value:.1f}A "
                    f"({pct}% de la capacite nominale {nominal_current}A)"
                ),
            })
    return alerts


def check_current_imbalance(measurement: MeasurementCreate) -> list[dict]:
    """Desequilibre de courant entre phases > 10%."""
    currents = [measurement.current_a, measurement.current_b, measurement.current_c]
    avg = sum(currents) / 3
    if avg == 0:
        return []

    max_deviation = max(abs(c - avg) for c in currents)
    imbalance_pct = (max_deviation / avg) * 100

    if imbalance_pct > 10:
        return [{
            "rule_name": "current_imbalance",
            "severity": "warning",
            "message": (
                f"Desequilibre de courant: {imbalance_pct:.1f}% "
                f"(A={measurement.current_a:.1f}, "
                f"B={measurement.current_b:.1f}, "
                f"C={measurement.current_c:.1f})"
            ),
        }]
    return []


def check_high_temperature(measurement: MeasurementCreate) -> list[dict]:
    """Temperature > 60 degres C sur n'importe quel capteur."""
    alerts = []
    for sensor, value in [
        ("1", measurement.temperature_1),
        ("2", measurement.temperature_2),
        ("3", measurement.temperature_3),
    ]:
        if value > 60:
            alerts.append({
                "rule_name": "high_temperature",
                "severity": "critical" if value > 80 else "warning",
                "message": f"Capteur {sensor}: temperature {value:.1f} C (seuil: 60 C)",
            })
    return alerts


def check_temperature_trend(
    temperatures_history: list[list[float]],
) -> list[dict]:
    """Temperature en hausse continue sur les N dernieres mesures.

    temperatures_history: liste de [temp1, temp2, temp3] des dernieres mesures,
    ordonnees du plus ancien au plus recent. Minimum 4 mesures necessaires.
    """
    if len(temperatures_history) < 4:
        return []

    # Verifier si la moyenne des temperatures augmente a chaque mesure
    averages = [sum(temps) / len(temps) for temps in temperatures_history]
    is_rising = all(averages[i] < averages[i + 1] for i in range(len(averages) - 1))

    if is_rising:
        delta = averages[-1] - averages[0]
        return [{
            "rule_name": "temperature_rising",
            "severity": "warning",
            "message": (
                f"Temperature en hausse continue sur {len(temperatures_history)} mesures "
                f"(+{delta:.1f} C)"
            ),
        }]
    return []


def check_low_battery(measurement: MeasurementCreate) -> list[dict]:
    """Tension batterie < 12.2V."""
    if measurement.battery_voltage < 12.2:
        severity = "critical" if measurement.battery_voltage < 11.5 else "warning"
        return [{
            "rule_name": "low_battery",
            "severity": severity,
            "message": (
                f"Tension batterie basse: {measurement.battery_voltage:.1f}V "
                f"(seuil: 12.2V)"
            ),
        }]
    return []


def check_abnormal_voltage(
    measurement: MeasurementCreate, nominal_voltage: float
) -> list[dict]:
    """Tension anormale sur une phase (ecart > 10% par rapport au nominal)."""
    alerts = []
    threshold = nominal_voltage * 0.10
    for phase, value in [
        ("A", measurement.voltage_a),
        ("B", measurement.voltage_b),
        ("C", measurement.voltage_c),
    ]:
        deviation = abs(value - nominal_voltage)
        if deviation > threshold:
            pct = round(deviation / nominal_voltage * 100, 1)
            alerts.append({
                "rule_name": "abnormal_voltage",
                "severity": "critical" if pct > 20 else "warning",
                "message": (
                    f"Phase {phase}: tension {value:.1f}V "
                    f"(ecart de {pct}% vs nominal {nominal_voltage}V)"
                ),
            })
    return alerts


def evaluate_all_rules(
    measurement: MeasurementCreate,
    nominal_current: float = 100.0,
    nominal_voltage: float = 120.0,
    temperatures_history: list[list[float]] | None = None,
) -> list[dict]:
    """Execute toutes les regles et retourne la liste complete des alertes."""
    alerts = []
    alerts.extend(check_overcurrent(measurement, nominal_current))
    alerts.extend(check_current_imbalance(measurement))
    alerts.extend(check_high_temperature(measurement))
    alerts.extend(check_low_battery(measurement))
    alerts.extend(check_abnormal_voltage(measurement, nominal_voltage))

    if temperatures_history:
        alerts.extend(check_temperature_trend(temperatures_history))

    # Ajouter l'equipment_id a chaque alerte
    for alert in alerts:
        alert["equipment_id"] = measurement.equipment_id

    return alerts
