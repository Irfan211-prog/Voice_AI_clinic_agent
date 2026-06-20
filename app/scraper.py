import re
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models import Department, Doctor, Slot


SCHEDULE_URL = "https://aiimspatna.edu.in/opd-schedule-general/"
TIMING_URL = "https://aiimspatna.edu.in/opd/"


try:
    IST = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    IST = timezone(timedelta(hours=5, minutes=30))


DAY_MAP = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
}


DAY_RE = r"\bMON\b|\bTUE\b|\bWED\b|\bTHU\b|\bFRI\b|\bSAT\b"


ROW_RE = re.compile(
    r"^(?P<department>.+?)\s+"
    r"(?P<unit>Unit\s+(?:[IVX]+|\d+)\s*[A-Z]?)\s+"
    r"General\s+OPD\s+"
    r"(?P<days>.*?)(?=(?:Dr\.|Prof\.))"
    r"(?P<faculty>(?:Dr\.|Prof\.).*)$",
    re.IGNORECASE,
)


NEXT_ROW_RE = re.compile(
    r"\s+[A-Z][A-Za-z &/().'-]+?\s+"
    r"Unit\s+(?:[IVX]+|\d+)\s*[A-Z]?\s+"
    r"General\s+OPD\s+",
    re.IGNORECASE,
)


def clean_text(value: str) -> str:
    if not value:
        return ""

    value = value.replace("\xa0", " ")
    value = value.replace("&amp;", "&")

    value = re.sub(r"\)(Dr\.|Prof\.)", r") \1", value)

    value = re.sub(
        r"\b(MON|TUE|WED|THU|FRI|SAT)(Dr\.|Prof\.)",
        r"\1 \2",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract_days(text: str):
    text = clean_text(text).upper()
    days = re.findall(DAY_RE, text)
    return list(dict.fromkeys(days))


def split_doctors(faculty_text: str):
    faculty_text = clean_text(faculty_text)

    if not faculty_text:
        return []

    faculty_text = NEXT_ROW_RE.split(faculty_text)[0]

    doctors = []

    for part in faculty_text.split(","):
        name = clean_text(part)

        if not name:
            continue

        if "General OPD" in name:
            continue

        if re.search(r"\bUnit\s+(?:[IVX]+|\d+)\b", name, flags=re.IGNORECASE):
            continue

        if not name.startswith("Dr.") and not name.startswith("Prof."):
            name = "Dr. " + name

        doctors.append(name)

    return list(dict.fromkeys(doctors))


def parse_schedule_line(line: str):
    line = clean_text(line)

    if "General OPD" not in line:
        return None

    if "Dr." not in line and "Prof." not in line:
        return None

    match = ROW_RE.match(line)

    if not match:
        return None

    department = clean_text(match.group("department"))
    unit = clean_text(match.group("unit"))
    days_text = clean_text(match.group("days"))
    faculty_text = clean_text(match.group("faculty"))

    days = extract_days(days_text)
    doctors = split_doctors(faculty_text)

    if not department or not unit or not days or not doctors:
        return None

    return {
        "department": department,
        "unit": unit,
        "days": days,
        "doctors": doctors,
        "source_url": SCHEDULE_URL,
    }


def unique_rows(rows):
    seen = set()
    final_rows = []

    for row in rows:
        key = (
            row["department"],
            row["unit"],
            tuple(row["days"]),
            tuple(row["doctors"]),
        )

        if key not in seen:
            seen.add(key)
            final_rows.append(row)

    return final_rows


def fetch_html_with_requests():
    response = requests.get(
        SCHEDULE_URL,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )

    response.raise_for_status()
    return response.text


def fetch_html_with_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page.goto(SCHEDULE_URL, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_selector("text=Anaesthesiology", timeout=30000)
        except Exception:
            page.wait_for_timeout(10000)

        html = page.content()
        browser.close()

    return html


def fetch_real_aiims_html():
    html = fetch_html_with_requests()

    blocked_words = [
        "Javascript is required",
        "You are being redirected",
        "enable javascript",
    ]

    is_blocked = any(word.lower() in html.lower() for word in blocked_words)

    if is_blocked or "General OPD" not in html:
        print("Normal requests blocked by website. Opening browser with Playwright...")
        html = fetch_html_with_browser()

    return html


def scrape_general_schedule():
    html = fetch_real_aiims_html()

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    rows = []

    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]

    for line in lines:
        row = parse_schedule_line(line)

        if row:
            rows.append(row)

    for tr in soup.find_all("tr"):
        cells = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in tr.find_all(["td", "th"])
        ]

        cells = [cell for cell in cells if cell]

        if not cells:
            continue

        joined = clean_text(" ".join(cells))
        row = parse_schedule_line(joined)

        if row:
            rows.append(row)

    for i in range(len(lines)):
        chunk = clean_text(" ".join(lines[i:i + 6]))
        row = parse_schedule_line(chunk)

        if row:
            rows.append(row)

    rows = unique_rows(rows)

    if not rows:
        Path("debug_aiims_opd_page.html").write_text(html, encoding="utf-8")
        Path("debug_aiims_opd_text.txt").write_text(text, encoding="utf-8")

        raise RuntimeError(
            "Could not parse real AIIMS Patna OPD data. "
            "Debug files created: debug_aiims_opd_page.html and debug_aiims_opd_text.txt"
        )

    print(f"Parsed {len(rows)} real OPD schedule rows from AIIMS Patna website.")

    for row in rows[:5]:
        print(row)

    return rows


def get_opd_window_for_date(slot_date):
    if slot_date.weekday() == 5:
        return time(8, 0), time(11, 30)

    return time(8, 0), time(13, 0)


def get_or_create_department(db: Session, name: str):
    department = db.query(Department).filter(Department.name == name).first()

    if department:
        return department

    department = Department(
        name=name,
        source_url=SCHEDULE_URL,
    )

    db.add(department)
    db.flush()

    return department


def get_or_create_doctor(db: Session, name: str, unit: str, department: Department):
    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.name == name,
            Doctor.unit == unit,
            Doctor.department_id == department.id,
        )
        .first()
    )

    if doctor:
        return doctor

    doctor = Doctor(
        name=name,
        unit=unit,
        department_id=department.id,
        source_url=SCHEDULE_URL,
    )

    db.add(doctor)
    db.flush()

    return doctor


def create_slots_for_doctor(
    db: Session,
    doctor: Doctor,
    department: Department,
    days,
    days_ahead=10,
):
    now = datetime.now(IST).replace(tzinfo=None)
    today = datetime.now(IST).date()

    wanted_weekdays = {DAY_MAP[d] for d in days if d in DAY_MAP}

    if not wanted_weekdays:
        return 0

    created = 0

    for offset in range(1, days_ahead + 1):
        current_date = today + timedelta(days=offset)

        if current_date.weekday() not in wanted_weekdays:
            continue

        start_t, end_t = get_opd_window_for_date(current_date)

        start_dt = datetime.combine(current_date, start_t)
        end_limit = datetime.combine(current_date, end_t)

        while start_dt + timedelta(minutes=30) <= end_limit:
            end_dt = start_dt + timedelta(minutes=30)

            if start_dt > now:
                existing = (
                    db.query(Slot)
                    .filter(
                        Slot.doctor_id == doctor.id,
                        Slot.start_at == start_dt,
                        Slot.end_at == end_dt,
                    )
                    .first()
                )

                if not existing:
                    db.add(
                        Slot(
                            doctor_id=doctor.id,
                            department_id=department.id,
                            start_at=start_dt,
                            end_at=end_dt,
                            appointment_type="General OPD",
                            status="available",
                            source_url=TIMING_URL,
                        )
                    )

                    created += 1

            start_dt = end_dt

    return created


def seed_real_aiims_patna_data(db: Session):
    all_rows = scrape_general_schedule()

    IMPORTANT_DEPARTMENTS = {
        "Cardiology",
        "Dermatology",
        "ENT",
        "Ophthalmology",
        "Orthopaedics",
        "Paediatrics",
        "Obstetrics & Gynaecology",
        "Neurology",
        "Nephrology",
        "Psychiatry",
        "Pulmonary Medicine",
        "Gastroenterology",
        "Urology",
        "General Medicine",
        "General Surgery",
    }

    rows = [
        row for row in all_rows
        if row["department"] in IMPORTANT_DEPARTMENTS
    ]

    print(
        f"Reduced schedule rows from {len(all_rows)} to {len(rows)} important rows.",
        flush=True,
    )

    total_doctors = 0
    total_slots = 0
    start_time = datetime.now()

    print("\n========================================", flush=True)
    print("Starting AIIMS Patna OPD database seed", flush=True)
    print(f"Total OPD schedule rows found: {len(rows)}", flush=True)
    print("========================================\n", flush=True)

    for row_index, row in enumerate(rows, start=1):
        department_name = row["department"]
        unit_name = row["unit"]
        doctors_in_row = row["doctors"]

        print(
            f"\n[{row_index}/{len(rows)}] Processing: {department_name} | {unit_name}",
            flush=True,
        )
        print(
            f"Doctors in this row: {len(doctors_in_row)} | OPD days: {', '.join(row['days'])}",
            flush=True,
        )

        department = get_or_create_department(db, department_name)

        row_doctors_count = 0
        row_slots_count = 0

        for doctor_name in doctors_in_row:
            doctor_name = clean_text(doctor_name)

            if not doctor_name:
                continue

            doctor = get_or_create_doctor(
                db=db,
                name=doctor_name,
                unit=unit_name,
                department=department,
            )

            slots_created = create_slots_for_doctor(
                db=db,
                doctor=doctor,
                department=department,
                days=row["days"],
            )

            total_doctors += 1
            total_slots += slots_created
            row_doctors_count += 1
            row_slots_count += slots_created

            print(
                f"  Stored doctor {total_doctors}: {doctor_name} | New slots: {slots_created} | Total slots: {total_slots}",
                flush=True,
            )

        db.commit()

        elapsed = (datetime.now() - start_time).total_seconds()
        progress = round((row_index / len(rows)) * 100, 2)

        print(
            f"Committed row {row_index}/{len(rows)} | Progress: {progress}% | "
            f"Doctors so far: {total_doctors} | Slots so far: {total_slots} | "
            f"Elapsed: {round(elapsed, 1)} sec",
            flush=True,
        )

    total_time = round((datetime.now() - start_time).total_seconds(), 2)

    print("\n========================================", flush=True)
    print("Seed completed successfully", flush=True)
    print(f"Total doctors processed: {total_doctors}", flush=True)
    print(f"Total slots created: {total_slots}", flush=True)
    print(f"Total time: {total_time} seconds", flush=True)
    print("========================================\n", flush=True)

    return {
        "ok": True,
        "clinic": "AIIMS Patna OPD",
        "source_schedule": SCHEDULE_URL,
        "source_timings": TIMING_URL,
        "parsed_schedule_rows": len(rows),
        "doctors_seen": total_doctors,
        "new_slots_created": total_slots,
        "time_taken_seconds": total_time,
    }