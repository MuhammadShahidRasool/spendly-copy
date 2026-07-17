"""Seed realistic dummy expenses for a specific user."""
import random
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.getcwd())
from database.db import get_db

# --- Parse args ---
try:
    user_id = int(sys.argv[1])
    count = int(sys.argv[2])
    months = int(sys.argv[3])
except (IndexError, ValueError):
    print("Usage: /seed-expenses <user_id> <count> <months>")
    print("Example: /seed-expenses 1 50 6")
    sys.exit(1)

# --- Category config: (name, min_amount, max_amount, weight) ---
categories = [
    ("Food", 50, 8000, 35),
    ("Transport", 20, 5000, 20),
    ("Bills", 200, 300000, 15),
    ("Shopping", 200, 50000, 12),
    ("Health", 100, 200000, 6),
    ("Entertainment", 100, 15000, 6),
    ("Other", 50, 10000, 6),
]
weights = [c[3] for c in categories]

descriptions = {
    "Food": [
        "Dahi bhalay", "Biryani takeaway", "Nihari breakfast", "Gol gappay",
        "BBQ night at Bundu Khan", "Chai and samosa", "Grocery run at Utility Store",
        "Pizza delivery", "Chicken karahi with friends", "Fruit and vegetable market",
        "Meat shop purchase", "Sunday brunch at Cafe", "Paratha roll",
        "Mangoes seasonal", "Iftar dinner", "Sehri at hotel",
    ],
    "Transport": [
        "Petrol for bike", "Diesel for car", "Uber ride", "Careem ride",
        "Bus fare to office", "Metro card topup", "Rickshaw ride",
        "Taxi to airport", "Oil change and service", "Parking fee",
        "Motorway toll", "CNG refill",
    ],
    "Bills": [
        "Electricity bill (IESCO)", "Water bill (WASA)", "Gas bill (SNGPL)",
        "Internet monthly", "School tuition fee", "Apartment rent",
        "Mobile load/topup", "Cable bill", "Maintenance fee", "Property tax",
        "Generator fuel", "Home WiFi bill",
    ],
    "Health": [
        "Doctor clinic visit", "Blood test at Chugtai Lab", "Dental checkup",
        "Medicine at pharmacy", "Eye checkup and glasses", "Vaccination",
        "MRI scan", "Physiotherapy session", "Health insurance premium",
        "X-ray diagnostic", "Child checkup",
    ],
    "Entertainment": [
        "Movie at Cineplex", "Netflix monthly", "Concert ticket",
        "Eid outfit tailoring", "Birthday dinner out", "Amusement park entry",
        "Board games cafe", "Zoo outing with kids", "PSN subscription",
        "Badminton court fee", "Weekend picnic",
    ],
    "Shopping": [
        "Kurta shalwar fabric", "Cashmere shawl", "Shoes from Servis",
        "Handbag", "Perfume fragrance", "Blanket and bedding",
        "Kitchen appliances", "Mobile accessories", "Books and stationery",
        "Eid shopping for family", "Furniture for guest room",
        "Lawn suit fabric", "Kids school uniforms",
    ],
    "Other": [
        "Flowers for guests", "Gift for wedding", "Home repair tools",
        "Donation at mosque", "Charitable zakat", "Photocopy and prints",
        "Home cleaning supplies", "Tailoring charges", "Watch repair",
    ],
}

# --- Step 1: Verify user ---
conn = get_db()
try:
    user = conn.execute("SELECT id, name FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        print(f"No user found with id {user_id}.")
        sys.exit(1)

    user_name = user["name"]

    # --- Step 2: Generate expenses ---
    end = datetime.now()
    start = end - timedelta(days=months * 30)
    day_span = max(1, (end - start).days - 1)

    expenses = []
    for _ in range(count):
        cat_idx = random.choices(range(len(categories)), weights=weights, k=1)[0]
        cat_name, cat_min, cat_max = categories[cat_idx][0], categories[cat_idx][1], categories[cat_idx][2]
        amount = round(random.uniform(cat_min, cat_max), 2)
        offset = random.randint(0, day_span)
        date = start + timedelta(days=offset)
        desc = random.choice(descriptions[cat_name])
        expenses.append((user_id, amount, cat_name, date.strftime("%Y-%m-%d"), desc))

    # --- Step 3: Insert in a single transaction ---
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()

    # --- Step 4: Confirm ---
    dates = [e[3] for e in expenses]
    print(f"Inserted {len(expenses)} expenses for user \"{user_name}\" (ID: {user_id})")
    print(f"Date range: {min(dates)} to {max(dates)}")
    print()
    print(f"{'ID':>4} | {'Amount':>10} | {'Category':<13} | {'Date':<10} | {'Description':<30}")
    print(f"{'-'*4}-+-{'-'*10}-+-{'-'*13}-+-{'-'*10}-+-{'-'*30}")
    for i, e in enumerate(expenses[:5], 1):
        print(f"{i:4} | PKR {e[1]:>7.2f} | {e[2]:<13} | {e[3]:<10} | {e[4]:<30}")
    if len(expenses) > 5:
        print(f"  ... and {len(expenses) - 5} more")

finally:
    conn.close()
