import json
from typing import Dict, Any

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.models import Department, Doctor, Slot, Appointment, CallLog
from app.scraper import seed_real_aiims_patna_data
from app.tools import handle_vapi_tool_call, run_tool


app = FastAPI(
    title="Voice AI Clinic Receptionist Backend",
    description="FastAPI backend for voice AI appointment receptionist using real AIIMS Patna OPD data.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "ok": True,
        "project": "Voice AI Clinic Receptionist",
        "clinic": settings.clinic_name,
        "docs": "/docs",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "ok": True,
        "departments": db.query(Department).count(),
        "doctors": db.query(Doctor).count(),
        "available_slots": db.query(Slot).filter(Slot.status == "available").count(),
        "booked_appointments": db.query(Appointment).filter(Appointment.status == "booked").count(),
    }


@app.post("/admin/seed")
def seed_data(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("x-admin-token")

    if settings.admin_token != "change-admin-token" and token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    return seed_real_aiims_patna_data(db)


@app.post("/tools/{tool_name}")
def debug_tool_endpoint(
    tool_name: str,
    body: Dict[str, Any],
    db: Session = Depends(get_db),
):
    return run_tool(db, tool_name, body)


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    secret = request.headers.get("x-vapi-secret")

    if settings.vapi_webhook_secret != "change-this-secret" and secret != settings.vapi_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid Vapi secret")

    payload = await request.json()

    db.add(
        CallLog(
            call_id=str(payload.get("call", {}).get("id", "")),
            event_type=str(payload.get("message", {}).get("type", "tool-call")),
            payload=json.dumps(payload),
        )
    )
    db.commit()

    return handle_vapi_tool_call(db, payload)