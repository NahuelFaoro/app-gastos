from __future__ import annotations

"""Esquema SQLite base de App Gastos.

Las migraciones incrementales permanecen en ``Database.initialize``; este módulo
contiene únicamente el esquema idempotente para instalaciones nuevas. Separarlo
evita mezclar cientos de líneas SQL con la orquestación de inicio.
"""

BASE_SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL DEFAULT 'Cuenta',
                    opening_balance REAL NOT NULL DEFAULT 0,
                    color TEXT NOT NULL DEFAULT '#4CCFA9',
                    archived INTEGER NOT NULL DEFAULT 0,
                    include_in_balance INTEGER NOT NULL DEFAULT 1,
                    credit_limit REAL NOT NULL DEFAULT 0,
                    closing_day INTEGER,
                    due_day INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('expense','income')),
                    parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                    color TEXT NOT NULL DEFAULT '#4CCFA9',
                    secondary_color TEXT,
                    icon TEXT NOT NULL DEFAULT 'other',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('expense','income','transfer')),
                    amount REAL NOT NULL CHECK(amount > 0),
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    to_account_id INTEGER REFERENCES accounts(id),
                    category_id INTEGER REFERENCES categories(id),
                    tx_date TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    recurring_id INTEGER,
                    installment_plan_id INTEGER,
                    installment_number INTEGER,
                    installment_total INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    category_id INTEGER REFERENCES categories(id),
                    account_id INTEGER REFERENCES accounts(id),
                    start_date TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS recurring_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN ('expense','income','transfer')),
                    amount REAL NOT NULL CHECK(amount > 0),
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    to_account_id INTEGER REFERENCES accounts(id),
                    category_id INTEGER REFERENCES categories(id),
                    description TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    frequency TEXT NOT NULL CHECK(frequency IN ('daily','weekly','monthly','yearly')),
                    interval_value INTEGER NOT NULL DEFAULT 1,
                    next_date TEXT NOT NULL,
                    anchor_day INTEGER,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS card_installment_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    total_amount REAL NOT NULL CHECK(total_amount > 0),
                    installments INTEGER NOT NULL CHECK(installments > 1),
                    base_amount REAL NOT NULL CHECK(base_amount > 0),
                    purchase_date TEXT NOT NULL,
                    next_installment_date TEXT NOT NULL,
                    next_number INTEGER NOT NULL DEFAULT 2,
                    description TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS account_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    amount REAL NOT NULL,
                    adjustment_date TEXT NOT NULL,
                    adjustment_type TEXT NOT NULL DEFAULT 'manual',
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS imported_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    tx_date TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('expense','income')),
                    amount REAL NOT NULL CHECK(amount > 0),
                    description TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','imported','ignored')),
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, external_id)
                );

                CREATE TABLE IF NOT EXISTS import_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('expense','income')),
                    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, pattern, kind)
                );

                CREATE TABLE IF NOT EXISTS historical_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL DEFAULT 'legacy_excel',
                    file_name TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    rows_count INTEGER NOT NULL DEFAULT 0,
                    total_expense REAL NOT NULL DEFAULT 0,
                    total_income REAL NOT NULL DEFAULT 0,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS historical_monthly (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id INTEGER NOT NULL REFERENCES historical_imports(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK(kind IN ('expense','income')),
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
                    category_name TEXT NOT NULL,
                    subcategory_name TEXT NOT NULL DEFAULT '',
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(import_id,kind,year,month,category_name,subcategory_name)
                );

                CREATE TABLE IF NOT EXISTS flex_zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT NOT NULL DEFAULT '#4CCFA9',
                    active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS flex_zone_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_id INTEGER NOT NULL REFERENCES flex_zones(id) ON DELETE CASCADE,
                    price REAL NOT NULL CHECK(price >= 0),
                    effective_from TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(zone_id, effective_from)
                );

                CREATE TABLE IF NOT EXISTS flex_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zone_id INTEGER NOT NULL REFERENCES flex_zones(id) ON DELETE RESTRICT,
                    week_start TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
                    unit_price REAL NOT NULL CHECK(unit_price >= 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS flex_income_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL UNIQUE,
                    transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
                    amount REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS work_trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client TEXT NOT NULL DEFAULT '',
                    origin TEXT NOT NULL DEFAULT '',
                    trip_date TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    trip_count INTEGER NOT NULL DEFAULT 1 CHECK(trip_count > 0),
                    stop_count INTEGER NOT NULL DEFAULT 1 CHECK(stop_count > 0),
                    bulky INTEGER NOT NULL DEFAULT 0,
                    rain INTEGER NOT NULL DEFAULT 0,
                    flex INTEGER NOT NULL DEFAULT 0,
                    own_client INTEGER NOT NULL DEFAULT 0,
                    details TEXT NOT NULL DEFAULT '',
                    charged REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS work_trip_destinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trip_id INTEGER NOT NULL REFERENCES work_trips(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL DEFAULT 0,
                    destination TEXT NOT NULL
                );

                -- Tabla legacy de v0.32. Se conserva para que backups viejos
                -- sigan siendo restaurables; desde v0.33 la UI utiliza work_extras.
                CREATE TABLE IF NOT EXISTS work_services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    service_date TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    charged REAL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS work_extras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT NOT NULL DEFAULT '',
                    work_date TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    hours REAL NOT NULL DEFAULT 0 CHECK(hours >= 0),
                    orders INTEGER NOT NULL DEFAULT 0 CHECK(orders >= 0),
                    amount REAL NOT NULL DEFAULT 0 CHECK(amount >= 0),
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS work_day_mileage (
                    work_date TEXT PRIMARY KEY,
                    week_start TEXT NOT NULL,
                    odometer_start REAL,
                    odometer_end REAL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK(odometer_start IS NULL OR odometer_start >= 0),
                    CHECK(odometer_end IS NULL OR odometer_end >= 0)
                );

                CREATE TABLE IF NOT EXISTS work_field_definitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    field_type TEXT NOT NULL CHECK(field_type IN ('check','text','number','money')),
                    ui_type TEXT NOT NULL DEFAULT '',
                    options_json TEXT NOT NULL DEFAULT '[]',
                    built_in_key TEXT UNIQUE,
                    active INTEGER NOT NULL DEFAULT 1,
                    show_in_summary INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS work_trip_field_values (
                    trip_id INTEGER NOT NULL REFERENCES work_trips(id) ON DELETE CASCADE,
                    field_id INTEGER NOT NULL REFERENCES work_field_definitions(id) ON DELETE CASCADE,
                    value_text TEXT,
                    value_number REAL,
                    value_bool INTEGER,
                    PRIMARY KEY(trip_id, field_id)
                );

                CREATE TABLE IF NOT EXISTS work_rate_schemes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('unit','option')),
                    unit_label TEXT NOT NULL DEFAULT '',
                    unit_rate REAL NOT NULL DEFAULT 0 CHECK(unit_rate >= 0),
                    active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS work_rate_options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id INTEGER NOT NULL REFERENCES work_rate_schemes(id) ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    rate REAL NOT NULL DEFAULT 0 CHECK(rate >= 0),
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tx_date);
                CREATE INDEX IF NOT EXISTS idx_tx_kind ON transactions(kind);
                CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id);
                CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category_id);
                CREATE INDEX IF NOT EXISTS idx_tx_kind_date ON transactions(kind, tx_date);
                CREATE INDEX IF NOT EXISTS idx_tx_category_date ON transactions(category_id, tx_date);
                CREATE INDEX IF NOT EXISTS idx_tx_account_date ON transactions(account_id, tx_date);
                CREATE INDEX IF NOT EXISTS idx_import_status_source ON imported_movements(status, source, tx_date);
                CREATE INDEX IF NOT EXISTS idx_import_status_date ON imported_movements(status, tx_date);
                CREATE INDEX IF NOT EXISTS idx_recurring_next ON recurring_transactions(active, next_date);
                CREATE INDEX IF NOT EXISTS idx_installment_next ON card_installment_plans(active, next_installment_date);
                CREATE INDEX IF NOT EXISTS idx_adjustments_account_date ON account_adjustments(account_id, adjustment_date);
                CREATE INDEX IF NOT EXISTS idx_history_month ON historical_monthly(year,month,kind);
                CREATE INDEX IF NOT EXISTS idx_flex_week ON flex_deliveries(week_start, zone_id);
                CREATE INDEX IF NOT EXISTS idx_flex_rates ON flex_zone_rates(zone_id, effective_from);
                CREATE INDEX IF NOT EXISTS idx_work_trips_week ON work_trips(week_start, trip_date);
                CREATE INDEX IF NOT EXISTS idx_work_trips_client ON work_trips(client);
                CREATE INDEX IF NOT EXISTS idx_work_destinations_trip ON work_trip_destinations(trip_id, position);
                CREATE INDEX IF NOT EXISTS idx_work_services_week ON work_services(week_start, service_date);
                CREATE INDEX IF NOT EXISTS idx_work_extras_week ON work_extras(week_start, work_date);
                CREATE INDEX IF NOT EXISTS idx_work_extras_app ON work_extras(app_name);
                CREATE INDEX IF NOT EXISTS idx_work_mileage_week ON work_day_mileage(week_start, work_date);
                CREATE INDEX IF NOT EXISTS idx_work_fields_order ON work_field_definitions(active, sort_order, id);
                CREATE INDEX IF NOT EXISTS idx_work_values_trip ON work_trip_field_values(trip_id, field_id);
                CREATE INDEX IF NOT EXISTS idx_work_rates_order ON work_rate_schemes(active, sort_order, id);
                CREATE INDEX IF NOT EXISTS idx_work_rate_options ON work_rate_options(scheme_id, sort_order, id);
"""
