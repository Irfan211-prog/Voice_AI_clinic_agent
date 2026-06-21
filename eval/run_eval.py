import json
import os
import statistics
import time
from datetime import datetime

import requests


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-admin-token")


def call_tool(name, args):
    start = time.perf_counter()

    try:
        response = requests.post(
            f"{BASE_URL}/tools/{name}",
            json=args,
            timeout=30,
        )

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        try:
            data = response.json()
        except Exception:
            data = {
                "ok": False,
                "message": response.text,
            }

        return data, latency_ms

    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "ok": False,
            "message": str(e),
        }, latency_ms


def ensure_seeded():
    health = requests.get(f"{BASE_URL}/health", timeout=20).json()

    if health.get("doctors", 0) > 0 and health.get("available_slots", 0) > 0:
        return health

    print("Database is empty. Seeding real AIIMS Patna OPD data...")

    response = requests.post(
        f"{BASE_URL}/admin/seed",
        headers={"x-admin-token": ADMIN_TOKEN},
        timeout=120,
    )

    print("Seed result:")
    print(json.dumps(response.json(), indent=2))

    return requests.get(f"{BASE_URL}/health", timeout=20).json()


def add_result(results, latencies, scenario, passed, latency_ms, details):
    results.append(
        {
            "scenario": scenario,
            "passed": bool(passed),
            "latency_ms": latency_ms,
            "details": details,
        }
    )

    latencies.append(latency_ms)


def is_real_slot_conflict(result):
    message = str(result.get("message", "")).lower()

    return (
        result.get("ok") is False
        and result.get("error") != "INVALID_PHONE"
        and (
            "taken" in message
            or "not available" in message
            or "alternative" in message
            or len(result.get("alternatives", [])) > 0
        )
    )


def main():
    print("Checking backend health...")
    health = ensure_seeded()

    print("Health:")
    print(json.dumps(health, indent=2))

    # Creates valid 10 digit Indian mobile numbers.
    # Format: 98 + 6 digit run_id + 10/11 = total 10 digits.
    run_id = str(int(time.time()))[-6:]
    patient_phone = f"98{run_id}10"
    second_phone = f"98{run_id}11"

    results = []
    latencies = []

    search_result, latency = call_tool(
        "search_availability",
        {
            "department": "heart",
            "time_window": "morning",
            "limit": 3,
        },
    )

    first_slot_id = None

    if search_result.get("options"):
        first_slot_id = search_result["options"][0]["slot_id"]

    add_result(
        results,
        latencies,
        "vague_symptom_heart_resolves_to_department",
        search_result.get("ok") is True and first_slot_id is not None,
        latency,
        search_result,
    )

    if not first_slot_id:
        summary = {
            "task_success_rate": 0,
            "message": "No slots found, so booking scenarios could not run.",
            "results": results,
        }

        print(json.dumps(summary, indent=2))

        with open("eval_results.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return

    book_result, latency = call_tool(
        "book_appointment",
        {
            "slot_id": first_slot_id,
            "patient_name": "Eval Patient",
            "phone": patient_phone,
            "reason": "Chest pain consultation",
        },
    )

    appointment_id = None

    if book_result.get("appointment"):
        appointment_id = book_result["appointment"]["appointment_id"]

    add_result(
        results,
        latencies,
        "book_appointment_success",
        book_result.get("ok") is True and appointment_id is not None,
        latency,
        book_result,
    )

    conflict_result, latency = call_tool(
        "book_appointment",
        {
            "slot_id": first_slot_id,
            "patient_name": "Second Eval Patient",
            "phone": second_phone,
            "reason": "Trying same slot",
        },
    )

    add_result(
        results,
        latencies,
        "double_booking_conflict_prevented",
        is_real_slot_conflict(conflict_result),
        latency,
        conflict_result,
    )

    search_new_result, latency = call_tool(
        "search_availability",
        {
            "department": "Cardiology",
            "limit": 5,
        },
    )

    new_slot_id = None

    for option in search_new_result.get("options", []):
        if option["slot_id"] != first_slot_id:
            new_slot_id = option["slot_id"]
            break

    add_result(
        results,
        latencies,
        "alternative_slots_found_for_reschedule",
        new_slot_id is not None,
        latency,
        search_new_result,
    )

    if appointment_id and new_slot_id:
        reschedule_result, latency = call_tool(
            "reschedule_appointment",
            {
                "appointment_id": appointment_id,
                "new_slot_id": new_slot_id,
            },
        )

        add_result(
            results,
            latencies,
            "reschedule_appointment_success",
            reschedule_result.get("ok") is True,
            latency,
            reschedule_result,
        )

    if appointment_id:
        lookup_result, latency = call_tool(
            "lookup_appointment",
            {
                "phone": patient_phone,
            },
        )

        add_result(
            results,
            latencies,
            "lookup_appointment_by_phone",
            lookup_result.get("ok") is True,
            latency,
            lookup_result,
        )

    if appointment_id:
        cancel_result, latency = call_tool(
            "cancel_appointment",
            {
                "appointment_id": appointment_id,
            },
        )

        add_result(
            results,
            latencies,
            "cancel_appointment_success",
            cancel_result.get("ok") is True,
            latency,
            cancel_result,
        )

    passed = sum(1 for item in results if item["passed"])
    total = len(results)

    sorted_latencies = sorted(latencies)

    if len(sorted_latencies) >= 2:
        p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1)
        p95 = sorted_latencies[p95_index]
    elif sorted_latencies:
        p95 = sorted_latencies[0]
    else:
        p95 = None

    summary = {
        "run_at_utc": datetime.utcnow().isoformat(),
        "base_url": BASE_URL,
        "test_phone_numbers_used": {
            "patient_phone": patient_phone,
            "second_phone": second_phone,
        },
        "what_this_eval_measures": [
            "Real clinic data availability search",
            "Vague symptom to department resolution",
            "Successful booking",
            "Double-booking conflict prevention",
            "Rescheduling",
            "Cancellation",
            "Lookup by phone",
            "Backend tool latency",
        ],
        "known_eval_limitations": [
            "This eval tests backend task correctness, not full human voice quality.",
            "It does not test every department.",
            "It does not measure speech-to-text or text-to-speech latency.",
        ],
        "task_success_rate": round(passed / total, 3) if total else 0,
        "passed": passed,
        "total": total,
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else None,
            "p95": p95,
            "max": max(latencies) if latencies else None,
        },
        "results": results,
    }

    with open("eval_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()