#!/usr/bin/env python3
import os
from datetime import datetime, timedelta

from db import get_conn
from collector import fetch_from_device, store_events

LOOKBACK_MINUTES = 60  # safe overlap

def main():
    conn = get_conn()
    cur = conn.cursor()

    devices = cur.execute("""
        SELECT id, ip, username, password
        FROM devices
        WHERE active = 1
    """).fetchall()

    conn.close()

    now = datetime.now()
    start = (now - timedelta(minutes=LOOKBACK_MINUTES)).strftime("%Y-%m-%dT%H:%M:%S-06:00")
    end = now.strftime("%Y-%m-%dT%H:%M:%S-06:00")

    for d in devices:
        try:
            print(f"[AUTO FETCH] device {d['id']} {d['ip']}")

            events = fetch_from_device(
                d["ip"],
                d["username"],
                d["password"],
                start,
                end
            )

            if events:
                stored = store_events(d["id"], events)
                print(f"[AUTO FETCH] stored {stored} events")

        except Exception as e:
            print(f"[AUTO FETCH] ERROR device {d['id']}: {e}")

if __name__ == "__main__":
    main()
