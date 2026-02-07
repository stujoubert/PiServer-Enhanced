from datetime import timedelta, datetime, time
from services.schedule_templates import get_user_schedule

# -----------------------------
# Configuration (safe defaults)
# -----------------------------
DUPLICATE_WINDOW = 60        # seconds
MIN_SHIFT_SECONDS = 60 * 10  # 10 minutes

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _naive(dt: datetime) -> datetime:
    """Ensure datetime is timezone-naive (local wall-clock)."""
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def _to_time(v):
    """
    Accepts datetime.time or 'HH:MM' / 'HH:MM:SS' strings.
    Returns datetime.time or None.
    """
    if not v:
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, str):
        try:
            if len(v.split(":")) == 2:
                return datetime.strptime(v, "%H:%M").time()
            return datetime.strptime(v, "%H:%M:%S").time()
        except Exception:
            return None
    return None


def deduplicate_events(events):
    cleaned = []
    last_time = None

    for e in events:
        t = _naive(e["event_time"])
        e["event_time"] = t

        if last_time and (t - last_time).total_seconds() <= DUPLICATE_WINDOW:
            continue

        cleaned.append(e)
        last_time = t

    return cleaned


# --------------------------------------------------
# Core daily attendance logic
# --------------------------------------------------
def calculate_daily_attendance(events):
    """
    Attendance calculation that NEVER hides users.
    Visibility is driven ONLY by events.
    """
    if not events:
        return {
            "in": None,
            "out": None,
            "worked_seconds": 0,
            "punch_count": 0,
            "flags": ["no_events"],
        }

    # Normalize & sort
    events = sorted(events, key=lambda e: e["event_time"])
    events = deduplicate_events(events)

    first_in = events[0]["event_time"]
    last_out = events[-1]["event_time"]

    punch_count = len(events)
    flags = []

    # Overnight safety
    if last_out < first_in:
        last_out = last_out + timedelta(days=1)

    worked_seconds = max(int((last_out - first_in).total_seconds()), 0)

    # Flags only — NEVER visibility logic
    if punch_count == 1:
        flags.append("single_punch")

    if worked_seconds < MIN_SHIFT_SECONDS:
        flags.append("short_day")

    return {
        "in": first_in,
        "out": last_out,
        "worked_seconds": worked_seconds,
        "punch_count": punch_count,
        "flags": flags,
    }

