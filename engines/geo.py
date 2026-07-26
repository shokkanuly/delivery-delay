"""Inter-city road distances for Kazakhstan (km, approximate).

Used by the scheduler to price the travel cost of sending a resource from its
home city to a project site. Approximate road distances are plenty for
optimization -- only the relative ordering drives the solver's choices.
"""
from __future__ import annotations

CITIES = ["Almaty", "Astana", "Shymkent", "Aktobe", "Karagandy", "Atyrau"]

# Symmetric matrix, km. Sources: approximate road distances between city centres.
_DIST = {
    ("Almaty", "Astana"): 1220, ("Almaty", "Shymkent"): 700,
    ("Almaty", "Aktobe"): 2000, ("Almaty", "Karagandy"): 1000,
    ("Almaty", "Atyrau"): 2300,
    ("Astana", "Shymkent"): 1500, ("Astana", "Aktobe"): 1300,
    ("Astana", "Karagandy"): 220, ("Astana", "Atyrau"): 1700,
    ("Shymkent", "Aktobe"): 1600, ("Shymkent", "Karagandy"): 1300,
    ("Shymkent", "Atyrau"): 1800,
    ("Aktobe", "Karagandy"): 1200, ("Aktobe", "Atyrau"): 850,
    ("Karagandy", "Atyrau"): 1600,
}


def distance_km(a: str, b: str) -> int:
    """Road distance between two cities; 0 for the same city."""
    if a == b:
        return 0
    return _DIST.get((a, b)) or _DIST.get((b, a)) or 1500  # 1500 = unknown pair
