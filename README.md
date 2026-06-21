# Voice AI Clinic Receptionist

A production-style voice AI receptionist for **AIIMS Patna OPD**.

The assistant can handle the appointment lifecycle through voice:

* Search real clinic availability
* Book appointments
* Reschedule appointments
* Cancel appointments
* Prevent double-booking conflicts
* Handle vague symptoms like “heart problem”, “skin rash”, or “joint pain”
* Recover when the requested slot or day is unavailable
* Validate Indian 10-digit phone numbers before booking

---

## Quick Links

* GitHub Repository: <https://github.com/Irfan211-prog/Voice_AI_clinic_agent>
* Loom Demo Video: <https://drive.google.com/file/d/1WCC2eEamkWEIw5UzjXdetZCb7nqMhpd4/view?usp=sharing>
* Live Backend Health:
  https://voice-ai-clinic-agent.onrender.com/health

---


## Assignment Context

This project was built for the **Voice AI Agent engineering assignment**.

The goal is not just to create a chatbot with speech, but a real voice agent connected to backend tools, real clinic data, appointment storage, conflict checking, and a rerunnable eval harness.

Patients should be able to speak naturally and complete appointment tasks such as booking, rescheduling, cancellation, and lookup without human involvement.

---

## Screenshots

### Vapi Assistant

![Vapi Assistant](images/vapi_assistant.png)

### Live Backend

![Render Health](images/render_health.png)

### Evaluation Result

![Eval Result](images/eval_result.png)

## Live Deployment

### Backend Health URL

```txt
https://voice-ai-clinic-agent.onrender.com/health
```

Latest deployed health result:

```json
{
  "ok": true,
  "departments": 15,
  "doctors": 108,
  "available_slots": 3554,
  "booked_appointments": 3
}
```

### Vapi Voice Agent

The voice assistant is configured in Vapi and connected to the deployed FastAPI backend through tool calls.

Tool webhook URL:

```txt
https://voice-ai-clinic-agent.onrender.com/vapi/webhook
```

A Vapi phone number was also configured for independent calling/testing: 

```txt
+1 929 242 0928
```
Note: Depending on the reviewer's location and carrier, international calling charges or ISD balance may be required to place a phone call. The complete functionality can also be verified through the Vapi dashboard, call logs, backend APIs, and evaluation harness.

![Phone number](phone_number.png)

---

## Tech Stack

* **Vapi** for the voice AI agent
* **FastAPI** for backend APIs
* **SQLAlchemy** for database models and queries
* **SQLite** for local testing
* **PostgreSQL / Supabase** for deployed database
* **Render** for backend deployment
* **BeautifulSoup + Playwright** for real AIIMS Patna OPD data extraction
* **Python eval harness** for repeatable backend task evaluation

---

## Why Vapi?

I chose **Vapi** because the assignment required a real voice AI agent, not just a chatbot with a voice layer. Vapi provides speech-to-text, LLM orchestration, text-to-speech, phone/web call testing, tool calling, and call logs in one platform.

This helped me focus on the core engineering work: real clinic data, appointment booking logic, conflict prevention, backend APIs, database storage, and evaluation. Vapi also makes it easy to connect the assistant to custom FastAPI tools, so every booking, rescheduling, cancellation, and lookup goes through the deployed backend instead of hardcoded responses.

---

## Real Clinic Data

The system uses real public OPD data from **AIIMS Patna**.

The scraped/source data includes:

* Departments
* Units
* Doctors/faculty
* OPD days

Appointment slots are generated from the official OPD timing windows:

* Monday to Friday: 08:00 AM to 01:00 PM
* Saturday: 08:00 AM to 11:30 AM
* Sunday: No general OPD

The system stores the scraped clinic data in the database, so the voice agent does not depend on placeholder doctors, fake departments, or hardcoded appointment responses.

---

## Architecture

```txt
Patient Voice
    ↓
Vapi Voice Assistant
    ↓
FastAPI Tool Webhook
    ↓
Backend Tool Logic
    ↓
Supabase PostgreSQL Database
    ↓
Appointment / Slot / Patient Updates
```

The assistant does not directly decide appointment availability. It calls backend tools, and the backend checks the real database before confirming any appointment.

---

## Main Features

### 1. Availability Search

The patient can ask for an appointment by department, doctor, symptom, date, or time window.

Example:

```txt
I want to see a heart doctor tomorrow morning.
```

The system maps “heart” to Cardiology, searches available slots, and returns real doctor/date/time options from the database.

---

### 2. Booking

The assistant collects:

* Preferred department/symptom
* Preferred date/time window
* Patient name
* Valid Indian 10-digit mobile number

Then it books only after confirmation.

The backend validates phone numbers before booking.

Accepted examples:

```txt
9876543210
+91 9876543210
```

Rejected examples:

```txt
12345
54321
1111111111
```

---

### 3. Rescheduling

The patient can reschedule using an appointment ID or phone number.

The backend:

* Finds the active appointment
* Searches new available slots
* Releases the old slot
* Books the new slot
* Updates the appointment record

---

### 4. Cancellation

The patient can cancel using an appointment ID or phone number.

The backend:

* Marks the appointment as cancelled
* Makes the booked slot available again

---

### 5. Conflict Handling

If two patients try to book the same slot, the backend prevents double booking.

Example backend response:

```txt
That slot was just taken. Offer alternatives instead.
```

The agent then offers different available slots instead of confirming an already-booked slot.

---

### 6. Vague Request Handling

The backend supports symptom-to-department mapping:

* heart / chest pain / cardiac → Cardiology
* skin / rash → Dermatology
* eye / eyes → Ophthalmology
* bone / joint pain / ortho → Orthopaedics
* child / kids → Paediatrics
* pregnancy / women → Obstetrics & Gynaecology
* ear / nose / throat → ENT
* kidney → Nephrology
* brain / nerve → Neurology
* mental health / anxiety / depression → Psychiatry
* lungs / breathing → Pulmonary Medicine
* stomach / gastric → Gastroenterology
* urine / urinary → Urology

---

### 7. Unavailable Slot Recovery

If a requested slot or day is not available, the backend does not invent a fake slot.

Example Sunday request result:

```json
{
  "ok": false,
  "message": "No exact slot is available. Offer these nearest alternatives.",
  "resolved_department": "Cardiology",
  "options": [...]
}
```

This allows the agent to gracefully offer real alternatives.

---

## Backend Tools

The Vapi assistant connects to these deployed backend tools:

* `get_clinic_context`
* `search_availability`
* `book_appointment`
* `lookup_appointment`
* `cancel_appointment`
* `reschedule_appointment`

Each tool performs real database operations through FastAPI and Supabase.

---

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

---

## Environment Variables

Create a `.env` file locally.

```env
DATABASE_URL=sqlite:///./clinic.db
VAPI_WEBHOOK_SECRET=change-this-secret
ADMIN_TOKEN=change-admin-token
CLINIC_NAME=AIIMS Patna OPD
```

For deployment, `DATABASE_URL` should point to Supabase PostgreSQL.

Example format:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres
```

Do not commit `.env` to GitHub.

---

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

---

## Run Eval Harness Locally

Start backend first:

```bash
uvicorn app.main:app --reload
```

In another terminal:

```bash
venv\Scripts\activate
python eval/run_eval.py
```

---

## Run Eval Harness Against Deployed Backend

```powershell
$env:BASE_URL="https://voice-ai-clinic-agent.onrender.com"
python eval/run_eval.py
```

The eval checks:

* Real clinic availability search
* Vague symptom resolution
* Booking success
* Double-booking prevention
* Alternative slot recovery
* Rescheduling
* Lookup by phone
* Cancellation
* Backend tool latency

Latest deployed eval result:

```json
{
  "task_success_rate": 1.0,
  "passed": 7,
  "total": 7,
  "latency_ms": {
    "p50": 1290.66,
    "p95": 2018.92,
    "max": 2292.71
  }
}
```

---

## What the Eval Measures

The eval harness measures backend task correctness across important appointment workflows:

1. Whether vague symptoms resolve to the correct department
2. Whether real availability is returned
3. Whether booking succeeds
4. Whether double booking is prevented
5. Whether alternative slots are found
6. Whether rescheduling succeeds
7. Whether lookup by phone works
8. Whether cancellation succeeds
9. Backend tool latency

---

## Eval Limitations

The eval harness does not test every possible department or every possible patient phrase.

It also does not measure full voice quality, speech-to-text accuracy, text-to-speech quality, or emotional naturalness of the conversation. Those are checked manually through Vapi call logs and Loom demo.

---

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

### Vapi Webhook

```http
POST /vapi/webhook
```

---

## Latency Story

The backend is designed to keep tool latency reasonable:

* Clinic data is scraped once and stored in Supabase.
* Scraping is not done during live patient calls.
* Slot search uses database queries.
* Backend functions are deterministic and do not call another LLM.
* Search results are limited to a small number of options.
* Appointment operations are handled directly in the database.

In the deployed eval run, backend tool latency was:

```txt
p50 ≈ 1.29s
p95 ≈ 2.02s
max ≈ 2.29s
```

These numbers include Render network latency and Supabase database latency.

Full end-to-end voice latency also depends on Vapi, speech-to-text, LLM response time, and text-to-speech generation.

---

## Known Limitations

* This project does not integrate with the official AIIMS Patna appointment booking system.
* The project uses public OPD schedule information and generates appointment slots from OPD days/timing windows.
* Public OPD schedule data can change, so the database should be reseeded periodically.
* Emergency handling is advisory only and does not replace real emergency medical care.
* The eval harness tests backend task correctness, not subjective human-like voice quality.
* Phone calling through Vapi may require active Vapi credits and, for international calling, caller-side ISD support.
* Some doctor entries may appear duplicated if the public OPD source lists doctors in multiple units or if old seeded data was not cleaned before reseeding.

---

## Demo Flow

The Loom demo includes:

* Live deployed backend on Render
* Vapi voice assistant
* Real appointment search
* Appointment booking
* Supabase database storage
* Double-booking prevention
* Rescheduling
* Cancellation
* Eval harness execution
* Task success rate of 1.0

---

## Final Result

The project demonstrates an end-to-end voice AI clinic receptionist using real clinic data, deployed backend logic, database-backed appointment handling, conflict prevention, and a rerunnable eval harness.

## Evaluation Summary

Latest deployed evaluation result:

```json
{
  "task_success_rate": 1.0,
  "passed": 7,
  "total": 7
}
```

This confirms successful execution of:

* Availability search
* Symptom-to-department mapping
* Appointment booking
* Double-booking prevention
* Alternative slot recovery
* Rescheduling
* Appointment lookup
* Cancellation
