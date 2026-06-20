# Voice AI Clinic Receptionist

A production-style voice AI receptionist for AIIMS Patna OPD.

The assistant can handle the appointment lifecycle through voice:

* Search real clinic availability
* Book appointments
* Reschedule appointments
* Cancel appointments
* Prevent double booking conflicts
* Handle vague symptoms like “heart problem” or “skin rash”
* Recover when the requested slot is unavailable

## Assignment Context

This project was built for the Voice AI Agent engineering assignment. The goal is not just to create a chatbot with speech, but a real voice agent connected to backend tools, real clinic data, appointment storage, and a rerunnable eval harness.

## Tech Stack

* Vapi for the voice AI agent
* FastAPI for backend APIs
* SQLAlchemy for database models and queries
* SQLite for local testing
* PostgreSQL/Supabase for deployed database
* Render for backend deployment
* BeautifulSoup + Playwright for real AIIMS Patna OPD data extraction
* Python eval harness for repeatable testing

## Why Vapi?

Vapi was selected because the assignment requires a real voice AI agent that can talk naturally and call backend tools during the conversation. Vapi lets the assistant connect to custom backend endpoints for actions such as searching slots, booking, rescheduling, and cancellation.

## Real Clinic Data

The system uses real public OPD data from AIIMS Patna:

* Departments
* Units
* Doctors/faculty
* OPD days

Appointment slots are generated from the official OPD timing windows:

* Monday to Friday: 08:00 AM to 01:00 PM
* Saturday: 08:00 AM to 11:30 AM
* Sunday: No general OPD

The system stores the scraped clinic data in the database, so the voice agent does not depend on hardcoded doctors or fake departments.

## Main Features

### 1. Booking

The patient can ask for an appointment by department, doctor, symptom, date, or time window.

Example:

> I want to see a heart doctor tomorrow morning.

The agent maps “heart” to Cardiology, searches available slots, offers options, collects patient name and phone number, and books only after confirmation.

### 2. Rescheduling

The patient can reschedule using an appointment ID or phone number. The backend releases the old slot and books the new slot.

### 3. Cancellation

The patient can cancel using an appointment ID or phone number. The backend marks the appointment as cancelled and makes the slot available again.

### 4. Conflict Handling

If two patients try to book the same slot, the backend prevents double booking and returns alternative available slots.

### 5. Vague Request Handling

The backend supports symptom-to-department mapping:

* heart / chest pain → Cardiology
* skin / rash → Dermatology
* eye → Ophthalmology
* bone / joint pain → Orthopaedics
* child / kids → Paediatrics
* pregnancy / women → Obstetrics & Gynaecology
* ear / nose / throat → ENT
* kidney → Nephrology
* brain / nerve → Neurology
* mental health / anxiety → Psychiatry
* lungs / breathing → Pulmonary Medicine
* stomach / gastric → Gastroenterology
* urine / urinary → Urology

## Project Structure

```txt
Voice_AI_Clinic_Agent/
├── app/
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── scraper.py
│   ├── tools.py
│   └── main.py
├── scripts/
│   └── seed_real_data.py
├── eval/
│   └── run_eval.py
├── vapi/
│   ├── assistant_prompt.md
│   └── tools.json
├── requirements.txt
├── render.yaml
└── README.md
```

## Local Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
python scripts/seed_real_data.py
uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000/docs
```

## Run Eval Harness

Start backend first:

```bash
uvicorn app.main:app --reload
```

In another terminal:

```bash
venv\Scripts\activate
python eval/run_eval.py
```

The eval checks:

* Real clinic availability search
* Vague symptom resolution
* Booking success
* Double-booking prevention
* Rescheduling
* Cancellation
* Lookup by phone
* Backend tool latency

Expected result:

```json
"task_success_rate": 1.0
```

## API Endpoints

### Health

```http
GET /health
```

### Seed Real Data

```http
POST /admin/seed
```

### Tool Debug Endpoint

```http
POST /tools/{tool_name}
```

Available tools:

* get_clinic_context
* search_availability
* book_appointment
* lookup_appointment
* cancel_appointment
* reschedule_appointment

### Vapi Webhook

```http
POST /vapi/webhook
```

## Latency Story

The backend is designed to keep tool latency low:

* Clinic data is scraped once and stored in the database.
* Slot search uses indexed fields.
* Backend functions are deterministic and do not call another LLM.
* Search results are limited to a small number of options.
* Appointment operations are handled directly in the database.

In local testing, backend tool calls are usually completed in a few milliseconds to a few hundred milliseconds. Full call latency also depends on the voice provider, speech-to-text, LLM, and text-to-speech settings.

## Known Limitations

* This project does not integrate with the real AIIMS Patna appointment system.
* Public OPD schedule data can change, so the database should be reseeded periodically.
* The generated slots are based on public OPD days and timing windows.
* Emergency handling is advisory only.
* The eval harness tests backend task correctness, not full subjective voice quality.

## Demo Flow

Suggested Loom demo:

1. Patient says: “I want to see a heart doctor tomorrow morning.”
2. Agent searches Cardiology availability.
3. Patient chooses a slot.
4. Agent collects name and phone number.
5. Agent books appointment.
6. Patient asks to reschedule.
7. Agent finds a new slot and reschedules.
8. Patient asks to cancel.
9. Agent cancels appointment.
10. Show eval harness output with task success rate.
