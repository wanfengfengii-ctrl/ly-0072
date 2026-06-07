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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspection_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                building_id INTEGER,
                component_id INTEGER,
                plan_date TEXT NOT NULL,
                plan_type TEXT NOT NULL,
                operator TEXT,
                description TEXT,
                status TEXT NOT NULL DEFAULT '待执行',
                reminder_days INTEGER DEFAULT 7,
                executed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                review_status TEXT NOT NULL DEFAULT '待复核',
                reviewer TEXT,
                review_time TEXT,
                review_note TEXT,
                is_false_alarm INTEGER DEFAULT 0,
                handling_suggestion TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
                UNIQUE(record_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                building_id INTEGER,
                component_id INTEGER,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                report_period_start TEXT,
                report_period_end TEXT,
                generated_by TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE SET NULL,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE SET NULL
            )
        """)

        try:
            cursor.execute("ALTER TABLE records ADD COLUMN review_status TEXT DEFAULT '正常'")
        except Exception:
            pass

        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("moisture_threshold", "20.0")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("consecutive_count", "3")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("default_inspection_interval_days", "30")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("default_reminder_days", "7")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("archive_directory", "archives")
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

    @staticmethod
    def get_default_inspection_interval() -> int:
        return int(SettingsRepository.get("default_inspection_interval_days", "30"))

    @staticmethod
    def set_default_inspection_interval(value: int):
        SettingsRepository.set("default_inspection_interval_days", str(value))

    @staticmethod
    def get_default_reminder_days() -> int:
        return int(SettingsRepository.get("default_reminder_days", "7"))

    @staticmethod
    def set_default_reminder_days(value: int):
        SettingsRepository.set("default_reminder_days", str(value))

    @staticmethod
    def get_archive_directory() -> str:
        return SettingsRepository.get("archive_directory", "archives")

    @staticmethod
    def set_archive_directory(value: str):
        SettingsRepository.set("archive_directory", value)


class InspectionPlanRepository:
    @staticmethod
    def create(building_id: int = None, component_id: int = None,
               plan_date: str = "", plan_type: str = "常规巡检",
               operator: str = "", description: str = "",
               status: str = "待执行", reminder_days: int = 7) -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO inspection_plans (building_id, component_id, plan_date, "
                "plan_type, operator, description, status, reminder_days, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (building_id, component_id, plan_date, plan_type, operator,
                 description, status, reminder_days, now, now)
            )
            return cursor.lastrowid

    @staticmethod
    def update(plan_id: int, building_id: int = None, component_id: int = None,
               plan_date: str = "", plan_type: str = "", operator: str = "",
               description: str = "", status: str = "", reminder_days: int = None,
               executed_at: str = None) -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            if building_id is not None:
                fields.append("building_id=?")
                values.append(building_id)
            if component_id is not None:
                fields.append("component_id=?")
                values.append(component_id)
            if plan_date:
                fields.append("plan_date=?")
                values.append(plan_date)
            if plan_type:
                fields.append("plan_type=?")
                values.append(plan_type)
            if operator is not None:
                fields.append("operator=?")
                values.append(operator)
            if description is not None:
                fields.append("description=?")
                values.append(description)
            if status:
                fields.append("status=?")
                values.append(status)
            if reminder_days is not None:
                fields.append("reminder_days=?")
                values.append(reminder_days)
            if executed_at is not None:
                fields.append("executed_at=?")
                values.append(executed_at)
            fields.append("updated_at=?")
            values.append(now)
            values.append(plan_id)
            cursor.execute(f"UPDATE inspection_plans SET {', '.join(fields)} WHERE id=?", values)
            return cursor.rowcount > 0

    @staticmethod
    def delete(plan_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inspection_plans WHERE id=?", (plan_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all(status: str = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT p.*, b.name as building_name, c.code as component_code, "
                    "c.name as component_name FROM inspection_plans p "
                    "LEFT JOIN buildings b ON p.building_id = b.id "
                    "LEFT JOIN components c ON p.component_id = c.id "
                    "WHERE p.status=? ORDER BY p.plan_date",
                    (status,)
                )
            else:
                cursor.execute("""
                    SELECT p.*, b.name as building_name, c.code as component_code,
                    c.name as component_name FROM inspection_plans p
                    LEFT JOIN buildings b ON p.building_id = b.id
                    LEFT JOIN components c ON p.component_id = c.id
                    ORDER BY p.plan_date
                """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_upcoming(days: int = 30) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, b.name as building_name, c.code as component_code,
                c.name as component_name FROM inspection_plans p
                LEFT JOIN buildings b ON p.building_id = b.id
                LEFT JOIN components c ON p.component_id = c.id
                WHERE p.status IN ('待执行', '已提醒')
                ORDER BY p.plan_date
            """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_building(building_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, b.name as building_name, c.code as component_code,
                c.name as component_name FROM inspection_plans p
                LEFT JOIN buildings b ON p.building_id = b.id
                LEFT JOIN components c ON p.component_id = c.id
                WHERE p.building_id=? ORDER BY p.plan_date
            """, (building_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, b.name as building_name, c.code as component_code,
                c.name as component_name FROM inspection_plans p
                LEFT JOIN buildings b ON p.building_id = b.id
                LEFT JOIN components c ON p.component_id = c.id
                WHERE p.id=?
            """, (plan_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class AnomalyReviewRepository:
    @staticmethod
    def create(record_id: int, component_id: int, review_status: str = "待复核",
               reviewer: str = "", review_note: str = "",
               is_false_alarm: int = 0, handling_suggestion: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO anomaly_reviews (record_id, component_id, review_status, "
                "reviewer, review_note, is_false_alarm, handling_suggestion, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record_id, component_id, review_status, reviewer, review_note,
                 is_false_alarm, handling_suggestion, now, now)
            )
            if cursor.lastrowid:
                cursor.execute(
                    "UPDATE records SET review_status=? WHERE id=?",
                    (review_status, record_id)
                )
            return cursor.lastrowid

    @staticmethod
    def update(review_id: int, review_status: str = "", reviewer: str = "",
               review_note: str = "", is_false_alarm: int = None,
               handling_suggestion: str = "") -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            if review_status:
                fields.append("review_status=?")
                values.append(review_status)
            if reviewer is not None:
                fields.append("reviewer=?")
                values.append(reviewer)
            if review_note is not None:
                fields.append("review_note=?")
                values.append(review_note)
            if is_false_alarm is not None:
                fields.append("is_false_alarm=?")
                values.append(is_false_alarm)
            if handling_suggestion is not None:
                fields.append("handling_suggestion=?")
                values.append(handling_suggestion)
            fields.append("review_time=?")
            values.append(datetime.now().isoformat())
            fields.append("updated_at=?")
            values.append(now)
            values.append(review_id)

            cursor.execute(f"SELECT record_id FROM anomaly_reviews WHERE id=?", (review_id,))
            row = cursor.fetchone()
            if not row:
                return False
            record_id = row[0]

            cursor.execute(f"UPDATE anomaly_reviews SET {', '.join(fields)} WHERE id=?", values)
            if review_status:
                cursor.execute(
                    "UPDATE records SET review_status=? WHERE id=?",
                    (review_status, record_id)
                )
            return cursor.rowcount > 0

    @staticmethod
    def delete(review_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM anomaly_reviews WHERE id=?", (review_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all(status: str = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT ar.*, r.measure_time, r.measure_position, r.moisture,
                    r.temperature, r.humidity, r.operator as record_operator,
                    c.code as component_code, c.name as component_name,
                    b.name as building_name
                    FROM anomaly_reviews ar
                    LEFT JOIN records r ON ar.record_id = r.id
                    LEFT JOIN components c ON ar.component_id = c.id
                    LEFT JOIN buildings b ON c.building_id = b.id
                    WHERE ar.review_status=?
                    ORDER BY ar.created_at DESC
                """, (status,))
            else:
                cursor.execute("""
                    SELECT ar.*, r.measure_time, r.measure_position, r.moisture,
                    r.temperature, r.humidity, r.operator as record_operator,
                    c.code as component_code, c.name as component_name,
                    b.name as building_name
                    FROM anomaly_reviews ar
                    LEFT JOIN records r ON ar.record_id = r.id
                    LEFT JOIN components c ON ar.component_id = c.id
                    LEFT JOIN buildings b ON c.building_id = b.id
                    ORDER BY ar.created_at DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component(component_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.*, r.measure_time, r.measure_position, r.moisture,
                r.temperature, r.humidity
                FROM anomaly_reviews ar
                LEFT JOIN records r ON ar.record_id = r.id
                WHERE ar.component_id=? ORDER BY ar.created_at DESC
            """, (component_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_record(record_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM anomaly_reviews WHERE record_id=?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_id(review_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.*, r.measure_time, r.measure_position, r.moisture,
                c.code as component_code, c.name as component_name,
                b.name as building_name
                FROM anomaly_reviews ar
                LEFT JOIN records r ON ar.record_id = r.id
                LEFT JOIN components c ON ar.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
                WHERE ar.id=?
            """, (review_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class ReportArchiveRepository:
    @staticmethod
    def create(report_type: str, file_name: str, file_path: str,
               building_id: int = None, component_id: int = None,
               file_size: int = None, report_period_start: str = "",
               report_period_end: str = "", generated_by: str = "",
               description: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO report_archives (report_type, building_id, component_id, "
                "file_name, file_path, file_size, report_period_start, report_period_end, "
                "generated_by, description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (report_type, building_id, component_id, file_name, file_path,
                 file_size, report_period_start, report_period_end,
                 generated_by, description, now)
            )
            return cursor.lastrowid

    @staticmethod
    def delete(archive_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM report_archives WHERE id=?", (archive_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all(report_type: str = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            if report_type:
                cursor.execute("""
                    SELECT ra.*, b.name as building_name, c.code as component_code,
                    c.name as component_name FROM report_archives ra
                    LEFT JOIN buildings b ON ra.building_id = b.id
                    LEFT JOIN components c ON ra.component_id = c.id
                    WHERE ra.report_type=? ORDER BY ra.created_at DESC
                """, (report_type,))
            else:
                cursor.execute("""
                    SELECT ra.*, b.name as building_name, c.code as component_code,
                    c.name as component_name FROM report_archives ra
                    LEFT JOIN buildings b ON ra.building_id = b.id
                    LEFT JOIN components c ON ra.component_id = c.id
                    ORDER BY ra.created_at DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_building(building_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ra.*, c.code as component_code, c.name as component_name
                FROM report_archives ra
                LEFT JOIN components c ON ra.component_id = c.id
                WHERE ra.building_id=? ORDER BY ra.created_at DESC
            """, (building_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(archive_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ra.*, b.name as building_name, c.code as component_code,
                c.name as component_name FROM report_archives ra
                LEFT JOIN buildings b ON ra.building_id = b.id
                LEFT JOIN components c ON ra.component_id = c.id
                WHERE ra.id=?
            """, (archive_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
