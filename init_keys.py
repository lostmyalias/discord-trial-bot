# init_keys.py
from replit import db

# your test keys (later swap for real SkyTrial-******)
KEYS = ["TestKey1", "TestKey2", "TestKey3"]

for key in KEYS:
    entry = db.get(f"key:{key}")
    if not entry:
        db[f"key:{key}"] = {"dispensed": False, "user_id": None}
        print(f" seeded {key}")
    else:
        print(f" already have {key}")
print("✅ Key pool initialized.")

