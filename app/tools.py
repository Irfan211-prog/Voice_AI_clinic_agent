import json
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any, Dict

from dateutil import parser as date_parser
from rapidfuzz import process, fuzz
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Department, Doctor, Slot, Patient, Appointment


try:
    IST = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    IST = timezone(timedelta(hours=5, minutes=30))


DEPARTMENT_ALIASES = {
    "heart": "Cardiology",
    "chest pain": "Cardiology",
    "cardiac": "Cardiology",

    "skin": "Dermatology",
    "rash": "Dermatology",

    "eye": "Ophthalmology",
    "eyes": "Ophthalmology",

    "bone": "Orthopaedics",
    "bones": "Orthopaedics",
    "joint pain": "Orthopaedics",
    "ortho": "Orthopaedics",
    "orthopedic": "Orthopaedics",
    "orthopedics": "Orthopaedics",

    "child": "Paediatrics",
    "children": "Paediatrics",
    "kid": "Paediatrics",
    "kids": "Paediatrics",
    "pediatric": "Paediatrics",
    "pediatrics": "Paediatrics",

    "pregnancy": "Obstetrics & Gynaecology",
    "women": "Obstetrics & Gynaecology",
    "gynecology": "Obstetrics & Gynaecology",
    "gynaecology": "Obstetrics & Gynaecology",

    "ent": "ENT",
    "ear": "ENT",
    "nose": "ENT",
    "throat": "ENT",

    "kidney": "Nephrology",

    "brain": "Neurology",
    "nerve": "Neurology",
    "neuro": "Neurology",

    "mental": "Psychiatry",
    "anxiety": "Psychiatry",
    "depression": "Psychiatry",

    "lungs": "Pulmonary Medicine",
    "breathing": "Pulmonary Medicine",
    "pulmonary": "Pulmonary Medicine",

    "stomach": "Gastroenterology",
    "gastric": "Gastroenterology",

    "urine": "Urology",
    "urinary": "Urology",
}


def now_local_naive():
    return datetime.now(IST).replace(tzinfo=None)


def parse_date(value):
    if not value:
        return None

    text = str(value).strip().lower()
    today = datetime.now(IST).date()

    if text == "today":
        return today

    if text == "tomorrow":
        return today + timedelta(days=1)

    if text.startswith("+"):
        try:
            return today + timedelta(days=int(text[1:]))
        except ValueError:
            return None

    try:
        return date_parser.parse(text, dayfirst=False).date()
    except Exception:
        return None


def slot_to_dict(slot: Slot):
    return {
        "slot_id": slot.id,
        "doctor": slot.doctor.name,
        "unit": slot.doctor.unit,
        "department": slot.department.name,
        "appointment_type": slot.appointment_type,
        "start_at": slot.start_at.strftime("%Y-%m-%d %I:%M %p"),
        "end_at": slot.end_at.strftime("%I:%M %p"),
        "source_url": slot.source_url,
    }


def appointment_to_dict(appt: Appointment):
    return {
        "appointment_id": appt.id,
        "status": appt.status,
        "patient_name": appt.patient.name,
        "phone": appt.patient.phone,
        "doctor": appt.doctor.name,
        "department": appt.slot.department.name,
        "slot_id": appt.slot.id,
        "start_at": appt.slot.start_at.strftime("%Y-%m-%d %I:%M %p"),
        "end_at": appt.slot.end_at.strftime("%I:%M %p"),
    }


def resolve_department(db: Session, raw_name: str):
    if not raw_name:
        return None

    raw = str(raw_name).strip()
    lowered = raw.lower()

    if lowered in DEPARTMENT_ALIASES:
        raw = DEPARTMENT_ALIASES[lowered]

    exact = (
        db.query(Department)
        .filter(func.lower(Department.name) == raw.lower())
        .first()
    )

    if exact:
        return exact

    contains = (
        db.query(Department)
        .filter(func.lower(Department.name).contains(raw.lower()))
        .first()
    )

    if contains:
        return contains

    departments = db.query(Department).all()
    choices = [d.name for d in departments]

    if not choices:
        return None

    match = process.extractOne(raw, choices, scorer=fuzz.WRatio)

    if match and match[1] >= 65:
        return db.query(Department).filter(Department.name == match[0]).first()

    return None


def resolve_doctor(db: Session, raw_name: str):
    if not raw_name:
        return None

    raw = str(raw_name).strip()

    contains = (
        db.query(Doctor)
        .filter(func.lower(Doctor.name).contains(raw.lower()))
        .first()
    )

    if contains:
        return contains

    doctors = db.query(Doctor).all()
    choices = [d.name for d in doctors]

    if not choices:
        return None

    match = process.extractOne(raw, choices, scorer=fuzz.WRatio)

    if match and match[1] >= 70:
        return db.query(Doctor).filter(Doctor.name == match[0]).first()

    return None


def apply_time_window(slots, time_window):
    if not time_window:
        return slots

    window = str(time_window).lower().strip()
    filtered = []

    for slot in slots:
        hour = slot.start_at.hour

        if window == "morning" and 8 <= hour < 12:
            filtered.append(slot)

        elif window == "afternoon" and 12 <= hour < 17:
            filtered.append(slot)

        elif window == "evening" and hour >= 17:
            filtered.append(slot)

        elif window not in ["morning", "afternoon", "evening"]:
            filtered.append(slot)

    return filtered


def get_clinic_context(db: Session, args: Dict[str, Any]):
    departments = db.query(Department).order_by(Department.name).all()
    doctor_count = db.query(Doctor).count()
    slot_count = db.query(Slot).filter(Slot.status == "available").count()
    booked_count = db.query(Appointment).filter(Appointment.status == "booked").count()

    return {
        "ok": True,
        "clinic": "AIIMS Patna OPD",
        "hours": {
            "monday_to_friday": "08:00 AM - 01:00 PM",
            "saturday": "08:00 AM - 11:30 AM",
            "sunday": "No general OPD",
        },
        "departments": [d.name for d in departments],
        "department_count": len(departments),
        "doctor_count": doctor_count,
        "available_slots": slot_count,
        "booked_appointments": booked_count,
    }


def search_availability(db: Session, args: Dict[str, Any]):
    department_name = args.get("department")
    doctor_name = args.get("doctor_name")
    preferred_date = parse_date(args.get("preferred_date"))
    time_window = args.get("time_window")
    appointment_type = args.get("appointment_type") or "General OPD"
    limit = int(args.get("limit") or 5)

    if limit <= 0:
        limit = 5

    query = (
        db.query(Slot)
        .join(Doctor, Slot.doctor_id == Doctor.id)
        .join(Department, Slot.department_id == Department.id)
        .filter(
            Slot.status == "available",
            Slot.start_at > now_local_naive(),
            Slot.appointment_type == appointment_type,
        )
    )

    resolved_department = None
    resolved_doctor = None

    if department_name:
        resolved_department = resolve_department(db, department_name)

        if not resolved_department:
            all_departments = db.query(Department).order_by(Department.name).limit(20).all()

            return {
                "ok": False,
                "message": f"I could not find the department '{department_name}'.",
                "available_departments": [d.name for d in all_departments],
                "options": [],
            }

        query = query.filter(Slot.department_id == resolved_department.id)

    if doctor_name:
        resolved_doctor = resolve_doctor(db, doctor_name)

        if not resolved_doctor:
            return {
                "ok": False,
                "message": f"I could not find doctor '{doctor_name}'.",
                "options": [],
            }

        query = query.filter(Slot.doctor_id == resolved_doctor.id)

    if preferred_date:
        start = datetime.combine(preferred_date, time.min)
        end = start + timedelta(days=1)
        query = query.filter(Slot.start_at >= start, Slot.start_at < end)
    else:
        query = query.filter(Slot.start_at < now_local_naive() + timedelta(days=10))

    slots = query.order_by(Slot.start_at.asc()).limit(100).all()
    slots = apply_time_window(slots, time_window)
    slots = slots[:limit]

    if not slots:
        fallback_query = (
            db.query(Slot)
            .join(Doctor, Slot.doctor_id == Doctor.id)
            .join(Department, Slot.department_id == Department.id)
            .filter(
                Slot.status == "available",
                Slot.start_at > now_local_naive(),
                Slot.appointment_type == appointment_type,
            )
        )

        if resolved_department:
            fallback_query = fallback_query.filter(Slot.department_id == resolved_department.id)

        if resolved_doctor:
            fallback_query = fallback_query.filter(Slot.doctor_id == resolved_doctor.id)

        fallback_slots = fallback_query.order_by(Slot.start_at.asc()).limit(limit).all()

        return {
            "ok": False,
            "message": "No exact slot is available. Offer these nearest alternatives.",
            "resolved_department": resolved_department.name if resolved_department else None,
            "options": [slot_to_dict(s) for s in fallback_slots],
        }

    return {
        "ok": True,
        "message": "Available slots found.",
        "resolved_department": resolved_department.name if resolved_department else None,
        "options": [slot_to_dict(s) for s in slots],
    }


def get_or_create_patient(db: Session, name: str, phone: str):
    patient = db.query(Patient).filter(Patient.phone == phone).first()

    if patient:
        patient.name = name
        db.flush()
        return patient

    patient = Patient(name=name, phone=phone)
    db.add(patient)
    db.flush()

    return patient


def book_appointment(db: Session, args: Dict[str, Any]):
    slot_id = args.get("slot_id")
    patient_name = args.get("patient_name")
    phone = args.get("phone")
    reason = args.get("reason")

    if not slot_id or not patient_name or not phone:
        return {
            "ok": False,
            "message": "Missing required details. Need slot_id, patient_name, and phone.",
        }

    slot = (
        db.query(Slot)
        .filter(Slot.id == int(slot_id))
        .with_for_update()
        .first()
    )

    if not slot:
        return {"ok": False, "message": "Slot not found."}

    if slot.status != "available":
        alternatives = search_availability(
            db,
            {
                "department": slot.department.name,
                "preferred_date": slot.start_at.strftime("%Y-%m-%d"),
                "limit": 3,
            },
        )

        return {
            "ok": False,
            "message": "That slot was just taken. Offer alternatives instead.",
            "alternatives": alternatives.get("options", []),
        }

    patient = get_or_create_patient(db, patient_name, phone)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=slot.doctor_id,
        slot_id=slot.id,
        status="booked",
        reason=reason,
    )

    slot.status = "booked"

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return {
        "ok": True,
        "message": "Appointment booked successfully.",
        "appointment": appointment_to_dict(appointment),
    }


def find_appointment(db: Session, appointment_id=None, phone=None):
    query = db.query(Appointment).filter(Appointment.status == "booked")

    if appointment_id:
        return query.filter(Appointment.id == int(appointment_id)).first()

    if phone:
        return (
            query.join(Patient, Appointment.patient_id == Patient.id)
            .filter(Patient.phone == phone)
            .order_by(Appointment.created_at.desc())
            .first()
        )

    return None


def find_appointment(db: Session, appointment_id=None, phone=None):
    query = db.query(Appointment).filter(Appointment.status == "booked")

    if appointment_id:
        appointment_id = str(appointment_id).strip()
        return query.filter(Appointment.id == appointment_id).first()

    if phone:
        phone = str(phone).strip()

        return (
            query.join(Patient, Appointment.patient_id == Patient.id)
            .filter(Patient.phone == phone)
            .order_by(Appointment.created_at.desc())
            .first()
        )

    return None


def lookup_appointment(db: Session, args: Dict[str, Any]):
    appointment_id = args.get("appointment_id")
    phone = args.get("phone")

    if appointment_id:
        appointment_id = str(appointment_id).strip()

        appt = (
            db.query(Appointment)
            .filter(Appointment.id == appointment_id)
            .first()
        )

        if not appt:
            return {
                "ok": False,
                "message": "No appointment found.",
            }

        return {
            "ok": True,
            "appointment": appointment_to_dict(appt),
        }

    if phone:
        phone = str(phone).strip()

        appointments = (
            db.query(Appointment)
            .join(Patient, Appointment.patient_id == Patient.id)
            .filter(Patient.phone == phone)
            .order_by(Appointment.created_at.desc())
            .limit(5)
            .all()
        )

        return {
            "ok": True,
            "appointments": [appointment_to_dict(a) for a in appointments],
        }

    return {
        "ok": False,
        "message": "Need appointment_id or phone.",
    }


def cancel_appointment(db: Session, args: Dict[str, Any]):
    appointment_id = args.get("appointment_id")
    phone = args.get("phone")

    appt = find_appointment(db, appointment_id=appointment_id, phone=phone)

    if not appt:
        return {
            "ok": False,
            "message": "No active appointment found to cancel.",
        }

    appt.status = "cancelled"
    appt.slot.status = "available"
    appt.updated_at = datetime.utcnow()

    db.commit()

    return {
        "ok": True,
        "message": "Appointment cancelled successfully.",
        "appointment": appointment_to_dict(appt),
    }


def reschedule_appointment(db: Session, args: Dict[str, Any]):
    appointment_id = args.get("appointment_id")
    phone = args.get("phone")
    new_slot_id = args.get("new_slot_id")

    if not new_slot_id:
        return {"ok": False, "message": "Need new_slot_id to reschedule."}

    appt = find_appointment(db, appointment_id=appointment_id, phone=phone)

    if not appt:
        return {
            "ok": False,
            "message": "No active appointment found to reschedule.",
        }

    new_slot = (
        db.query(Slot)
        .filter(Slot.id == int(new_slot_id))
        .with_for_update()
        .first()
    )

    if not new_slot:
        return {"ok": False, "message": "New slot not found."}

    if new_slot.status != "available":
        alternatives = search_availability(
            db,
            {
                "department": appt.slot.department.name,
                "limit": 3,
            },
        )

        return {
            "ok": False,
            "message": "The requested new slot is not available. Offer alternatives.",
            "alternatives": alternatives.get("options", []),
        }

    old_slot = appt.slot
    old_slot.status = "available"

    new_slot.status = "booked"

    appt.slot_id = new_slot.id
    appt.doctor_id = new_slot.doctor_id
    appt.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(appt)

    return {
        "ok": True,
        "message": "Appointment rescheduled successfully.",
        "appointment": appointment_to_dict(appt),
    }


TOOL_MAP = {
    "get_clinic_context": get_clinic_context,
    "clinic_context": get_clinic_context,

    "search_availability": search_availability,
    "search_slots": search_availability,
    "find_slots": search_availability,
    "get_available_slots": search_availability,

    "book_appointment": book_appointment,
    "lookup_appointment": lookup_appointment,
    "cancel_appointment": cancel_appointment,
    "reschedule_appointment": reschedule_appointment,
}


def run_tool(db: Session, tool_name: str, args: Dict[str, Any]):
    if tool_name not in TOOL_MAP:
        return {
            "ok": False,
            "message": f"Unknown tool: {tool_name}",
            "available_tools": list(TOOL_MAP.keys()),
        }

    try:
        return TOOL_MAP[tool_name](db, args or {})
    except Exception as exc:
        db.rollback()
        return {
            "ok": False,
            "message": "Tool execution failed safely.",
            "error": str(exc),
        }


def extract_tool_calls(payload: Dict[str, Any]):
    message = payload.get("message", payload)

    calls = (
        message.get("toolCallList")
        or message.get("toolCalls")
        or payload.get("toolCalls")
        or message.get("tool_calls")
        or []
    )

    return calls


def get_tool_name_and_args(call: Dict[str, Any]):
    function_obj = call.get("function") or {}

    name = (
        call.get("name")
        or function_obj.get("name")
        or call.get("toolName")
    )

    args = (
        call.get("arguments")
        or function_obj.get("arguments")
        or function_obj.get("parameters")
        or {}
    )

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}

    tool_call_id = (
        call.get("id")
        or call.get("toolCallId")
        or call.get("callId")
    )

    return tool_call_id, name, args


def handle_vapi_tool_call(db: Session, payload: Dict[str, Any]):
    calls = extract_tool_calls(payload)
    results = []

    for call in calls:
        tool_call_id, tool_name, args = get_tool_name_and_args(call)

        result = run_tool(db, tool_name, args)

        results.append(
            {
                "toolCallId": tool_call_id,
                "result": json.dumps(result),
            }
        )

    return {"results": results}