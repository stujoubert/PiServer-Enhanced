from collector import sync_users_from_events
from users import get_users_without_faces
from users import promote_event_snapshots_for_users

from services.users import (get_users_missing_faces, promote_event_snapshot_for_users,
)

missing = get_users_missing_faces()
count  = promote_event_snapshots_for_users(missing)

print(f"Faces promoted: {count}")

def daily_user_sync():
    """
    1) Import new users from events
    2) Attach faces only for newly created users
    """

    inserted = sync_users_from_events()

    if inserted == 0:
        return {
            "users_added": 0,
            "faces_added": 0,
            "status": "no-op"
        }

    # Get users without face after insertion
    users = get_users_without_faces()

    if not users:
        return {
            "users_added": inserted,
            "faces_added": 0,
            "status": "users-added-no-faces-needed"
        }

    faces = promote_event_snapshots_for_users(users)

    return {
        "users_added": inserted,
        "faces_added": faces,
        "status": "completed"
    }
