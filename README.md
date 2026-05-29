# Electrical Health Monitoring (EHM)

Plateforme de monitoring intelligent d'equipements electriques. Recoit des mesures de capteurs via MQTT, analyse l'etat de sante, genere des alertes et permet la visualisation via Grafana.

## Stack

- **Backend** : Python 3.11+ / FastAPI
- **Base de donnees** : PostgreSQL + TimescaleDB
- **Messaging** : MQTT (Eclipse Mosquitto)
- **Visualisation** : Grafana
- **Conteneurisation** : Docker Compose

## Demarrage rapide

### 1. Prerequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installe et lance

### 2. Configuration

```bash
cp .env.example .env
```

### 3. Lancer tous les services

```bash
docker compose up --build -d
```

Cela demarre :
| Service     | URL / Port             |
|-------------|------------------------|
| FastAPI     | http://localhost:8000  |
| API Docs    | http://localhost:8000/docs |
| PostgreSQL  | localhost:5432         |
| Mosquitto   | localhost:1883         |
| Grafana     | http://localhost:3000  |

### 4. Creer un equipement

```bash
curl -X POST http://localhost:8000/equipment \
  -H "Content-Type: application/json" \
  -d '{"equipment_id": "PANEL-001", "name": "Panneau principal", "location": "Batiment A", "nominal_current": 100, "nominal_voltage": 120}'
```

### 5. Lancer le simulateur

```bash
# Installer les dependances localement (ou dans un venv)
pip install paho-mqtt

# Mode normal
python backend/scripts/simulate_sensor.py

# Simuler une surchauffe progressive
python backend/scripts/simulate_sensor.py --scenario overheat

# Simuler un desequilibre de courant
python backend/scripts/simulate_sensor.py --scenario imbalance

# Simuler une batterie faible
python backend/scripts/simulate_sensor.py --scenario battery
```

### 6. Consulter les donnees

```bash
# Dernieres mesures
curl http://localhost:8000/measurements/PANEL-001

# Alertes
curl http://localhost:8000/alerts

# Score de sante
curl http://localhost:8000/health-score/PANEL-001
```

### 7. Grafana

1. Ouvrir http://localhost:3000 (admin / admin)
2. Le dashboard "Electrical Health Monitoring" est pre-configure
3. Selectionner l'equipement dans le menu deroulant

## Lancer les tests

```bash
cd backend
pip install -r requirements.txt pytest
pytest tests/ -v
```

## Architecture

```
Simulateur MQTT --> Mosquitto --> FastAPI Backend --> PostgreSQL
                                     |                    |
                                  Alertes             Grafana
                                  Score sante
```

## Regles d'alerte

| Regle                  | Condition                         | Severite  |
|------------------------|-----------------------------------|-----------|
| Surcourant             | Courant > 80% nominal             | warning/critical |
| Desequilibre courant   | Ecart entre phases > 10%          | warning   |
| Temperature elevee     | T > 60 C                          | warning/critical |
| Tendance temperature   | Hausse continue sur 4+ mesures    | warning   |
| Batterie faible        | V < 12.2V                         | warning/critical |
| Tension anormale       | Ecart > 10% du nominal            | warning/critical |

## Score de sante (0-100)

| Plage   | Statut        |
|---------|---------------|
| 100     | Excellent     |
| 70-99   | Normal        |
| 40-69   | A surveiller  |
| 0-39    | Critique      |

## Arreter les services

```bash
docker compose down
```

Pour supprimer aussi les volumes (donnees) :

```bash
docker compose down -v
```
