# Electrical Health Monitoring (EHM)

Plateforme de monitoring intelligent d'équipements électriques. Reçoit des mesures de capteurs via MQTT, analyse l'état de santé, génère des alertes et permet la visualisation via Grafana.

Conçue pour surveiller en temps réel les panneaux électriques triphasés (120/208V et 347/600V) dans les bâtiments commerciaux, institutionnels et industriels.

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend API | Python 3.11+ / FastAPI / Pydantic v2 |
| Base de données | PostgreSQL + TimescaleDB |
| ORM | SQLAlchemy 2.0 |
| Messaging | MQTT (Eclipse Mosquitto) |
| Visualisation | Grafana 10.4.2 |
| Conteneurisation | Docker Compose (4 services) |

## Architecture

```
                                    ┌──────────────┐
  Capteurs / ESP32  ──── MQTT ────► │  Mosquitto   │
  (ou simulateur)                   │  Broker      │
                                    └──────┬───────┘
                                           │
                                           ▼
                                    ┌──────────────┐         ┌─────────────────┐
                                    │  FastAPI     │ ──SQL──►│  PostgreSQL     │
                                    │  Backend     │         │  + TimescaleDB  │
                                    │  - MQTT sub  │         └────────┬────────┘
                                    │  - Alertes   │                  │
                                    │  - Score     │                  │
                                    └──────────────┘         ┌───────┴────────┐
                                                             │    Grafana     │
                                                             │   Dashboards   │
                                                             └────────────────┘
```

## Fonctionnalités

### Mesures en temps réel
- Tension sur 3 phases (voltage_a, voltage_b, voltage_c)
- Courant sur 3 phases (current_a, current_b, current_c)
- 3 points de température (temperature_1, temperature_2, temperature_3)
- Tension batterie de secours (battery_voltage)

### 6 règles d'alerte avec seuils configurables

| Règle | Condition par défaut | Sévérité |
|-------|---------------------|----------|
| Surcourant | Courant > 80% du nominal | warning / critical |
| Déséquilibre courant | Écart entre phases > 10% | warning |
| Température élevée | T > 60 °C | warning / critical |
| Tendance température | Hausse continue sur 4+ mesures | warning |
| Batterie faible | V < 12.2V | warning / critical |
| Tension anormale | Écart > 10% du nominal | warning / critical |

Tous les seuils sont **configurables par équipement** via l'API.

### Score de santé (0-100)

Moyenne pondérée de 5 sous-scores :
- Courant (25%) : pénalité si proche du nominal
- Équilibre (20%) : pénalité si déséquilibre entre phases
- Température (25%) : pénalité si températures élevées
- Tendance température (10%) : pénalité si hausse continue
- Batterie (20%) : pénalité si tension basse

| Plage | Statut |
|-------|--------|
| 100 | Excellent |
| 70-99 | Normal |
| 40-69 | À surveiller |
| 0-39 | Critique |

### Déduplication des alertes
- Une alerte active n'est **pas recréée** à chaque mesure
- Quand la condition disparaît, l'alerte est marquée comme résolue (`is_active = false`)
- Réduit le bruit : ~9 alertes au lieu de ~50+ pour un scénario de surchauffe de 25 mesures

### API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/equipment` | Créer un équipement avec seuils personnalisés |
| GET | `/equipment` | Lister tous les équipements |
| POST | `/measurements` | Envoyer une mesure (alternative à MQTT) |
| GET | `/measurements/{equipment_id}` | Dernières mesures d'un équipement |
| GET | `/alerts` | Alertes (filtres: equipment_id, severity) |
| GET | `/health-score/{equipment_id}` | Score de santé actuel |

### Dashboard Grafana
5 panels pré-configurés :
- Voltage par phase (timeseries)
- Courant par phase (timeseries)
- Températures (timeseries)
- Tension batterie (timeseries)
- Alertes récentes (table)

Variable `equipment_id` pour filtrer par équipement.

## Démarrage rapide

### 1. Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé

### 2. Configuration

```bash
cp .env.example .env
```

### 3. Lancer tous les services

```bash
docker compose up --build -d
```

| Service | URL / Port |
|---------|------------|
| FastAPI | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Mosquitto MQTT | localhost:1883 |
| Grafana | http://localhost:3000 (admin / admin) |

### 4. Créer un équipement

Avec seuils par défaut :
```bash
curl -X POST http://localhost:8000/equipment \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": "PANEL-001",
    "name": "Panneau principal",
    "location": "Bâtiment A",
    "nominal_current": 100,
    "nominal_voltage": 120
  }'
```

Avec seuils personnalisés (ex: équipement sensible) :
```bash
curl -X POST http://localhost:8000/equipment \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": "TRANSFO-001",
    "name": "Transformateur salle serveur",
    "location": "Sous-sol B",
    "nominal_current": 50,
    "nominal_voltage": 120,
    "alert_current_pct": 60,
    "alert_temp_max": 45,
    "alert_imbalance_pct": 5,
    "alert_battery_min": 12.5,
    "alert_voltage_deviation_pct": 5
  }'
```

### 5. Lancer le simulateur

```bash
pip install paho-mqtt

# Mode normal
python backend/scripts/simulate_sensor.py

# Simuler une surchauffe progressive
python backend/scripts/simulate_sensor.py --scenario overheat

# Simuler un déséquilibre de courant
python backend/scripts/simulate_sensor.py --scenario imbalance

# Simuler une batterie faible
python backend/scripts/simulate_sensor.py --scenario battery

# Options
python backend/scripts/simulate_sensor.py --equipment TRANSFO-001 --interval 2 --count 50
```

### 6. Consulter les données

```bash
# Dernières mesures
curl http://localhost:8000/measurements/PANEL-001

# Alertes (toutes)
curl http://localhost:8000/alerts

# Alertes filtrées
curl "http://localhost:8000/alerts?equipment_id=PANEL-001&severity=critical"

# Score de santé
curl http://localhost:8000/health-score/PANEL-001
```

### 7. Grafana

1. Ouvrir http://localhost:3000 (admin / admin)
2. Le dashboard "Electrical Health Monitoring" est pré-configuré
3. Sélectionner l'équipement dans le menu déroulant "Equipment"

## Lancer les tests

```bash
cd backend
pip install -r requirements.txt pytest
pytest tests/ -v
```

44 tests couvrant les règles d'alerte (seuils par défaut et personnalisés) et le calcul du score de santé.

## Structure du projet

```
backend/
  app/
    main.py              # Point d'entrée FastAPI + démarrage MQTT
    database.py          # Connexion PostgreSQL / SQLAlchemy
    models.py            # 3 tables : Equipment, Measurement, Alert
    schemas.py           # Validation Pydantic v2
    mqtt_client.py       # Subscriber MQTT (thread daemon)
    alert_rules.py       # 6 règles d'alerte + AlertThresholds
    health_score.py      # Score de santé pondéré 0-100
    routes/
      measurements.py    # POST/GET mesures + déduplication alertes
      equipment.py       # POST/GET équipements
      alerts.py          # GET alertes avec filtres
      health.py          # GET score de santé
  scripts/
    simulate_sensor.py   # Simulateur MQTT (4 scénarios)
  tests/
    test_alert_rules.py  # 32 tests (dont seuils custom)
    test_health_score.py # 12 tests
  requirements.txt
  Dockerfile
docker-compose.yml
grafana/
  provisioning/
    datasources/datasource.yml
    dashboards/
      dashboard.yml
      electrical_health.json
mosquitto/
  mosquitto.conf
.env.example
```

## Format de données MQTT

Topic : `sensors/{equipment_id}/measurements`

```json
{
  "equipment_id": "PANEL-001",
  "timestamp": "2026-05-29T18:00:00Z",
  "voltage_a": 120.5,
  "voltage_b": 119.8,
  "voltage_c": 121.2,
  "current_a": 45.3,
  "current_b": 44.1,
  "current_c": 46.7,
  "temperature_1": 35.2,
  "temperature_2": 34.8,
  "temperature_3": 36.1,
  "battery_voltage": 13.2
}
```

## Matériel pour déploiement réel

### Clients cibles
- Immeubles commerciaux (panneaux triphasés 200A+)
- Écoles, hôpitaux, CHSLD
- Usines et manufacturiers
- Data centers
- Immeubles multi-logements (50+ unités)

### Kit capteurs par panneau (~100-130$ CAD)

| Composant | Modèle | Qté | Prix unitaire |
|-----------|--------|-----|---------------|
| Microcontrôleur | ESP32 DevKit V1 | 1 | ~10$ |
| Capteurs courant | YHDC SCT-013-000 (100A) | 3 | ~12$ |
| Capteurs tension | ZMPT101B | 3 | ~5$ |
| Sondes température | DS18B20 étanche | 3 | ~4$ |
| Mesure batterie | INA219 (optionnel) | 1 | ~5$ |
| Résistances de charge | 33 ohms (pour CTs) | 3 | ~1$ le lot |
| Alimentation | 5V USB | 1 | ~8$ |
| Breadboard + fils | Kit prototypage | 1 | ~10$ |

Fournisseurs : Amazon.ca, AliExpress, Digikey.ca, Mouser.ca

### Installation physique
- CTs : autour de chaque conducteur de phase à l'entrée du panneau
- Température 1 : sur la barre bus principale
- Température 2 : sur le disjoncteur principal
- Température 3 : température ambiante dans le panneau
- ESP32 : dans un boîtier ABS à l'intérieur ou à proximité du panneau

## Arrêter les services

```bash
docker compose down
```

Supprimer aussi les données :
```bash
docker compose down -v
```

## Roadmap production

- [ ] Firmware ESP32 (MicroPython/Arduino) pour lire les capteurs réels
- [ ] Authentification JWT sur l'API
- [ ] TLS/HTTPS pour l'API et MQTT
- [ ] Notifications email/SMS (Twilio, SendGrid)
- [ ] Interface web client (remplacer Grafana brut)
- [ ] Multi-tenant (séparation par client/bâtiment)
- [ ] Export rapports PDF mensuels
- [ ] Mise à jour firmware OTA
- [ ] App mobile (notifications push)
- [ ] Déploiement cloud (AWS/Azure)
- [ ] Certifications CSA/UL pour les capteurs
