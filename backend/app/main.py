"""Point d'entree FastAPI pour l'application de monitoring electrique."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, engine
from .mqtt_client import start_mqtt_client
from .routes import alerts, equipment, health, measurements

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cree les tables au demarrage et lance le client MQTT."""
    # Creer les tables si elles n'existent pas
    Base.metadata.create_all(bind=engine)
    logger.info("Tables de base de donnees creees/verifiees")

    # Demarrer le client MQTT
    start_mqtt_client()

    yield  # L'application tourne ici

    logger.info("Arret de l'application")


app = FastAPI(
    title="Electrical Health Monitoring",
    description="Plateforme de monitoring intelligent d'equipements electriques",
    version="0.1.0",
    lifespan=lifespan,
)

# Enregistrer les routes
app.include_router(measurements.router)
app.include_router(equipment.router)
app.include_router(alerts.router)
app.include_router(health.router)


@app.get("/")
def root():
    return {
        "app": "Electrical Health Monitoring",
        "version": "0.1.0",
        "docs": "/docs",
    }
