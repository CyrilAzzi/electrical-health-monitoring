"""Watchdog de perte de communication.

Vérifie périodiquement si chaque équipement a envoyé une mesure
dans les dernières X secondes (configurable par équipement).
Génère une alerte 'comm_loss' si le délai est dépassé.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Alert, Equipment, Measurement

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 15  # Fréquence de vérification


async def comm_watchdog_loop():
    """Boucle asynchrone qui vérifie la communication de chaque équipement."""
    logger.info(f"Watchdog communication démarré (intervalle: {CHECK_INTERVAL_SEC}s)")

    while True:
        await asyncio.sleep(CHECK_INTERVAL_SEC)
        try:
            _check_all_equipment()
        except Exception as e:
            logger.error(f"Erreur watchdog communication : {e}")


def _check_all_equipment():
    """Vérifie chaque équipement et crée/résout les alertes comm_loss."""
    db: Session = SessionLocal()
    try:
        equipment_list = db.query(Equipment).all()
        now = datetime.now(timezone.utc)

        for eq in equipment_list:
            timeout = timedelta(seconds=eq.comm_timeout_sec)

            # Dernière mesure reçue
            last = (
                db.query(Measurement)
                .filter(Measurement.equipment_id == eq.equipment_id)
                .order_by(desc(Measurement.timestamp))
                .first()
            )

            # Alerte active existante pour comm_loss
            active_alert = (
                db.query(Alert)
                .filter(
                    Alert.equipment_id == eq.equipment_id,
                    Alert.rule_name == "comm_loss",
                    Alert.is_active == True,
                )
                .first()
            )

            if last is None:
                # Pas encore de mesure — pas d'alerte (l'équipement vient d'être créé)
                continue

            elapsed = now - last.timestamp.replace(tzinfo=timezone.utc)
            is_timeout = elapsed > timeout

            if is_timeout and not active_alert:
                # Créer l'alerte
                minutes = int(elapsed.total_seconds() / 60)
                seconds = int(elapsed.total_seconds()) % 60
                db.add(Alert(
                    equipment_id=eq.equipment_id,
                    rule_name="comm_loss",
                    severity="critical",
                    message=(
                        f"Aucune donnée reçue depuis {minutes}m{seconds:02d}s "
                        f"(seuil : {eq.comm_timeout_sec}s)"
                    ),
                ))
                db.commit()
                logger.warning(
                    f"comm_loss: {eq.equipment_id} — pas de données depuis "
                    f"{minutes}m{seconds:02d}s"
                )

            elif not is_timeout and active_alert:
                # Résoudre l'alerte — la communication a repris
                active_alert.is_active = False
                db.commit()
                logger.info(f"comm_loss résolue: {eq.equipment_id}")

    finally:
        db.close()
