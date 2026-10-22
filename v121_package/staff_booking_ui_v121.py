"""Presentation-only availability summary for both staff booking entry points.

The booking service remains authoritative; this module never reserves beds.
"""


def availability_summary(rooms, free, start, end):
    capacity = sum(room.capacity for room in rooms)
    if not (start and end and end > start):
        return {
            "ready": False, "capacity": capacity, "free": None,
            "unavailable": None, "rooms_with_space": None,
            "room_count": len(rooms), "nights": None,
        }
    available = sum(max(0, free.get(room.pk, 0)) for room in rooms)
    return {
        "ready": True,
        "capacity": capacity,
        "free": available,
        "unavailable": max(0, capacity - available),
        "rooms_with_space": sum(1 for room in rooms if free.get(room.pk, 0) > 0),
        "room_count": len(rooms),
        "nights": (end - start).days,
    }
