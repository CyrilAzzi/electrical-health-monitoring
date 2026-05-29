"""Tests unitaires pour le calcul du score de santé."""

from app.health_score import compute_health_score, get_status_label
from app.schemas import MeasurementCreate


def _make_measurement(**overrides) -> MeasurementCreate:
    defaults = {
        "equipment_id": "TEST-001",
        "voltage_a": 120.0,
        "voltage_b": 120.0,
        "voltage_c": 120.0,
        "current_a": 30.0,
        "current_b": 30.0,
        "current_c": 30.0,
        "temperature_1": 30.0,
        "temperature_2": 30.0,
        "temperature_3": 30.0,
        "battery_voltage": 13.5,
    }
    defaults.update(overrides)
    return MeasurementCreate(**defaults)


class TestStatusLabels:
    def test_excellent(self):
        assert get_status_label(100) == "Excellent"

    def test_normal(self):
        assert get_status_label(85) == "Normal"
        assert get_status_label(70) == "Normal"

    def test_a_surveiller(self):
        assert get_status_label(50) == "À surveiller"
        assert get_status_label(40) == "À surveiller"

    def test_critique(self):
        assert get_status_label(39) == "Critique"
        assert get_status_label(0) == "Critique"


class TestHealthScore:
    def test_perfect_system(self):
        m = _make_measurement()
        result = compute_health_score(m, nominal_current=100)
        assert result["score"] == 100.0
        assert result["status"] == "Excellent"

    def test_high_current_lowers_score(self):
        m = _make_measurement(current_a=90, current_b=90, current_c=90)
        result = compute_health_score(m, nominal_current=100)
        assert result["score"] < 100
        assert result["details"]["current"] < 100

    def test_high_temperature_lowers_score(self):
        m = _make_measurement(temperature_1=70, temperature_2=70, temperature_3=70)
        result = compute_health_score(m, nominal_current=100)
        assert result["details"]["temperature"] < 100

    def test_low_battery_lowers_score(self):
        m = _make_measurement(battery_voltage=11.5)
        result = compute_health_score(m, nominal_current=100)
        assert result["details"]["battery"] < 100

    def test_imbalance_lowers_score(self):
        m = _make_measurement(current_a=80, current_b=40, current_c=40)
        result = compute_health_score(m, nominal_current=100)
        assert result["details"]["balance"] < 100

    def test_critical_system(self):
        """Tout est mauvais : le score doit être très bas."""
        m = _make_measurement(
            current_a=110, current_b=40, current_c=40,
            temperature_1=85, temperature_2=85, temperature_3=85,
            battery_voltage=10.5,
        )
        result = compute_health_score(m, nominal_current=100)
        assert result["score"] < 40
        assert result["status"] == "Critique"

    def test_score_bounds(self):
        """Le score doit toujours être entre 0 et 100."""
        m = _make_measurement()
        result = compute_health_score(m, nominal_current=100)
        assert 0 <= result["score"] <= 100

    def test_temp_trend_penalizes(self):
        m = _make_measurement()
        history = [[30, 30, 30], [35, 35, 35], [40, 40, 40], [45, 45, 45]]
        result = compute_health_score(m, nominal_current=100, temperatures_history=history)
        assert result["details"]["temp_trend"] < 100
