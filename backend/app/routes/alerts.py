"""Routes pour consulter les alertes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert
from ..schemas import AlertRead

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertRead])
def get_alerts(
    equipment_id: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Recuperer les alertes, avec filtres optionnels."""
    query = db.query(Alert)
    if equipment_id:
        query = query.filter(Alert.equipment_id == equipment_id)
    if severity:
        query = query.filter(Alert.severity == severity)
    return query.order_by(desc(Alert.created_at)).limit(limit).all()
