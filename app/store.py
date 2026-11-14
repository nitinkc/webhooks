"""In-memory state — deliberately dumb.

A real provider keeps subscriptions in a database and deliveries in a
durable queue; a real receiver persists the delivery IDs it has processed.
Here everything is a list or dict that vanishes on restart — all a local
demo needs.
"""

from datetime import datetime, timezone


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- receiver side ---
events: list[dict] = []
seen_delivery_ids: set[str] = set()

# --- provider side ---
subscriptions: dict[str, str] = {}  # subscription id -> callback URL
deliveries: list[dict] = []

# --- demo endpoints ---
flaky_counts: dict[str, int] = {}  # delivery id -> attempts seen so far
