import sqlite3


DATABASE_NAME = "backend/antarctic.db"


def get_connection():

    connection = sqlite3.connect(
        DATABASE_NAME
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ship_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            speed_knots REAL NOT NULL,
            heading_degrees REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS icebergs (
            iceberg_id TEXT PRIMARY KEY,
            current_latitude REAL NOT NULL,
            current_longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            length_m REAL,
            width_m REAL,
            freeboard_m REAL,
            shape_class TEXT,
            estimated_draft_m REAL,
            draft_uncertainty_m REAL,
            drift_speed_knots REAL,
            drift_direction_degrees REAL,
            predicted_latitude REAL,
            predicted_longitude REAL,
            forecast_time TEXT,
            bias_corrected_latitude REAL,
            bias_corrected_longitude REAL,
            bias_correction_applied INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            source TEXT DEFAULT 'unknown',
            last_updated TEXT
        )
    """)

    try:

        cursor.execute("""
            ALTER TABLE icebergs
            ADD COLUMN source TEXT DEFAULT 'unknown'
        """)

    except sqlite3.OperationalError:

        pass

    try:

        cursor.execute("""
            ALTER TABLE icebergs
            ADD COLUMN last_updated TEXT
        """)

    except sqlite3.OperationalError:

        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sea_ice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            concentration REAL NOT NULL,
            risk_level TEXT NOT NULL,
            confidence REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hazards (
            id TEXT PRIMARY KEY,
            hazard_type TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            radius_m REAL NOT NULL,
            risk_level TEXT NOT NULL,
            confidence REAL NOT NULL,
            source TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            route_id TEXT PRIMARY KEY,
            points TEXT NOT NULL,
            distance_km REAL NOT NULL,
            estimated_fuel_cost REAL,
            risk_level TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    try:
        cursor.execute("ALTER TABLE routes ADD COLUMN points TEXT NOT NULL DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ais_vessels (
            vessel_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            speed_knots REAL NOT NULL DEFAULT 0.0,
            heading_degrees REAL NOT NULL DEFAULT 0.0,
            is_ncpor_fleet INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL
        )
    """)

    connection.commit()

    connection.close()



if __name__ == "__main__":

    initialize_database()

    print(
        "Database initialized successfully."
    )