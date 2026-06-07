import sqlite3
import os
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

DB_FILENAME = "wood_moisture.db"


def get_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, DB_FILENAME)


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS buildings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                built_year TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                component_type TEXT NOT NULL,
                material TEXT,
                position TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE RESTRICT,
                UNIQUE(building_id, code)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                measure_time TEXT NOT NULL,
                measure_position TEXT NOT NULL,
                moisture REAL NOT NULL,
                temperature REAL,
                humidity REAL,
                operator TEXT,
                remark TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE RESTRICT,
                UNIQUE(component_id, measure_time)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("moisture_threshold", "20.0")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("consecutive_count", "3")
        )


class BuildingRepository:
    @staticmethod
    def create(name: str, location: str = "", built_year: str = "",
               description: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO buildings (name, location, built_year, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, location, built_year, description, now, now)
            )
            return cursor.lastrowid

    @staticmethod
    def update(building_id: int, name: str, location: str = "", built_year: str = "",
               description: str = "") -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE buildings SET name=?, location=?, built_year=?, description=?, updated_at=? "
                "WHERE id=?",
                (name, location, built_year, description, now, building_id)
            )
            return cursor.rowcount > 0

    @staticmethod
    def delete(building_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM components WHERE building_id=?", (building_id,))
            if cursor.fetchone()[0] > 0:
                raise ValueError("该建筑下存在构件，无法删除")
            cursor.execute("DELETE FROM buildings WHERE id=?", (building_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM buildings ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(building_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM buildings WHERE id=?", (building_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class ComponentRepository:
    @staticmethod
    def create(building_id: int, code: str, name: str, component_type: str,
               material: str = "", position: str = "", description: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO components (building_id, code, name, component_type, material, "
                "position, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (building_id, code, name, component_type, material, position,
                 description, now, now)
            )
            return cursor.lastrowid

    @staticmethod
    def update(component_id: int, building_id: int, code: str, name: str,
               component_type: str, material: str = "", position: str = "",
               description: str = "") -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE components SET building_id=?, code=?, name=?, component_type=?, "
                "material=?, position=?, description=?, updated_at=? WHERE id=?",
                (building_id, code, name, component_type, material, position,
                 description, now, component_id)
            )
            return cursor.rowcount > 0

    @staticmethod
    def delete(component_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM records WHERE component_id=?", (component_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                raise ValueError(f"该构件存在 {count} 条历史检测记录，无法删除")
            cursor.execute("DELETE FROM components WHERE id=?", (component_id,))
            return cursor.rowcount > 0

    @staticmethod
    def has_records(component_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM records WHERE component_id=?", (component_id,))
            return cursor.fetchone()[0] > 0

    @staticmethod
    def get_by_building(building_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM components WHERE building_id=? ORDER BY code",
                (building_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(component_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM components WHERE id=?", (component_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, b.name as building_name 
                FROM components c 
                LEFT JOIN buildings b ON c.building_id = b.id 
                ORDER BY b.name, c.code
            """)
            return [dict(row) for row in cursor.fetchall()]


class RecordRepository:
    @staticmethod
    def create(component_id: int, measure_time: str, measure_position: str,
               moisture: float, temperature: float = None, humidity: float = None,
               operator: str = "", remark: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO records (component_id, measure_time, measure_position, moisture, "
                "temperature, humidity, operator, remark, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (component_id, measure_time, measure_position, moisture,
                 temperature, humidity, operator, remark, now)
            )
            return cursor.lastrowid

    @staticmethod
    def bulk_create(records: List[Tuple]) -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            data = []
            for r in records:
                data.append((*r, now))
            cursor.executemany(
                "INSERT INTO records (component_id, measure_time, measure_position, moisture, "
                "temperature, humidity, operator, remark, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                data
            )
            return cursor.rowcount

    @staticmethod
    def delete(record_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM records WHERE id=?", (record_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_by_component(component_id: int, position: str = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            if position:
                cursor.execute(
                    "SELECT * FROM records WHERE component_id=? AND measure_position=? "
                    "ORDER BY measure_time",
                    (component_id, position)
                )
            else:
                cursor.execute(
                    "SELECT * FROM records WHERE component_id=? ORDER BY measure_time",
                    (component_id,)
                )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_positions(component_id: int) -> List[str]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT measure_position FROM records WHERE component_id=? "
                "ORDER BY measure_position",
                (component_id,)
            )
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def exists(component_id: int, measure_time: str, measure_position: str = None) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM records WHERE component_id=? AND measure_time=?",
                (component_id, measure_time)
            )
            return cursor.fetchone()[0] > 0


class SettingsRepository:
    @staticmethod
    def get(key: str, default: str = "") -> str:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    @staticmethod
    def set(key: str, value: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value)
            )

    @staticmethod
    def get_moisture_threshold() -> float:
        return float(SettingsRepository.get("moisture_threshold", "20.0"))

    @staticmethod
    def set_moisture_threshold(value: float):
        SettingsRepository.set("moisture_threshold", str(value))

    @staticmethod
    def get_consecutive_count() -> int:
        return int(SettingsRepository.get("consecutive_count", "3"))

    @staticmethod
    def set_consecutive_count(value: int):
        SettingsRepository.set("consecutive_count", str(value))
