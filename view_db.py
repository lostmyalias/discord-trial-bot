# view_db.py
from replit import db
import json

def pretty(val):
    try:
        return json.dumps(val, indent=2)
    except:
        return str(val)

# ── Section: Linked Users ──
print("👤 Linked Users:\n")
user_count = 0
for key in db.keys():
    if key.startswith("user:"):
        print(f"{key} → {pretty(db[key])}\n")
        user_count += 1
print(f"🧾 Total linked users: {user_count}\n")
print("─" * 40 + "\n")

# ── Section: Trial Keys ──
print("🔑 Trial Keys:\n")
key_count = 0
for key in db.keys():
    if key.startswith("key:"):
        print(f"{key} → {pretty(db[key])}\n")
        key_count += 1
print(f"📦 Total keys in pool: {key_count}\n")
