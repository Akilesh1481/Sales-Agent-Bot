#!/usr/bin/env python3
"""
Seed script:
- Executes Create_Tables.sql to create schema.
- Executes seed_data.sql (your provided inserts) where possible.
- Counts rows per table and generates synthetic data (Faker) to reach 150 rows per table.
- Produces sales.db (SQLite).
"""
import sqlite3
import os
import re
import sys
from faker import Faker
import random
from datetime import datetime, timedelta

DB_PATH = "sales.db"
SCHEMA_FILE = "Create_Tables.sql"
INPUT_SEED_FILE = "seed_data.sql"
TARGET_ROWS = 150

fake = Faker()
random.seed(42)
Faker.seed(42)

def exec_sql_file(conn, path):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    # Split on semicolon but keep it simple; sqlite3.executescript can run the whole file
    try:
        conn.executescript(sql)
        return []
    except Exception as e:
        # Try to run statements individually and collect errors
        errors = []
        stmts = [s.strip() + ";" for s in sql.split(";") if s.strip()]
        for s in stmts:
            try:
                conn.executescript(s)
            except Exception as ex:
                errors.append((s[:200], str(ex)))
        return errors

def table_count(conn, table):
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]

def get_ids(conn, table, idcol):
    cur = conn.execute(f"SELECT {idcol} FROM {table}")
    return [r[0] for r in cur.fetchall()]

def safe_commit(conn):
    try:
        conn.commit()
    except Exception as e:
        print("Commit error:", e)

def generate_missing(conn):
    # Order of generation is important for FK resolution.
    # We'll ensure base tables exist: Brands, Manufacture_Plant, Dealers, Models, Car_Parts, Car_Options, Car_Vins, Customers, Dealer_Brand, Customer_Ownership
    # Helpers for counts and inserts:
    def ensure_brands():
        cnt = table_count(conn, "Brands")
        while cnt < TARGET_ROWS:
            name = fake.company()[:50]
            conn.execute("INSERT INTO Brands (brand_name) VALUES (?)", (name,))
            cnt += 1
        safe_commit(conn)

    def ensure_manufacture_plants():
        cnt = table_count(conn, "Manufacture_Plant")
        while cnt < TARGET_ROWS:
            plant = fake.company()[:50]
            ptype = random.choice(["Assembly","Parts"])
            loc = fake.city()[:100]
            co = random.choice([0,1])
            conn.execute("INSERT INTO Manufacture_Plant (plant_name, plant_type, plant_location, company_owned) VALUES (?,?,?,?)",
                         (plant, ptype, loc, co))
            cnt += 1
        safe_commit(conn)

    def ensure_dealers():
        cnt = table_count(conn, "Dealers")
        while cnt < TARGET_ROWS:
            name = fake.company()[:50]
            addr = fake.address()[:200]
            conn.execute("INSERT INTO Dealers (dealer_name, dealer_address) VALUES (?,?)", (name, addr))
            cnt += 1
        safe_commit(conn)

    def ensure_models():
        cnt = table_count(conn, "Models")
        brand_ids = get_ids(conn, "Brands", "brand_id")
        if not brand_ids:
            ensure_brands()
            brand_ids = get_ids(conn, "Brands", "brand_id")
        while cnt < TARGET_ROWS:
            mname = fake.word().capitalize()[:50]
            price = random.randint(15000, 120000)
            brand = random.choice(brand_ids)
            conn.execute("INSERT INTO Models (model_name, model_base_price, brand_id) VALUES (?,?,?)",
                         (mname, price, brand))
            cnt += 1
        safe_commit(conn)

    def ensure_car_parts():
        cnt = table_count(conn, "Car_Parts")
        plant_ids = get_ids(conn, "Manufacture_Plant", "manufacture_plant_id")
        if not plant_ids:
            ensure_manufacture_plants()
            plant_ids = get_ids(conn, "Manufacture_Plant", "manufacture_plant_id")
        while cnt < TARGET_ROWS:
            part = fake.word().capitalize() + " part"
            plant = random.choice(plant_ids)
            start = fake.date_between(start_date='-10y', end_date='today').isoformat()
            
            if random.random() < 0.8:
                end = None
            else:
                start_dt = datetime.fromisoformat(start)
                end = fake.date_between(start_date=start_dt, end_date=start_dt + timedelta(days=365*3)).isoformat()
            recall = 1 if random.random() < 0.05 else 0
            conn.execute("INSERT INTO Car_Parts (part_name, manufacture_plant_id, manufacture_start_date, manufacture_end_date, part_recall) VALUES (?,?,?,?,?)",
                         (part[:100], plant, start, end, recall))
            cnt += 1
        safe_commit(conn)

    def ensure_car_options():
        cnt = table_count(conn, "Car_Options")
        model_ids = get_ids(conn, "Models", "model_id")
        part_ids = get_ids(conn, "Car_Parts", "part_id")
        if not part_ids:
            ensure_car_parts()
            part_ids = get_ids(conn, "Car_Parts", "part_id")
        while cnt < TARGET_ROWS:
            model = random.choice(model_ids) if model_ids and random.random() < 0.9 else None
            engine = random.choice(part_ids)
            transmission = random.choice(part_ids)
            chassis = random.choice(part_ids)
            premium = random.choice(part_ids) if random.random() < 0.3 else None
            color = random.choice(["Black","White","Red","Blue","Silver","Gray","Beige","Green"])
            price = random.randint(500, 15000)
            conn.execute("INSERT INTO Car_Options (model_id, engine_id, transmission_id, chassis_id, premium_sound_id, color, option_set_price) VALUES (?,?,?,?,?,?,?)",
                         (model, engine, transmission, chassis, premium, color, price))
            cnt += 1
        safe_commit(conn)

    def ensure_car_vins():
        cnt = table_count(conn, "Car_Vins")
        model_ids = get_ids(conn, "Models", "model_id")
        option_ids = get_ids(conn, "Car_Options", "option_set_id")
        plant_ids = get_ids(conn, "Manufacture_Plant", "manufacture_plant_id")
        while cnt < TARGET_ROWS:
            model = random.choice(model_ids)
            opt = random.choice(option_ids)
            mdate = fake.date_between(start_date=datetime(2018,1,1).date(), end_date=datetime(2026,12,31).date()).isoformat()
            plant = random.choice(plant_ids)
            conn.execute("INSERT INTO Car_Vins (model_id, option_set_id, manufactured_date, manufactured_plant_id) VALUES (?,?,?,?)",
                         (model, opt, mdate, plant))
            cnt += 1
        safe_commit(conn)

    def ensure_customers():
        cnt = table_count(conn, "Customers")
        while cnt < TARGET_ROWS:
            fn = fake.first_name()[:50]
            ln = fake.last_name()[:50]
            gender = random.choice(["Male","Female"])
            income = random.randint(20000, 400000)
            birth = fake.date_of_birth(minimum_age=18, maximum_age=90).isoformat()
            phone = re.sub(r'\D','', fake.phone_number())[:20]
            email = fake.email()[:128]
            conn.execute("INSERT INTO Customers (first_name, last_name, gender, household_income, birthdate, phone_number, email) VALUES (?,?,?,?,?,?,?)",
                         (fn, ln, gender, income, birth, phone, email))
            cnt += 1
        safe_commit(conn)

    def ensure_dealer_brand():
        cnt = table_count(conn, "Dealer_Brand")
        dealer_ids = get_ids(conn, "Dealers", "dealer_id")
        brand_ids = get_ids(conn, "Brands", "brand_id")
        # create random pairings until we have TARGET_ROWS
        existing = set(conn.execute("SELECT dealer_id, brand_id FROM Dealer_Brand").fetchall())
        while cnt < TARGET_ROWS:
            d = random.choice(dealer_ids)
            b = random.choice(brand_ids)
            if (d,b) in existing:
                # skip duplicates
                continue
            conn.execute("INSERT INTO Dealer_Brand (dealer_id, brand_id) VALUES (?,?)", (d,b))
            existing.add((d,b))
            cnt += 1
        safe_commit(conn)

    def ensure_customer_ownership():
        cnt = table_count(conn, "Customer_Ownership")
        customer_ids = get_ids(conn, "Customers", "customer_id")
        vin_ids = get_ids(conn, "Car_Vins", "vin")
        dealer_ids = get_ids(conn, "Dealers", "dealer_id")
        existing = set(conn.execute("SELECT customer_id, vin FROM Customer_Ownership").fetchall())
        # Create ownership rows until TARGET_ROWS, avoid duplicates
        while cnt < TARGET_ROWS:
            c = random.choice(customer_ids)
            v = random.choice(vin_ids)
            if (c,v) in existing:
                continue
            purchase_date = fake.date_between(start_date=datetime(2018,1,1).date(), end_date=datetime(2026,12,31).date()).isoformat()
            price = random.randint(10000, 120000)
            warantee = None if random.random() < 0.3 else (datetime.fromisoformat(purchase_date) + timedelta(days=365*5)).date().isoformat()
            dealer = random.choice(dealer_ids)
            conn.execute("INSERT INTO Customer_Ownership (customer_id, vin, purchase_date, purchase_price, warantee_expire_date, dealer_id) VALUES (?,?,?,?,?,?)",
                         (c, v, purchase_date, price, warantee, dealer))
            existing.add((c,v))
            cnt += 1
        safe_commit(conn)

    # Run ensures in a safe order
    ensure_brands()
    ensure_manufacture_plants()
    ensure_dealers()
    ensure_models()
    ensure_car_parts()
    ensure_car_options()
    ensure_car_vins()
    ensure_customers()
    ensure_dealer_brand()
    ensure_customer_ownership()

def main():
    # Remove existing DB if user wants fresh start
    if os.path.exists(DB_PATH):
        print(f"Overwriting existing {DB_PATH}")
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Create schema
    print("Creating schema from", SCHEMA_FILE)
    errors = exec_sql_file(conn, SCHEMA_FILE)
    if errors:
        print("Schema execution reported errors (first 5):")
        for s, e in errors[:5]:
            print("Error:", e, "on stmt:", s[:200])

    # Try to execute your provided seed_data.sql (best-effort)
    if os.path.exists(INPUT_SEED_FILE):
        print("Applying provided seed_data.sql (best-effort).")
        seed_errors = exec_sql_file(conn, INPUT_SEED_FILE)
        if seed_errors:
            print(f"Seed file had {len(seed_errors)} failing statements; continuing and will fill missing rows programmatically.")
            # Print a few errors
            for s, e in seed_errors[:5]:
                print("Failed stmt snippet:", s[:200], "error:", e)
    else:
        print("No seed_data.sql found in working dir. Skipping.")

    # Show counts before generation
    tables = ["Brands","Manufacture_Plant","Dealers","Models","Car_Parts","Car_Options","Car_Vins","Customers","Dealer_Brand","Customer_Ownership"]
    print("Row counts before generation:")
    for t in tables:
        try:
            print(t, table_count(conn, t))
        except Exception as e:
            print("Error counting", t, e)

    # Generate missing rows up to TARGET_ROWS
    print("Generating missing rows to reach", TARGET_ROWS, "per table.")
    generate_missing(conn)

    # Final counts
    print("\nFinal row counts:")
    for t in tables:
        try:
            print(t, table_count(conn, t))
        except Exception as e:
            print("Error counting", t, e)

    # Optionally export to SQL dump
    # with open("sales_dump.sql","w",encoding="utf-8") as out:
    #     for line in conn.iterdump():
    #         out.write("%s\n" % line)

    conn.close()
    print("Done. Database written to", DB_PATH)

if __name__ == "__main__":
    main()