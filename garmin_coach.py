#!/usr/bin/env python3
"""Portable Garmin Connect Personal API snapshot fetcher (schema 1.0)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Personal API key (GCDC_…) comes from GARMIN_PERSONAL_API_KEY or --api-key.
# It is not a bearer token; the client exchanges it for a 24h JWT.
SCHEMA_VERSION = "1.0"
CHUNK = 28
ACT_WINDOW = 30


def eprint(*a: Any) -> None:
    print(*a, file=sys.stderr)


def num(v: Any) -> float | int | None:
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def dig(o: Any, *path: str, default: Any = None) -> Any:
    cur = o
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def call_ok(fn, *a, **kw) -> tuple[Any, str | None]:
    try:
        return fn(*a, **kw), None
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status_code", None)
        detail = f"HTTP {status}" if status else type(exc).__name__
        return None, detail


def chunks(start: date, end: date, size: int = CHUNK) -> list[tuple[date, date]]:
    out, cur = [], start
    while cur <= end:
        ce = min(cur + timedelta(days=size - 1), end)
        out.append((cur, ce))
        cur = ce + timedelta(days=1)
    return out


def by_date(rows: list[dict], *keys: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for k in keys:
            v = row.get(k)
            if isinstance(v, str) and v:
                out[v[:10]] = row
                break
    return out


def mean(vals: list) -> float | None:
    return round(sum(float(v) for v in vals) / len(vals), 2) if vals else None


def hr_zones(a: dict) -> dict[str, float] | None:
    out = {}
    for i in range(1, 6):
        secs = num(a.get(f"hrTimeInZone_{i}"))
        if secs is not None:
            out[f"z{i}"] = round(float(secs) / 60.0, 1)
    return out or None


def norm_activity(a: dict) -> dict:
    dur = num(a.get("duration") or a.get("elapsedDuration") or a.get("movingDuration"))
    dist = num(a.get("distance"))
    t = dig(a, "activityType", "typeKey") or a.get("activityType")
    if isinstance(t, dict):
        t = t.get("typeKey")
    return {
        "id": a.get("activityId") or a.get("id"),
        "name": a.get("activityName") or a.get("name"),
        "type": t,
        "start_local": a.get("startTimeLocal"),
        "duration_s": dur,
        "distance_m": dist,
        "distance_km": round(float(dist) / 1000.0, 3) if dist else None,
        "avg_hr_bpm": num(a.get("averageHR")),
        "max_hr_bpm": num(a.get("maxHR")),
        "avg_pace_min_per_km": (
            round((float(dur) / 60.0) / (float(dist) / 1000.0), 2) if dur and dist and dist > 0 else None
        ),
        "training_load": num(a.get("activityTrainingLoad") or a.get("trainingLoad")),
        "aerobic_te": num(a.get("aerobicTrainingEffect")),
        "anaerobic_te": num(a.get("anaerobicTrainingEffect")),
        "hr_zone_min": hr_zones(a),
        "calories": num(a.get("calories")),
        "elevation_gain_m": num(a.get("elevationGain")),
    }


def sleep_fields(row: dict) -> dict:
    scores = row.get("sleepScores") if isinstance(row.get("sleepScores"), dict) else {}
    overall = scores.get("overall") if isinstance(scores.get("overall"), dict) else {}
    return {
        "sleep_score": num(overall.get("value") or row.get("sleepScore")),
        "sleep_qualifier": overall.get("qualifierKey"),
        "sleep_duration_s": num(row.get("sleepTimeSeconds")),
        "sleep_deep_s": num(row.get("deepSleepSeconds")),
        "sleep_light_s": num(row.get("lightSleepSeconds")),
        "sleep_rem_s": num(row.get("remSleepSeconds")),
        "sleep_awake_s": num(row.get("awakeSleepSeconds")),
    }


def hrv_fields(row: dict) -> dict:
    s = row.get("hrvSummary") if isinstance(row.get("hrvSummary"), dict) else row
    b = s.get("baseline") if isinstance(s.get("baseline"), dict) else {}
    return {
        "hrv_last_night_ms": num(s.get("lastNightAvg")),
        "hrv_weekly_avg_ms": num(s.get("weeklyAvg")),
        "hrv_status": s.get("status"),
        "hrv_baseline_low_ms": num(b.get("balancedLow")),
        "hrv_baseline_high_ms": num(b.get("balancedUpper")),
    }


def daily_fields(row: dict) -> dict:
    hr = row.get("heartRate") if isinstance(row.get("heartRate"), dict) else {}
    stress = row.get("stress") if isinstance(row.get("stress"), dict) else {}
    bb = row.get("bodyBattery") if isinstance(row.get("bodyBattery"), dict) else {}
    mov = row.get("movement") if isinstance(row.get("movement"), dict) else {}
    steps = mov.get("steps") if isinstance(mov.get("steps"), dict) else {}
    inten = row.get("intensityMinutes") if isinstance(row.get("intensityMinutes"), dict) else {}
    cals = row.get("calories") if isinstance(row.get("calories"), dict) else {}
    stress_avg = num(stress.get("avgLevel"))
    if stress_avg is not None and stress_avg < 0:
        stress_avg = None
    return {
        "steps": num(steps.get("value") or steps.get("totalSteps")),
        "calories_total": num(cals.get("burnedTotal")),
        "calories_active": num(cals.get("burnedActive")),
        "resting_hr_bpm": num(hr.get("restingValue")),
        "stress_avg": stress_avg,
        "body_battery_high": num(bb.get("maxValue")),
        "body_battery_low": num(bb.get("minValue")),
        "body_battery_charged": num(bb.get("chargedValue")),
        "body_battery_drained": num(bb.get("drainedValue")),
        "intensity_moderate_min": num(inten.get("moderate")),
        "intensity_vigorous_min": num(inten.get("vigorous")),
    }


def hrv_vs_baseline(row: dict) -> str:
    v, lo, hi = row.get("hrv_last_night_ms"), row.get("hrv_baseline_low_ms"), row.get("hrv_baseline_high_ms")
    if v is None or lo is None or hi is None:
        return "unknown"
    if v < lo:
        return "below"
    if v > hi:
        return "above"
    return "in_range"


def qualitative(row: dict | None) -> str:
    if not row:
        return "unknown"
    score = checks = 0
    if row.get("sleep_score") is not None:
        checks += 1
        score += 2 if row["sleep_score"] >= 80 else 1 if row["sleep_score"] >= 65 else 0
    vs = hrv_vs_baseline(row)
    if vs != "unknown":
        checks += 1
        score += 2 if vs in ("in_range", "above") else 0
    if row.get("body_battery_high") is not None:
        checks += 1
        score += 2 if row["body_battery_high"] >= 75 else 1 if row["body_battery_high"] >= 50 else 0
    if row.get("stress_avg") is not None:
        checks += 1
        score += 2 if row["stress_avg"] <= 25 else 1 if row["stress_avg"] <= 40 else 0
    if not checks:
        return "unknown"
    avg = score / (checks * 2)
    return "strong" if avg >= 0.75 else "adequate" if avg >= 0.45 else "poor"


def search_activities(client, start: date, end: date, limit: int) -> list[dict]:
    def window(ws: date, we: date) -> list[dict]:
        try:
            raw = client.search_activities(
                start=0, limit=min(50, limit), start_date=ws.isoformat(), end_date=we.isoformat()
            )
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "status_code", None) in (500, 502, 503) and ws < we:
                mid = ws + (we - ws) // 2
                return window(ws, mid) + window(mid + timedelta(days=1), we)
            raise
        if not raw:
            return []
        if isinstance(raw, dict):
            raw = raw.get("activities") or raw.get("activityList") or []
        return [a for a in raw if isinstance(a, dict)]

    seen, out = set(), []
    for ws, we in chunks(start, end, ACT_WINDOW):
        for a in window(ws, we):
            aid = a.get("activityId") or a.get("id")
            if aid in seen:
                continue
            seen.add(aid)
            out.append(a)
            if len(out) >= limit:
                return out
    return out


def build(client, start: date, end: date, max_act: int) -> dict:
    notes = [
        "Training Readiness / Training Status are not in Personal API; "
        "aggregates.recovery.qualitative is a local heuristic."
    ]
    avail: dict[str, dict] = {}
    daily_map = {
        (start + timedelta(days=i)).isoformat(): {"date": (start + timedelta(days=i)).isoformat()}
        for i in range((end - start).days + 1)
    }

    profile, err = call_ok(client.get_user_profile_settings)
    avail["profile"] = {"status": "ok"} if profile is not None else {"status": "error" if err else "empty", **({"detail": err} if err else {})}
    zones, zerr = call_ok(client.get_heart_rate_zones)
    avail["hr_zones"] = {"status": "ok"} if zones is not None else {"status": "error" if zerr else "empty", **({"detail": zerr} if zerr else {})}

    summaries, sum_err = [], None
    for a, b in chunks(start, end):
        part, err = call_ok(client.get_daily_summaries, a.isoformat(), b.isoformat())
        sum_err = err or sum_err
        if isinstance(part, list):
            summaries.extend(part)
        elif isinstance(part, dict):
            nested = part.get("data") or part.get("dailySummaries") or part.get("summaries")
            summaries.extend(nested if isinstance(nested, list) else [part])
    avail["daily_summaries"] = {"status": "ok"} if summaries else {"status": "error" if sum_err else "empty", **({"detail": sum_err} if sum_err else {})}
    for day, row in by_date(summaries, "calendarDate", "date").items():
        daily_map.setdefault(day, {"date": day}).update(daily_fields(row))

    sleep_rows, sleep_err = [], None
    for a, b in chunks(start, end):
        part, err = call_ok(client.get_daily_sleep_summaries, a.isoformat(), b.isoformat())
        sleep_err = err or sleep_err
        if isinstance(part, list):
            sleep_rows.extend(part)
        elif isinstance(part, dict):
            sleep_rows.extend(part.get("dailySleepSummaries") or part.get("sleepSummaries") or [part])
    known = set(by_date(sleep_rows, "calendarDate", "sleepDate", "date"))
    cur = start
    while cur <= end:
        day = cur.isoformat()
        if day not in known:
            part, err = call_ok(client.get_daily_sleep, day)
            sleep_err = sleep_err or err
            if isinstance(part, dict) and (part.get("sleepTimeSeconds") is not None or part.get("sleepScores")):
                sleep_rows.append({**part, "calendarDate": part.get("calendarDate") or day})
        cur += timedelta(days=1)
    usable_sleep = [r for r in sleep_rows if isinstance(r, dict) and (r.get("sleepTimeSeconds") is not None or r.get("sleepScores"))]
    avail["sleep"] = {"status": "ok"} if usable_sleep else {"status": "error" if sleep_err else "empty", **({"detail": sleep_err} if sleep_err else {})}
    if not usable_sleep:
        notes.append("No scored sleep nights in range (often empty until daily watch wear).")
    for day, row in by_date(usable_sleep, "calendarDate", "sleepDate", "date").items():
        daily_map.setdefault(day, {"date": day}).update(sleep_fields(row))

    hrv_rows, hrv_err = [], None
    for a, b in chunks(start, end):
        part, err = call_ok(client.get_daily_hrv_summaries, a.isoformat(), b.isoformat())
        hrv_err = err or hrv_err
        if isinstance(part, list):
            hrv_rows.extend(part)
        elif isinstance(part, dict):
            nested = part.get("hrvSummaries") or part.get("dailyHrvSummaries")
            hrv_rows.extend(nested if isinstance(nested, list) else [part])
    usable_hrv = []
    for row in hrv_rows:
        if not isinstance(row, dict):
            continue
        f = hrv_fields(row)
        if f.get("hrv_last_night_ms") is None and f.get("hrv_weekly_avg_ms") is None:
            continue
        usable_hrv.append(row)
    avail["hrv"] = {"status": "ok"} if usable_hrv else {"status": "error" if hrv_err else "empty", **({"detail": hrv_err} if hrv_err else {})}
    if not usable_hrv:
        notes.append("No HRV averages in range (needs overnight HRV-capable wear).")
    for day, row in by_date(usable_hrv, "calendarDate", "date").items():
        if "calendarDate" not in row and isinstance(row.get("hrvSummary"), dict):
            nd = row["hrvSummary"].get("calendarDate")
            if nd:
                day = str(nd)[:10]
        daily_map.setdefault(day, {"date": day}).update(hrv_fields(row))

    bb_any, bb_err = False, None
    for a, b in chunks(start, end):
        part, err = call_ok(client.get_daily_body_battery, a.isoformat(), b.isoformat())
        bb_err = err or bb_err
        rows = part if isinstance(part, list) else ([part] if part else [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            day = row.get("calendarDate") or row.get("date")
            if not isinstance(day, str):
                continue
            bb_any = True
            day = day[:10]
            t = daily_map.setdefault(day, {"date": day})
            vals = []
            for item in row.get("bodyBatteryValuesArray") or []:
                if isinstance(item, list) and len(item) >= 2 and item[1] is not None:
                    vals.append(item[1])
            if vals:
                t.setdefault("body_battery_high", max(vals))
                t.setdefault("body_battery_low", min(vals))
            if t.get("body_battery_charged") is None:
                t["body_battery_charged"] = num(row.get("charged") or row.get("chargedValue"))
            if t.get("body_battery_drained") is None:
                t["body_battery_drained"] = num(row.get("drained") or row.get("drainedValue"))
    avail["body_battery"] = {"status": "ok"} if bb_any else {"status": "error" if bb_err else "empty", **({"detail": bb_err} if bb_err else {})}

    vo2_rows, vo2_err = [], None
    for a, b in chunks(start, end):
        part, err = call_ok(
            client.get, f"/metrics-service/metrics/maxmet/daily/{a.isoformat()}/{b.isoformat()}"
        )
        vo2_err = err or vo2_err
        if isinstance(part, list):
            vo2_rows.extend(part)
        elif isinstance(part, dict):
            vo2_rows.append(part)
    vo2_ok = False
    for row in vo2_rows:
        if not isinstance(row, dict):
            continue
        blobs = [row.get(k) for k in ("generic", "cycling", "running") if isinstance(row.get(k), dict)]
        if not blobs and "vo2MaxValue" in row:
            blobs = [row]
        for blob in blobs:
            day = blob.get("calendarDate") or blob.get("date")
            vo2 = num(blob.get("vo2MaxValue") or blob.get("vo2MaxPreciseValue"))
            if isinstance(day, str) and vo2 is not None:
                vo2_ok = True
                slot = daily_map.setdefault(day[:10], {"date": day[:10]})
                prev = slot.get("vo2_max")
                if prev is None or float(vo2) > float(prev):
                    slot["vo2_max"] = vo2
    avail["vo2_max"] = {"status": "ok"} if vo2_ok else {"status": "error" if vo2_err else "empty", **({"detail": vo2_err} if vo2_err else {})}

    fitness, ferr = call_ok(client.get_fitness_age, end.isoformat())
    avail["fitness_age"] = {"status": "ok"} if fitness is not None else {"status": "error" if ferr else "empty", **({"detail": ferr} if ferr else {})}

    try:
        acts_raw = search_activities(client, start, end, max_act)
        avail["activities"] = {"status": "ok" if acts_raw else "empty"}
    except Exception as exc:  # noqa: BLE001
        acts_raw, avail["activities"] = [], {"status": "error", "detail": str(getattr(exc, "status_code", type(exc).__name__))}

    activities = [norm_activity(a) for a in acts_raw]
    daily = [daily_map[d] for d in sorted(daily_map)]
    by_type: dict[str, int] = {}
    for a in activities:
        k = str(a.get("type") or "unknown")
        by_type[k] = by_type.get(k, 0) + 1
    latest = None
    for row in reversed(daily):
        if any(row.get(k) is not None for k in ("sleep_score", "hrv_last_night_ms", "body_battery_high", "stress_avg")):
            latest = row
            break

    display = None
    if isinstance(profile, dict):
        display = profile.get("displayName") or profile.get("userDisplayName") or dig(profile, "userData", "displayName")

    return {
        "schema_version": SCHEMA_VERSION,
        "source": "garmin-connect-personal-api",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "availability": avail,
        "profile": {"display_name": display, "hr_zones": zones},
        "daily": daily,
        "activities": activities,
        "aggregates": {
            "activity_count": len(activities),
            "total_duration_s": round(sum(float(a["duration_s"]) for a in activities if a.get("duration_s") is not None), 1),
            "total_distance_km": round(sum(float(a["distance_km"]) for a in activities if a.get("distance_km") is not None), 3),
            "total_training_load": round(sum(float(a["training_load"]) for a in activities if a.get("training_load") is not None), 1),
            "activities_by_type": by_type,
            "avg_sleep_score": mean([d["sleep_score"] for d in daily if d.get("sleep_score") is not None]),
            "avg_hrv_last_night_ms": mean([d["hrv_last_night_ms"] for d in daily if d.get("hrv_last_night_ms") is not None]),
            "avg_resting_hr_bpm": mean([d["resting_hr_bpm"] for d in daily if d.get("resting_hr_bpm") is not None]),
            "avg_stress": mean([d["stress_avg"] for d in daily if d.get("stress_avg") is not None]),
            "fitness_age": fitness,
            "recovery": {
                "latest_date": latest.get("date") if latest else None,
                "sleep_score": latest.get("sleep_score") if latest else None,
                "hrv_last_night_ms": latest.get("hrv_last_night_ms") if latest else None,
                "hrv_vs_baseline": hrv_vs_baseline(latest or {}),
                "body_battery_high": latest.get("body_battery_high") if latest else None,
                "stress_avg": latest.get("stress_avg") if latest else None,
                "qualitative": qualitative(latest),
            },
        },
        "notes": notes,
    }


def configure_ssl() -> None:
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception as exc:  # noqa: BLE001
        eprint(f"Warning: OS trust store unavailable ({exc})")


def resolve_api_key(explicit: str | None = None) -> str:
    key = (explicit or os.environ.get("GARMIN_PERSONAL_API_KEY") or "").strip()
    if not key:
        raise SystemExit(
            "Missing Garmin Personal API key. Set GARMIN_PERSONAL_API_KEY or pass --api-key."
        )
    return key


def resolve_range(
    *,
    days: int = 14,
    start: str | None = None,
    end: str | None = None,
) -> tuple[date, date]:
    today = date.today()
    end_d = date.fromisoformat(end) if end else today
    start_d = date.fromisoformat(start) if start else end_d - timedelta(days=max(days, 1) - 1)
    if start_d > end_d:
        raise ValueError("start must be <= end")
    if (end_d - start_d).days > 91:
        raise ValueError("max range is 92 days")
    return start_d, end_d


def fetch_coach_snapshot(
    *,
    days: int = 14,
    start: str | None = None,
    end: str | None = None,
    max_activities: int = 200,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch a schema 1.0 coaching snapshot for agents."""
    start_d, end_d = resolve_range(days=days, start=start, end=end)
    key = resolve_api_key(api_key)
    configure_ssl()
    try:
        from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator
    except ImportError as exc:
        raise RuntimeError(
            "Install deps: pip install garmin-connect-personal-api-python truststore"
        ) from exc

    cache = Path.home() / ".cache" / "garmin-personal-api-bearer-token.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    with PersonalApiAuthenticator(bearer_token_cache_file=cache) as auth:
        token = auth.obtain_token(key)
    with GarminPersonalApiClient(token.access_token) as client:
        snap = build(client, start_d, end_d, max_activities)

    snap["purpose"] = "agent-coaching"
    snap["coach_hints"] = {
        "prefer": ["daily", "activities", "aggregates"],
        "recovery_field": "aggregates.recovery",
        "training_readiness": (
            "Official Garmin Training Readiness is not in Personal API; "
            "use aggregates.recovery.qualitative as a local heuristic only."
        ),
        "empty_sleep_hrv": (
            "Empty sleep/HRV is normal without daily wear of an HRV-capable watch."
        ),
    }
    return snap


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--max-activities", type=int, default=200)
    p.add_argument("--api-key", help="Garmin Personal API key (prefer env var)")
    args = p.parse_args()

    try:
        eprint(f"Fetching Garmin coaching snapshot …")
        snap = fetch_coach_snapshot(
            days=args.days,
            start=args.start,
            end=args.end,
            max_activities=args.max_activities,
            api_key=args.api_key,
        )
    except Exception as exc:  # noqa: BLE001
        eprint(exc)
        return 1

    text = json.dumps(snap, indent=2, default=str)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        eprint(f"Wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
