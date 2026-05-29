"""Routes pour la gestion des equipements."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Equipment
from ..schemas import EquipmentCreate, EquipmentRead

router = APIRouter(tags=["equipment"])


@router.post("/equipment", response_model=EquipmentRead)
def create_equipment(data: EquipmentCreate, db: Session = Depends(get_db)):
    """Enregistrer un nouvel equipement."""
    existing = (
        db.query(Equipment)
        .filter(Equipment.equipment_id == data.equipment_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="equipment_id deja existant")

    equipment = Equipment(**data.model_dump())
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


@router.get("/equipment", response_model=list[EquipmentRead])
def list_equipment(db: Session = Depends(get_db)):
    """Lister tous les equipements."""
    return db.query(Equipment).all()
