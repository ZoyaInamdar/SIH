import sqlite3

def update_iceberg_drafts():
    db_path = "c:/Users/ishit/OneDrive/Documents/SIH_prototype/SIH/backend/antarctic.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    updates = [
        ("ICB-2026-A23A", 3400.0, 2200.0, 45.0, 440.0),
        ("ICB-2026-PINN", 1200.0, 750.0, 65.0, 260.0),
        ("ICB-2026-DRYDOCK", 1100.0, 750.0, 32.0, 175.0),
        ("ICB-2026-DOME", 800.0, 550.0, 22.0, 115.0),
        ("ICB-2026-WEDGE", 550.0, 350.0, 16.0, 75.0),
        ("ICB-2026-LOWCONF", 320.0, 220.0, 9.0, 38.0),
        ("ICB-2026-NODRAFT", 700.0, 450.0, 20.0, None)
    ]

    for icb_id, length, width, freeboard, draft in updates:
        c.execute(
            """
            UPDATE icebergs 
            SET length_m = ?, width_m = ?, freeboard_m = ?, estimated_draft_m = ?
            WHERE iceberg_id = ?
            """,
            (length, width, freeboard, draft, icb_id)
        )

    conn.commit()
    print("Database updated successfully:")
    rows = c.execute(
        "SELECT iceberg_id, length_m, width_m, freeboard_m, estimated_draft_m FROM icebergs WHERE iceberg_id LIKE 'ICB-2026%'"
    ).fetchall()
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    update_iceberg_drafts()
