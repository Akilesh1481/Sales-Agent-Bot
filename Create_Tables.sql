PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Customers (
  customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name VARCHAR(50) NOT NULL,
  last_name VARCHAR(50) NOT NULL,
  gender TEXT CHECK(gender IN ('Male','Female')),
  household_income INTEGER,
  birthdate DATE NOT NULL,
  phone_number TEXT NOT NULL,
  email VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS Manufacture_Plant (
  manufacture_plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_name VARCHAR(50) NOT NULL,
  plant_type VARCHAR(10) CHECK (plant_type IN ('Assembly','Parts')),
  plant_location VARCHAR(100),
  company_owned INTEGER CHECK(company_owned IN (0,1))
);

CREATE TABLE IF NOT EXISTS Brands (
  brand_id INTEGER PRIMARY KEY AUTOINCREMENT,
  brand_name VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS Dealers (
  dealer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  dealer_name VARCHAR(50) NOT NULL,
  dealer_address VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS Models (
  model_id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_name VARCHAR(50) NOT NULL,
  model_base_price INTEGER NOT NULL,
  brand_id INTEGER NOT NULL,
  FOREIGN KEY (brand_id) REFERENCES Brands(brand_id)
);

CREATE TABLE IF NOT EXISTS Car_Parts (
  part_id INTEGER PRIMARY KEY AUTOINCREMENT,
  part_name VARCHAR(100) NOT NULL,
  manufacture_plant_id INTEGER NOT NULL,
  manufacture_start_date DATE NOT NULL,
  manufacture_end_date DATE,
  part_recall INTEGER DEFAULT 0 CHECK (part_recall IN (0,1)),
  FOREIGN KEY (manufacture_plant_id) REFERENCES Manufacture_Plant(manufacture_plant_id)
);

CREATE TABLE IF NOT EXISTS Car_Options (
  option_set_id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER,
  engine_id INTEGER NOT NULL,
  transmission_id INTEGER NOT NULL,
  chassis_id INTEGER NOT NULL,
  premium_sound_id INTEGER,
  color VARCHAR(30) NOT NULL,
  option_set_price INTEGER NOT NULL,
  FOREIGN KEY (model_id) REFERENCES Models(model_id),
  FOREIGN KEY (engine_id) REFERENCES Car_Parts(part_id),
  FOREIGN KEY (premium_sound_id) REFERENCES Car_Parts(part_id),
  FOREIGN KEY (transmission_id) REFERENCES Car_Parts(part_id),
  FOREIGN KEY (chassis_id) REFERENCES Car_Parts(part_id)
);

CREATE TABLE IF NOT EXISTS Car_Vins (
  vin INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id INTEGER NOT NULL,
  option_set_id INTEGER NOT NULL,
  manufactured_date DATE NOT NULL,
  manufactured_plant_id INTEGER NOT NULL,
  FOREIGN KEY (model_id) REFERENCES Models(model_id),
  FOREIGN KEY (manufactured_plant_id) REFERENCES Manufacture_Plant(manufacture_plant_id),
  FOREIGN KEY (option_set_id) REFERENCES Car_Options(option_set_id)
);

CREATE TABLE IF NOT EXISTS Dealer_Brand (
  dealer_id INTEGER NOT NULL,
  brand_id INTEGER NOT NULL,
  FOREIGN KEY (dealer_id) REFERENCES Dealers(dealer_id),
  FOREIGN KEY (brand_id) REFERENCES Brands(brand_id),
  PRIMARY KEY (dealer_id, brand_id)
);

CREATE TABLE IF NOT EXISTS Customer_Ownership (
  customer_id INTEGER NOT NULL,
  vin INTEGER NOT NULL,
  purchase_date DATE NOT NULL,
  purchase_price INTEGER NOT NULL,
  warantee_expire_date DATE,
  dealer_id INTEGER NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES Customers(customer_id),
  FOREIGN KEY (vin) REFERENCES Car_Vins(vin),
  FOREIGN KEY (dealer_id) REFERENCES Dealers(dealer_id),
  PRIMARY KEY (customer_id, vin)
);