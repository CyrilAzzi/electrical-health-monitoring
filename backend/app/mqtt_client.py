"""Client MQTT qui s'abonne aux mesures des capteurs.

Ecoute le topic `sensors/+/measurements` et insere chaque mesure en BDD
en declenchant l'evaluation des regles d'alerte.
"""

import json
import logging
import os
import threading

import paho.mqtt.client as mqtt

from .database import SessionLocal
from .schemas import MeasurementCreate
from .routes.measurements import _process_measurement

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/+/measurements")


def _on_connect(client, userdata, flags, reason_code, properties):
    """Callback a la connexion : s'abonner au topic."""
    logger.info(f"MQTT connecte (code={reason_code}). Abonnement a {MQTT_TOPIC}")
    client.subscribe(MQTT_TOPIC)


def _on_message(client, userdata, msg):
    """Callback a la reception d'un message MQTT."""
    try:
        payload = json.loads(msg.payload.decode())
        data = MeasurementCreate(**payload)

        db = SessionLocal()
        try:
            _process_measurement(db, data)
            logger.info(f"Mesure MQTT traitee pour {data.equipment_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Erreur traitement message MQTT: {e}")


def start_mqtt_client():
    """Demarre le client MQTT dans un thread daemon."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _on_connect
    client.on_message = _on_message

    def _run():
        try:
            client.connect(MQTT_BROKER, MQTT_PORT)
            client.loop_forever()
        except Exception as e:
            logger.error(f"Impossible de se connecter au broker MQTT: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"Client MQTT demarre ({MQTT_BROKER}:{MQTT_PORT})")
    return client
