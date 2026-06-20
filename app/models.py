import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False, index=True)
    source_url = Column(Text, nullable=False)

    doctors = relationship("Doctor", back_populates="department")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    unit = Column(String(100), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    source_url = Column(Text, nullable=False)

    department = relationship("Department", back_populates="doctors")
    slots = relationship("Slot", back_populates="doctor")

    __table_args__ = (
        UniqueConstraint("name", "unit", "department_id", name="uq_doctor_unit_dept"),
    )


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)

    start_at = Column(DateTime, nullable=False, index=True)
    end_at = Column(DateTime, nullable=False)

    appointment_type = Column(String(80), default="General OPD")
    status = Column(String(30), default="available", index=True)
    source_url = Column(Text, nullable=False)

    doctor = relationship("Doctor", back_populates="slots")
    department = relationship("Department")

    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "start_at",
            "end_at",
            "appointment_type",
            name="uq_doctor_slot_time",
        ),
        Index("idx_slot_search", "department_id", "status", "start_at"),
    )


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(30), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)

    status = Column(String(30), default="booked", index=True)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient")
    doctor = relationship("Doctor")
    slot = relationship("Slot")


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(120), nullable=True, index=True)
    event_type = Column(String(80), nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)