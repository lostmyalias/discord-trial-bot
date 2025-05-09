from replit import db
for key in list(db.keys()):
    del db[key]
print("✅ DB wiped.")

