"""Calcul du score de sante electrique (0-100).

Le score est compose de 5 sous-scores ponderes :
- Courant (25%)      : penalite si proche ou au-dessus du nominal
- Equilibre (20%)    : penalite si desequilibre entre phases
- Temperature (25%)  : penalite si temperatures elevees
- Tendance temp (10%): penalite si temperature en hausse continue
- Batterie (20%)     : penalite si tension batterie basse
"""

from .schemas import MeasurementCreate

WEIGHTS = {
    "current": 0.25,
    "balance": 0.20,
    "temperature": 0.25,
    "temp_trend": 0.10,
    "battery": 0.20,
}


def _score_current(measurement: MeasurementCreate, nominal_current: float) -> float:
    """Score courant : 100 si < 50% nominal, 0 si >= 100% nominal."""
    max_current = max(
        measurement.current_a, measurement.current_b, measurement.current_c
    )
    ratio = max_current / nominal_current if nominal_current > 0 else 1.0
    if ratio <= 0.5:
        return 100.0
    if ratio >= 1.0:
        return 0.0
    # Interpolation lineaire entre 50% et 100%
    return max(0.0, (1.0 - ratio) / 0.5 * 100.0)


def _score_balance(measurement: MeasurementCreate) -> float:
    """Score equilibre : 100 si parfait, 0 si desequilibre > 30%."""
    currents = [measurement.current_a, measurement.current_b, measurement.current_c]
    avg = sum(currents) / 3
    if avg == 0:
        return 100.0

    max_deviation = max(abs(c - avg) for c in currents)
    imbalance_pct = (max_deviation / avg) * 100

    if imbalance_pct <= 5:
        return 100.0
    if imbalance_pct >= 30:
        return 0.0
    return max(0.0, (30.0 - imbalance_pct) / 25.0 * 100.0)


def _score_temperature(measurement: MeasurementCreate) -> float:
    """Score temperature : 100 si < 40C, 0 si >= 80C."""
    max_temp = max(
        measurement.temperature_1, measurement.temperature_2, measurement.temperature_3
    )
    if max_temp <= 40:
        return 100.0
    if max_temp >= 80:
        return 0.0
    return max(0.0, (80.0 - max_temp) / 40.0 * 100.0)


def _score_temp_trend(temperatures_history: list[list[float]] | None) -> float:
    """Score tendance : 100 si stable/en baisse, 0 si hausse continue forte."""
    if not temperatures_history or len(temperatures_history) < 4:
        return 100.0

    averages = [sum(temps) / len(temps) for temps in temperatures_history]
    is_rising = all(averages[i] < averages[i + 1] for i in range(len(averages) - 1))

    if not is_rising:
        return 100.0

    # Penalite proportionnelle a la hausse totale
    delta = averages[-1] - averages[0]
    if delta <= 2:
        return 80.0
    if delta >= 15:
        return 0.0
    return max(0.0, (15.0 - delta) / 13.0 * 80.0)


def _score_battery(measurement: MeasurementCreate) -> float:
    """Score batterie : 100 si >= 13V, 0 si <= 11V."""
    v = measurement.battery_voltage
    if v >= 13.0:
        return 100.0
    if v <= 11.0:
        return 0.0
    return max(0.0, (v - 11.0) / 2.0 * 100.0)


def get_status_label(score: float) -> str:
    """Convertit le score en label textuel."""
    if score >= 100:
        return "Excellent"
    if score >= 70:
        return "Normal"
    if score >= 40:
        return "À surveiller"
    return "Critique"


def compute_health_score(
    measurement: MeasurementCreate,
    nominal_current: float = 100.0,
    temperatures_history: list[list[float]] | None = None,
) -> dict:
    """Calcule le score de sante global et les sous-scores."""
    details = {
        "current": _score_current(measurement, nominal_current),
        "balance": _score_balance(measurement),
        "temperature": _score_temperature(measurement),
        "temp_trend": _score_temp_trend(temperatures_history),
        "battery": _score_battery(measurement),
    }

    score = sum(details[k] * WEIGHTS[k] for k in WEIGHTS)
    score = round(min(100.0, max(0.0, score)), 1)

    return {
        "score": score,
        "status": get_status_label(score),
        "details": {k: round(v, 1) for k, v in details.items()},
    }
