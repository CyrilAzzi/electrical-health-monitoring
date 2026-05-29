"""Calcul du score de santé électrique (0-100).

Le score est composé de sous-scores pondérés. Les poids s'adaptent
dynamiquement selon les capteurs disponibles :

Avec tous les capteurs :
- Courant (25%), Équilibre (20%), Température (25%), Tendance (10%), Batterie (20%)

Sans tension ni batterie (mode CT + température) :
- Courant (30%), Équilibre (25%), Température (30%), Tendance (15%)
"""

from .schemas import MeasurementCreate

# Poids de base pour chaque sous-score
BASE_WEIGHTS = {
    "current": 25,
    "balance": 20,
    "temperature": 25,
    "temp_trend": 10,
    "battery": 20,
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
    return max(0.0, (1.0 - ratio) / 0.5 * 100.0)


def _score_balance(measurement: MeasurementCreate) -> float:
    """Score équilibre : 100 si parfait, 0 si déséquilibre > 30%."""
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
    """Score température : 100 si < 40C, 0 si >= 80C."""
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

    delta = averages[-1] - averages[0]
    if delta <= 2:
        return 80.0
    if delta >= 15:
        return 0.0
    return max(0.0, (15.0 - delta) / 13.0 * 80.0)


def _score_battery(measurement: MeasurementCreate) -> float | None:
    """Score batterie : 100 si >= 13V, 0 si <= 11V. None si pas de capteur."""
    if measurement.battery_voltage is None:
        return None
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
    """Calcule le score de santé global et les sous-scores.

    Les poids s'adaptent dynamiquement : si la batterie n'est pas mesurée,
    son poids est redistribué proportionnellement aux autres sous-scores.
    """
    # Calculer tous les sous-scores
    raw_scores = {
        "current": _score_current(measurement, nominal_current),
        "balance": _score_balance(measurement),
        "temperature": _score_temperature(measurement),
        "temp_trend": _score_temp_trend(temperatures_history),
        "battery": _score_battery(measurement),
    }

    # Filtrer les sous-scores disponibles (exclure None)
    available = {k: v for k, v in raw_scores.items() if v is not None}

    # Recalculer les poids normalisés
    total_weight = sum(BASE_WEIGHTS[k] for k in available)
    weights = {k: BASE_WEIGHTS[k] / total_weight for k in available}

    # Score pondéré
    score = sum(available[k] * weights[k] for k in available)
    score = round(min(100.0, max(0.0, score)), 1)

    # Détails : inclure tous les sous-scores disponibles
    details = {k: round(v, 1) for k, v in available.items()}

    return {
        "score": score,
        "status": get_status_label(score),
        "details": details,
    }
