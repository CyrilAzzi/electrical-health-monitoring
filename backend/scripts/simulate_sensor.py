"""Simulateur de capteurs electriques.

Publie des mesures fictives via MQTT. Peut simuler des scenarios :
  - normal   : valeurs stables et saines
  - overheat : temperature qui monte progressivement
  - imbalance: desequilibre de courant croissant
  - battery  : tension batterie qui descend

Usage:
  python simulate_sensor.py                          # mode normal
  python simulate_sensor.py --scenario overheat      # temperature monte
  python simulate_sensor.py --scenario imbalance     # courant desequilibre
  python simulate_sensor.py --scenario battery       # batterie faiblit
  python simulate_sensor.py --equipment PANEL-002    # equipement specifique
  python simulate_sensor.py --interval 2             # toutes les 2 secondes
"""

import argparse
import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def generate_normal():
    """Mesures normales avec leger bruit."""
    return {
        "voltage_a": round(120 + random.gauss(0, 1.5), 1),
        "voltage_b": round(120 + random.gauss(0, 1.5), 1),
        "voltage_c": round(120 + random.gauss(0, 1.5), 1),
        "current_a": round(45 + random.gauss(0, 3), 1),
        "current_b": round(45 + random.gauss(0, 3), 1),
        "current_c": round(45 + random.gauss(0, 3), 1),
        "temperature_1": round(35 + random.gauss(0, 2), 1),
        "temperature_2": round(34 + random.gauss(0, 2), 1),
        "temperature_3": round(36 + random.gauss(0, 2), 1),
        "battery_voltage": round(13.2 + random.gauss(0, 0.1), 2),
    }


def generate_overheat(step: int):
    """Temperature qui monte de 1 degre a chaque mesure."""
    base = generate_normal()
    rise = min(step * 1.0, 50)  # plafond a +50C
    base["temperature_1"] = round(35 + rise + random.gauss(0, 0.5), 1)
    base["temperature_2"] = round(34 + rise * 0.8 + random.gauss(0, 0.5), 1)
    base["temperature_3"] = round(36 + rise * 0.9 + random.gauss(0, 0.5), 1)
    return base


def generate_imbalance(step: int):
    """Desequilibre de courant croissant sur la phase A."""
    base = generate_normal()
    extra = min(step * 2.0, 40)
    base["current_a"] = round(45 + extra + random.gauss(0, 1), 1)
    base["current_b"] = round(45 + random.gauss(0, 1), 1)
    base["current_c"] = round(45 + random.gauss(0, 1), 1)
    return base


def generate_battery(step: int):
    """Tension batterie qui descend progressivement."""
    base = generate_normal()
    drop = min(step * 0.1, 3.0)
    base["battery_voltage"] = round(13.5 - drop + random.gauss(0, 0.05), 2)
    return base


def generate_ct_only(step: int = 0):
    """Mode CT + température seulement (pas de capteurs de tension)."""
    return {
        "current_a": round(45 + random.gauss(0, 3), 1),
        "current_b": round(45 + random.gauss(0, 3), 1),
        "current_c": round(45 + random.gauss(0, 3), 1),
        "temperature_1": round(35 + random.gauss(0, 2), 1),
        "temperature_2": round(34 + random.gauss(0, 2), 1),
        "temperature_3": round(36 + random.gauss(0, 2), 1),
    }


def generate_ct_overheat(step: int):
    """Mode CT seulement avec surchauffe progressive."""
    base = generate_ct_only()
    rise = min(step * 1.0, 50)
    base["temperature_1"] = round(35 + rise + random.gauss(0, 0.5), 1)
    base["temperature_2"] = round(34 + rise * 0.8 + random.gauss(0, 0.5), 1)
    base["temperature_3"] = round(36 + rise * 0.9 + random.gauss(0, 0.5), 1)
    return base


def generate_fault(step: int):
    """Simule un capteur défectueux : CT débranché + sonde température cassée."""
    base = generate_normal()
    if step >= 3:
        base["current_b"] = 0.0  # CT phase B débranché
    if step >= 6:
        base["temperature_2"] = -127.0  # DS18B20 défaillant
    return base


def generate_door(step: int):
    """Simule une ouverture de porte du panneau."""
    base = generate_normal()
    # Porte ouverte entre les mesures 5 et 12
    base["door_open"] = 5 <= step <= 12
    return base


SCENARIOS = {
    "normal": lambda step: generate_normal(),
    "overheat": generate_overheat,
    "imbalance": generate_imbalance,
    "battery": generate_battery,
    "ct_only": lambda step: generate_ct_only(step),
    "ct_overheat": generate_ct_overheat,
    "fault": generate_fault,
    "door": generate_door,
}


def main():
    parser = argparse.ArgumentParser(description="Simulateur de capteurs electriques")
    parser.add_argument("--broker", default="localhost", help="Adresse du broker MQTT")
    parser.add_argument("--port", type=int, default=1883, help="Port MQTT")
    parser.add_argument("--equipment", default="PANEL-001", help="ID de l'equipement")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="normal",
        help="Scenario de simulation",
    )
    parser.add_argument(
        "--interval", type=float, default=3.0, help="Intervalle entre mesures (sec)"
    )
    parser.add_argument(
        "--count", type=int, default=0, help="Nombre de mesures (0 = infini)"
    )
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.broker, args.port)
    client.loop_start()

    topic = f"sensors/{args.equipment}/measurements"
    generator = SCENARIOS[args.scenario]

    print(f"Simulateur demarre: {args.scenario} -> {topic}")
    print(f"Intervalle: {args.interval}s | Broker: {args.broker}:{args.port}")
    print("Ctrl+C pour arreter\n")

    step = 0
    try:
        while args.count == 0 or step < args.count:
            data = generator(step)
            data["equipment_id"] = args.equipment
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

            payload = json.dumps(data)
            client.publish(topic, payload)

            line = (f"[{step:04d}] Publie: I=[{data['current_a']:.1f}, "
                   f"{data['current_b']:.1f}, {data['current_c']:.1f}]A  "
                   f"T=[{data['temperature_1']:.1f}, {data['temperature_2']:.1f}, "
                   f"{data['temperature_3']:.1f}]C")
            if "battery_voltage" in data:
                line += f"  Bat={data['battery_voltage']:.2f}V"
            if "voltage_a" in data:
                line += f"  V=[{data['voltage_a']:.1f}, {data['voltage_b']:.1f}, {data['voltage_c']:.1f}]"
            if data.get("door_open"):
                line += "  DOOR=OPEN"
            print(line)

            step += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nArrete apres {step} mesures.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
