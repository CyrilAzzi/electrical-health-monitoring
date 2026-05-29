"""Tests unitaires pour les règles d'alerte."""

from app.alert_rules import (
    AlertThresholds,
    check_abnormal_voltage,
    check_current_imbalance,
    check_door_open,
    check_high_temperature,
    check_low_battery,
    check_overcurrent,
    check_sensor_fault,
    check_temperature_trend,
    evaluate_all_rules,
)
from app.schemas import MeasurementCreate


def _make_measurement(**overrides) -> MeasurementCreate:
    """Helper : crée une mesure avec des valeurs par défaut normales."""
    defaults = {
        "equipment_id": "TEST-001",
        "voltage_a": 120.0,
        "voltage_b": 120.0,
        "voltage_c": 120.0,
        "current_a": 50.0,
        "current_b": 50.0,
        "current_c": 50.0,
        "temperature_1": 35.0,
        "temperature_2": 35.0,
        "temperature_3": 35.0,
        "battery_voltage": 13.0,
    }
    defaults.update(overrides)
    return MeasurementCreate(**defaults)


# --- Overcurrent ---

class TestOvercurrent:
    def test_no_alert_when_normal(self):
        m = _make_measurement(current_a=50, current_b=50, current_c=50)
        assert check_overcurrent(m, nominal_current=100) == []

    def test_warning_at_85_percent(self):
        m = _make_measurement(current_a=85, current_b=50, current_c=50)
        alerts = check_overcurrent(m, nominal_current=100)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"
        assert alerts[0]["rule_name"] == "overcurrent"

    def test_critical_above_nominal(self):
        m = _make_measurement(current_a=110, current_b=50, current_c=50)
        alerts = check_overcurrent(m, nominal_current=100)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"

    def test_multiple_phases(self):
        m = _make_measurement(current_a=90, current_b=95, current_c=50)
        alerts = check_overcurrent(m, nominal_current=100)
        assert len(alerts) == 2

    def test_custom_threshold(self):
        m = _make_measurement(current_a=70, current_b=50, current_c=50)
        assert check_overcurrent(m, nominal_current=100, threshold_pct=80) == []
        alerts = check_overcurrent(m, nominal_current=100, threshold_pct=60)
        assert len(alerts) == 1

    def test_message_contains_threshold(self):
        m = _make_measurement(current_a=85)
        alerts = check_overcurrent(m, nominal_current=100, threshold_pct=80)
        assert "seuil" in alerts[0]["message"]
        assert "80" in alerts[0]["message"]


# --- Current Imbalance ---

class TestCurrentImbalance:
    def test_balanced(self):
        m = _make_measurement(current_a=50, current_b=50, current_c=50)
        assert check_current_imbalance(m) == []

    def test_slight_imbalance_ok(self):
        m = _make_measurement(current_a=52, current_b=50, current_c=49)
        assert check_current_imbalance(m) == []

    def test_imbalance_detected(self):
        m = _make_measurement(current_a=70, current_b=50, current_c=50)
        alerts = check_current_imbalance(m)
        assert len(alerts) == 1
        assert "séquilibre" in alerts[0]["message"].lower()

    def test_zero_currents(self):
        m = _make_measurement(current_a=0, current_b=0, current_c=0)
        assert check_current_imbalance(m) == []

    def test_custom_threshold(self):
        m = _make_measurement(current_a=55, current_b=50, current_c=50)
        assert check_current_imbalance(m, threshold_pct=10) == []
        alerts = check_current_imbalance(m, threshold_pct=3)
        assert len(alerts) == 1


# --- High Temperature ---

class TestHighTemperature:
    def test_normal_temperature(self):
        m = _make_measurement(temperature_1=40, temperature_2=38, temperature_3=42)
        assert check_high_temperature(m) == []

    def test_warning_above_60(self):
        m = _make_measurement(temperature_1=65, temperature_2=40, temperature_3=40)
        alerts = check_high_temperature(m)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"

    def test_critical_above_80(self):
        m = _make_measurement(temperature_1=85)
        alerts = check_high_temperature(m)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"

    def test_custom_threshold(self):
        m = _make_measurement(temperature_1=55)
        assert check_high_temperature(m, temp_max=60) == []
        alerts = check_high_temperature(m, temp_max=50)
        assert len(alerts) == 1


# --- Temperature Trend ---

class TestTemperatureTrend:
    def test_not_enough_data(self):
        assert check_temperature_trend([[30, 30, 30], [31, 31, 31]]) == []

    def test_stable_no_alert(self):
        history = [[35, 35, 35], [35, 35, 35], [35, 35, 35], [35, 35, 35]]
        assert check_temperature_trend(history) == []

    def test_rising_trend(self):
        history = [[30, 30, 30], [32, 32, 32], [34, 34, 34], [36, 36, 36]]
        alerts = check_temperature_trend(history)
        assert len(alerts) == 1
        assert alerts[0]["rule_name"] == "temperature_rising"

    def test_mixed_trend_no_alert(self):
        history = [[30, 30, 30], [35, 35, 35], [32, 32, 32], [36, 36, 36]]
        assert check_temperature_trend(history) == []


# --- Low Battery ---

class TestLowBattery:
    def test_healthy_battery(self):
        m = _make_measurement(battery_voltage=13.0)
        assert check_low_battery(m) == []

    def test_warning_battery(self):
        m = _make_measurement(battery_voltage=12.0)
        alerts = check_low_battery(m)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"

    def test_critical_battery(self):
        m = _make_measurement(battery_voltage=11.0)
        alerts = check_low_battery(m)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"

    def test_custom_threshold(self):
        m = _make_measurement(battery_voltage=12.5)
        assert check_low_battery(m, battery_min=12.2) == []
        alerts = check_low_battery(m, battery_min=13.0)
        assert len(alerts) == 1


# --- Abnormal Voltage ---

class TestAbnormalVoltage:
    def test_normal_voltage(self):
        m = _make_measurement(voltage_a=120, voltage_b=119, voltage_c=121)
        assert check_abnormal_voltage(m, nominal_voltage=120) == []

    def test_low_voltage(self):
        m = _make_measurement(voltage_a=100)
        alerts = check_abnormal_voltage(m, nominal_voltage=120)
        assert len(alerts) == 1
        assert "Phase A" in alerts[0]["message"]

    def test_high_voltage(self):
        m = _make_measurement(voltage_a=150)
        alerts = check_abnormal_voltage(m, nominal_voltage=120)
        assert len(alerts) == 1

    def test_custom_threshold(self):
        m = _make_measurement(voltage_a=130)
        assert check_abnormal_voltage(m, nominal_voltage=120, deviation_pct=10) == []
        alerts = check_abnormal_voltage(m, nominal_voltage=120, deviation_pct=5)
        assert len(alerts) == 1


# --- Evaluate All ---

class TestEvaluateAll:
    def test_no_alerts_for_healthy_system(self):
        m = _make_measurement()
        alerts = evaluate_all_rules(m)
        assert len(alerts) == 0

    def test_multiple_alerts_combined(self):
        m = _make_measurement(current_a=90, temperature_1=70, battery_voltage=11.5)
        alerts = evaluate_all_rules(m, nominal_current=100)
        rule_names = {a["rule_name"] for a in alerts}
        assert "overcurrent" in rule_names
        assert "high_temperature" in rule_names
        assert "low_battery" in rule_names

    def test_alerts_have_equipment_id(self):
        m = _make_measurement(equipment_id="EQ-42", current_a=90)
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert all(a["equipment_id"] == "EQ-42" for a in alerts)

    def test_custom_thresholds_object(self):
        m = _make_measurement(current_a=70, current_b=70, current_c=70,
                              temperature_1=55, battery_voltage=12.5)
        # Avec seuils par défaut : pas d'alertes
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert len(alerts) == 0
        # Avec seuils stricts : alertes
        strict = AlertThresholds(current_pct=60, temp_max=50, battery_min=13.0)
        alerts = evaluate_all_rules(m, nominal_current=100, thresholds=strict)
        rule_names = {a["rule_name"] for a in alerts}
        assert "overcurrent" in rule_names
        assert "high_temperature" in rule_names
        assert "low_battery" in rule_names

    def test_messages_have_accents(self):
        m = _make_measurement(current_a=90, temperature_1=65)
        alerts = evaluate_all_rules(m, nominal_current=100)
        messages = " ".join(a["message"] for a in alerts)
        assert "capacité" in messages
        assert "°C" in messages


# --- Mode CT + Température seulement (sans tension ni batterie) ---

def _make_ct_only_measurement(**overrides) -> MeasurementCreate:
    """Helper : mesure CT + température seulement, sans tension ni batterie."""
    defaults = {
        "equipment_id": "TEST-CT",
        "current_a": 50.0,
        "current_b": 50.0,
        "current_c": 50.0,
        "temperature_1": 35.0,
        "temperature_2": 35.0,
        "temperature_3": 35.0,
    }
    defaults.update(overrides)
    return MeasurementCreate(**defaults)


class TestCTOnlyMode:
    def test_no_alerts_for_healthy_ct_only(self):
        m = _make_ct_only_measurement()
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert len(alerts) == 0

    def test_overcurrent_works_without_voltage(self):
        m = _make_ct_only_measurement(current_a=90)
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert any(a["rule_name"] == "overcurrent" for a in alerts)

    def test_no_voltage_alerts_when_absent(self):
        m = _make_ct_only_measurement()
        alerts = evaluate_all_rules(m, nominal_current=100, nominal_voltage=120)
        assert not any(a["rule_name"] == "abnormal_voltage" for a in alerts)

    def test_no_battery_alerts_when_absent(self):
        m = _make_ct_only_measurement()
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert not any(a["rule_name"] == "low_battery" for a in alerts)

    def test_temperature_alert_works(self):
        m = _make_ct_only_measurement(temperature_1=70)
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert any(a["rule_name"] == "high_temperature" for a in alerts)

    def test_imbalance_works_without_voltage(self):
        m = _make_ct_only_measurement(current_a=70, current_b=45, current_c=45)
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert any(a["rule_name"] == "current_imbalance" for a in alerts)


# --- Capteur défectueux ---

class TestSensorFault:
    def test_no_fault_when_all_normal(self):
        m = _make_measurement()
        assert check_sensor_fault(m) == []

    def test_ct_disconnected_one_phase(self):
        """CT débranché sur phase B : courant = 0 alors que A et C sont actives."""
        m = _make_measurement(current_a=45, current_b=0, current_c=48)
        alerts = check_sensor_fault(m)
        assert len(alerts) == 1
        assert alerts[0]["rule_name"] == "sensor_fault_ct_b"
        assert alerts[0]["severity"] == "critical"
        assert "phase B" in alerts[0]["message"]

    def test_no_fault_when_all_zero(self):
        """Panneau éteint (tout à 0) : pas de faux positif."""
        m = _make_measurement(current_a=0, current_b=0, current_c=0)
        assert check_sensor_fault(m) == []

    def test_temp_probe_broken_negative(self):
        """DS18B20 retourne -127°C quand il est défaillant."""
        m = _make_measurement(temperature_2=-127)
        alerts = check_sensor_fault(m)
        assert len(alerts) == 1
        assert "défaillante" in alerts[0]["message"]
        assert "capteur" in alerts[0]["message"].lower() or "sonde" in alerts[0]["message"].lower()

    def test_temp_probe_broken_high(self):
        """Lecture aberrante > 150°C."""
        m = _make_measurement(temperature_1=200)
        alerts = check_sensor_fault(m)
        assert len(alerts) == 1

    def test_normal_high_temp_not_fault(self):
        """70°C est élevé mais pas aberrant — pas une faute capteur."""
        m = _make_measurement(temperature_1=70)
        assert check_sensor_fault(m) == []

    def test_multiple_faults(self):
        """CT débranché + sonde cassée en même temps."""
        m = _make_measurement(current_a=50, current_b=0, current_c=45, temperature_3=-127)
        alerts = check_sensor_fault(m)
        assert len(alerts) == 2


# --- Ouverture de porte ---

class TestDoorOpen:
    def test_no_alert_when_door_absent(self):
        m = _make_measurement()
        assert check_door_open(m) == []

    def test_no_alert_when_door_closed(self):
        m = _make_measurement(door_open=False)
        assert check_door_open(m) == []

    def test_alert_when_door_open(self):
        m = _make_measurement(door_open=True)
        alerts = check_door_open(m)
        assert len(alerts) == 1
        assert alerts[0]["rule_name"] == "door_open"
        assert alerts[0]["severity"] == "warning"

    def test_door_open_in_evaluate_all(self):
        m = _make_measurement(door_open=True)
        alerts = evaluate_all_rules(m, nominal_current=100)
        assert any(a["rule_name"] == "door_open" for a in alerts)
