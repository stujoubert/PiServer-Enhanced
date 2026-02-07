import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


from collector import sync_users_from_events
from services.users import (
    get_users_without_faces,
    promote_event_snapshots_for_users
)

def run():
    inserted = sync_users_from_events()

    if inserted == 0:
        print("No new users detected.")
        return

    users = get_users_without_faces()

    if not users:
        print(f"{inserted} users added, all already have faces.")
        return

    faces = promote_event_snapshots_for_users(users)
    print(f"{inserted} users added, {faces} faces attached.")

if __name__ == "__main__":
    run()
