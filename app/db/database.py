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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                anomaly_review_id INTEGER,
                defect_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT '一般',
                description TEXT NOT NULL,
                location_detail TEXT,
                discovery_date TEXT NOT NULL,
                discoverer TEXT,
                status TEXT NOT NULL DEFAULT '待处置',
                photo_paths TEXT,
                remark TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE RESTRICT,
                FOREIGN KEY (anomaly_review_id) REFERENCES anomaly_reviews(id) ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                defect_id INTEGER NOT NULL,
                order_no TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                assignee TEXT,
                assign_date TEXT NOT NULL,
                deadline TEXT,
                priority TEXT NOT NULL DEFAULT '中',
                work_content TEXT NOT NULL,
                required_materials TEXT,
                status TEXT NOT NULL DEFAULT '待处理',
                completed_at TEXT,
                operator TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (defect_id) REFERENCES defects(id) ON DELETE RESTRICT
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_open_workorder
            ON work_orders(defect_id)
            WHERE status IN ('待处理', '处理中', '待验收')
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rectification_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_order_id INTEGER NOT NULL,
                track_date TEXT NOT NULL,
                progress TEXT NOT NULL,
                problems TEXT,
                next_steps TEXT,
                tracker TEXT,
                photo_paths TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acceptance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_order_id INTEGER NOT NULL UNIQUE,
                accept_date TEXT NOT NULL,
                accept_result TEXT NOT NULL,
                accept_person TEXT,
                inspection_items TEXT,
                accept_note TEXT,
                photo_paths TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE RESTRICT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS effectiveness_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                defect_id INTEGER NOT NULL UNIQUE,
                eval_date TEXT NOT NULL,
                overall_effect TEXT NOT NULL,
                moisture_before REAL,
                moisture_after REAL,
                moisture_improvement REAL,
                risk_level_before TEXT,
                risk_level_after TEXT,
                durability TEXT,
                aesthetic TEXT,
                eval_note TEXT,
                evaluator TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (defect_id) REFERENCES defects(id) ON DELETE RESTRICT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defect_status_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                defect_id INTEGER NOT NULL,
                work_order_id INTEGER,
                from_status TEXT,
                to_status TEXT NOT NULL,
                operator TEXT,
                change_note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (defect_id) REFERENCES defects(id) ON DELETE CASCADE,
                FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE SET NULL
            )
        """)

        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("defect_reminder_days", "7")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("default_priority", "中")
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
            cursor.execute("""
                SELECT c.*, b.name as building_name 
                FROM components c 
                LEFT JOIN buildings b ON c.building_id = b.id 
                WHERE c.id=?
            """, (component_id,))
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


DEFECT_TYPES = [
    "含水率超标", "木材腐朽", "虫蛀蚁害", "开裂变形",
    "榫卯松动", "油漆剥落", "糟朽软化", "连接节点损坏", "其他病害"
]

DEFECT_SEVERITIES = ["轻微", "一般", "严重", "危急"]

DEFECT_STATUSES = ["待处置", "处置中", "待验收", "已验收", "已完成", "已关闭"]

WORK_ORDER_STATUSES = ["待处理", "处理中", "待验收", "已完成", "已取消"]

PRIORITIES = ["低", "中", "高", "紧急"]

ACCEPT_RESULTS = ["合格", "基本合格", "不合格", "需返工"]

EFFECT_LEVELS = ["优秀", "良好", "一般", "较差"]


class DefectRepository:
    @staticmethod
    def create(component_id: int, defect_type: str, description: str,
               discovery_date: str, anomaly_review_id: int = None,
               severity: str = "一般", location_detail: str = "",
               discoverer: str = "", photo_paths: str = "",
               remark: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO defects (component_id, anomaly_review_id, defect_type,
                   severity, description, location_detail, discovery_date, discoverer,
                   status, photo_paths, remark, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, '待处置', ?, ?, ?, ?)""",
                (component_id, anomaly_review_id, defect_type, severity,
                 description, location_detail, discovery_date, discoverer,
                 photo_paths, remark, now, now)
            )
            defect_id = cursor.lastrowid
            DefectStatusLogRepository.create(
                defect_id=defect_id, from_status=None, to_status="待处置",
                change_note="病害登记创建"
            )
            return defect_id

    @staticmethod
    def update(defect_id: int, **kwargs) -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for k, v in kwargs.items():
                if v is not None:
                    fields.append(f"{k}=?")
                    values.append(v)
            if not fields:
                return False
            fields.append("updated_at=?")
            values.append(now)
            values.append(defect_id)
            cursor.execute(f"UPDATE defects SET {', '.join(fields)} WHERE id=?", values)
            return cursor.rowcount > 0

    @staticmethod
    def update_status(defect_id: int, status: str, operator: str = "",
                      change_note: str = "") -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM defects WHERE id=?", (defect_id,))
            row = cursor.fetchone()
            if not row:
                return False
            old_status = row[0]
            if old_status == status:
                return True
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE defects SET status=?, updated_at=? WHERE id=?",
                (status, now, defect_id)
            )
            if cursor.rowcount > 0:
                DefectStatusLogRepository.create(
                    defect_id=defect_id, from_status=old_status, to_status=status,
                    operator=operator, change_note=change_note
                )
                return True
            return False

    @staticmethod
    def delete(defect_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM work_orders WHERE defect_id=? AND status IN ('待处理', '处理中', '待验收')",
                (defect_id,)
            )
            if cursor.fetchone()[0] > 0:
                raise ValueError("该病害存在未关闭的维修工单，无法删除")
            cursor.execute("DELETE FROM defects WHERE id=?", (defect_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all(status: str = None, component_id: int = None,
                building_id: int = None, defect_type: str = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT d.*, c.code as component_code, c.name as component_name,
                c.component_type, b.name as building_name, b.id as building_id
                FROM defects d
                LEFT JOIN components c ON d.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
            """
            conditions = []
            params = []
            if status:
                conditions.append("d.status=?")
                params.append(status)
            if component_id:
                conditions.append("d.component_id=?")
                params.append(component_id)
            if building_id:
                conditions.append("c.building_id=?")
                params.append(building_id)
            if defect_type:
                conditions.append("d.defect_type=?")
                params.append(defect_type)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY d.created_at DESC"
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(defect_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, c.code as component_code, c.name as component_name,
                c.component_type, b.name as building_name, b.id as building_id
                FROM defects d
                LEFT JOIN components c ON d.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
                WHERE d.id=?
            """, (defect_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_building(building_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, c.code as component_code, c.name as component_name,
                c.component_type FROM defects d
                LEFT JOIN components c ON d.component_id = c.id
                WHERE c.building_id=? ORDER BY d.created_at DESC
            """, (building_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def has_open_work_order(defect_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM work_orders WHERE defect_id=? AND status IN ('待处理', '处理中', '待验收')",
                (defect_id,)
            )
            return cursor.fetchone()[0] > 0

    @staticmethod
    def get_overdue_reminders() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, w.id as work_order_id, w.order_no, w.deadline,
                w.priority, w.assignee, w.status as wo_status,
                c.code as component_code, c.name as component_name,
                b.name as building_name
                FROM defects d
                LEFT JOIN work_orders w ON d.id = w.defect_id
                LEFT JOIN components c ON d.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
                WHERE w.status IN ('待处理', '处理中', '待验收')
                ORDER BY w.deadline ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_statistics(building_id: int = None) -> Dict[str, Any]:
        with get_connection() as conn:
            cursor = conn.cursor()
            where_sql = ""
            params = []
            if building_id:
                where_sql = "WHERE component_id IN (SELECT id FROM components WHERE building_id = ?)"
                params = [building_id]
            cursor.execute(f"SELECT status, COUNT(*) FROM defects {where_sql} GROUP BY status", params)
            rows = cursor.fetchall()
            stats: Dict[str, Any] = {s: 0 for s in DEFECT_STATUSES}
            for r in rows:
                stats[r[0]] = r[1]
            stats["total"] = sum(stats.values())
            cursor.execute(f"SELECT severity, COUNT(*) FROM defects {where_sql} GROUP BY severity", params)
            sev_rows = cursor.fetchall()
            severity_stats = {s: 0 for s in DEFECT_SEVERITIES}
            for r in sev_rows:
                severity_stats[r[0]] = r[1]
            stats["by_severity"] = severity_stats
            cursor.execute(f"SELECT defect_type, COUNT(*) FROM defects {where_sql} GROUP BY defect_type", params)
            type_rows = cursor.fetchall()
            type_stats = {}
            for r in type_rows:
                type_stats[r[0]] = r[1]
            stats["by_type"] = type_stats
            return stats


class WorkOrderRepository:
    @staticmethod
    def generate_order_no() -> str:
        now = datetime.now()
        prefix = f"WO{now.strftime('%Y%m%d')}"
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM work_orders WHERE order_no LIKE ?",
                (prefix + "%",)
            )
            seq = cursor.fetchone()[0] + 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def create(defect_id: int, title: str, work_content: str,
               assign_date: str, assignee: str = "", deadline: str = "",
               priority: str = "中", required_materials: str = "",
               operator: str = "") -> int:
        if DefectRepository.has_open_work_order(defect_id):
            raise ValueError("该病害已存在未关闭的维修工单")
        now = datetime.now().isoformat()
        order_no = WorkOrderRepository.generate_order_no()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO work_orders (defect_id, order_no, title, assignee,
                   assign_date, deadline, priority, work_content, required_materials,
                   status, operator, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '待处理', ?, ?, ?)""",
                (defect_id, order_no, title, assignee, assign_date, deadline,
                 priority, work_content, required_materials, operator, now, now)
            )
            wo_id = cursor.lastrowid
            DefectStatusLogRepository.create(
                defect_id=defect_id, work_order_id=wo_id,
                from_status="待处置", to_status="处置中",
                operator=operator, change_note=f"创建维修工单: {order_no}"
            )
            DefectRepository.update_status(
                defect_id, "处置中", operator, f"创建维修工单: {order_no}"
            )
            return wo_id

    @staticmethod
    def update(work_order_id: int, **kwargs) -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for k, v in kwargs.items():
                if v is not None:
                    fields.append(f"{k}=?")
                    values.append(v)
            if not fields:
                return False
            fields.append("updated_at=?")
            values.append(now)
            values.append(work_order_id)
            cursor.execute(f"UPDATE work_orders SET {', '.join(fields)} WHERE id=?", values)
            return cursor.rowcount > 0

    @staticmethod
    def update_status(work_order_id: int, status: str, operator: str = "",
                      change_note: str = "") -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, status, defect_id FROM work_orders WHERE id=?",
                (work_order_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            old_status = row[1]
            defect_id = row[2]
            if old_status == status:
                return True
            now = datetime.now().isoformat()
            extra = {}
            if status == "已完成":
                extra["completed_at"] = now
            fields = ["status=?", "updated_at=?"]
            values = [status, now]
            for k, v in extra.items():
                fields.append(f"{k}=?")
                values.append(v)
            values.append(work_order_id)
            cursor.execute(
                f"UPDATE work_orders SET {', '.join(fields)} WHERE id=?",
                values
            )
            if cursor.rowcount > 0:
                defect_status_map = {
                    "待处理": "处置中", "处理中": "处置中",
                    "待验收": "待验收", "已完成": "已验收",
                    "已取消": "已关闭"
                }
                new_defect_status = defect_status_map.get(status)
                if new_defect_status:
                    DefectStatusLogRepository.create(
                        defect_id=defect_id, work_order_id=work_order_id,
                        from_status=old_status, to_status=status,
                        operator=operator, change_note=change_note
                    )
                    DefectRepository.update_status(
                        defect_id, new_defect_status, operator,
                        change_note or f"工单状态变更为: {status}"
                    )
                return True
            return False

    @staticmethod
    def delete(work_order_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM work_orders WHERE id=?", (work_order_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            if row[0] in ("处理中", "待验收"):
                raise ValueError("该工单正在处理中或待验收，无法删除")
            cursor.execute("DELETE FROM work_orders WHERE id=?", (work_order_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_all(status: str = None, defect_id: int = None,
                building_id: int = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT w.*, d.description as defect_description, d.defect_type,
                d.severity, d.status as defect_status,
                c.code as component_code, c.name as component_name,
                b.name as building_name
                FROM work_orders w
                LEFT JOIN defects d ON w.defect_id = d.id
                LEFT JOIN components c ON d.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
            """
            conditions = []
            params = []
            if status:
                conditions.append("w.status=?")
                params.append(status)
            if defect_id:
                conditions.append("w.defect_id=?")
                params.append(defect_id)
            if building_id:
                conditions.append("c.building_id=?")
                params.append(building_id)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY w.created_at DESC"
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_id(work_order_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT w.*, d.description as defect_description, d.defect_type,
                d.severity, d.status as defect_status,
                c.code as component_code, c.name as component_name,
                b.name as building_name
                FROM work_orders w
                LEFT JOIN defects d ON w.defect_id = d.id
                LEFT JOIN components c ON d.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
                WHERE w.id=?
            """, (work_order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class RectificationTrackingRepository:
    @staticmethod
    def create(work_order_id: int, track_date: str, progress: str,
               problems: str = "", next_steps: str = "", tracker: str = "",
               photo_paths: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO rectification_tracking (work_order_id, track_date,
                   progress, problems, next_steps, tracker, photo_paths, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (work_order_id, track_date, progress, problems,
                 next_steps, tracker, photo_paths, now)
            )
            return cursor.lastrowid

    @staticmethod
    def delete(track_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM rectification_tracking WHERE id=?", (track_id,))
            return cursor.rowcount > 0

    @staticmethod
    def get_by_work_order(work_order_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM rectification_tracking WHERE work_order_id=? ORDER BY track_date DESC",
                (work_order_id,)
            )
            return [dict(row) for row in cursor.fetchall()]


class AcceptanceRecordRepository:
    @staticmethod
    def create(work_order_id: int, accept_date: str, accept_result: str,
               accept_person: str = "", inspection_items: str = "",
               accept_note: str = "", photo_paths: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR IGNORE INTO acceptance_records
                   (work_order_id, accept_date, accept_result, accept_person,
                   inspection_items, accept_note, photo_paths, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (work_order_id, accept_date, accept_result, accept_person,
                 inspection_items, accept_note, photo_paths, now)
            )
            if cursor.lastrowid:
                if accept_result in ("合格", "基本合格"):
                    WorkOrderRepository.update_status(
                        work_order_id, "已完成", accept_person,
                        f"验收通过，结果: {accept_result}"
                    )
                elif accept_result == "需返工":
                    WorkOrderRepository.update_status(
                        work_order_id, "处理中", accept_person,
                        "验收不通过，需要返工"
                    )
            return cursor.lastrowid

    @staticmethod
    def get_by_work_order(work_order_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM acceptance_records WHERE work_order_id=?",
                (work_order_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_defect(defect_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.*, w.order_no, w.title, d.description as defect_description
                FROM acceptance_records ar
                LEFT JOIN work_orders w ON ar.work_order_id = w.id
                LEFT JOIN defects d ON w.defect_id = d.id
                WHERE d.id=?
            """, (defect_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


class EffectivenessEvaluationRepository:
    @staticmethod
    def create(defect_id: int, eval_date: str, overall_effect: str,
               moisture_before: float = None, moisture_after: float = None,
               risk_level_before: str = "", risk_level_after: str = "",
               durability: str = "", aesthetic: str = "",
               eval_note: str = "", evaluator: str = "") -> int:
        moisture_improvement = None
        if moisture_before is not None and moisture_after is not None and moisture_before > 0:
            moisture_improvement = round((moisture_before - moisture_after) / moisture_before * 100, 1)
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR IGNORE INTO effectiveness_evaluations
                   (defect_id, eval_date, overall_effect, moisture_before,
                   moisture_after, moisture_improvement, risk_level_before,
                   risk_level_after, durability, aesthetic, eval_note,
                   evaluator, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (defect_id, eval_date, overall_effect, moisture_before,
                 moisture_after, moisture_improvement, risk_level_before,
                 risk_level_after, durability, aesthetic, eval_note,
                 evaluator, now)
            )
            if cursor.lastrowid:
                DefectRepository.update_status(
                    defect_id, "已完成", evaluator,
                    f"完成效果评估，结果: {overall_effect}"
                )
            return cursor.lastrowid

    @staticmethod
    def get_by_defect(defect_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM effectiveness_evaluations WHERE defect_id=?",
                (defect_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all(building_id: int = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            where_sql = ""
            params = []
            if building_id:
                where_sql = "WHERE c.building_id = ?"
                params = [building_id]
            cursor.execute(f"""
                SELECT e.*, d.description as defect_description, d.defect_type,
                c.code as component_code, c.name as component_name,
                b.name as building_name
                FROM effectiveness_evaluations e
                LEFT JOIN defects d ON e.defect_id = d.id
                LEFT JOIN components c ON d.component_id = c.id
                LEFT JOIN buildings b ON c.building_id = b.id
                {where_sql}
                ORDER BY e.created_at DESC
            """, params)
            return [dict(row) for row in cursor.fetchall()]


class DefectStatusLogRepository:
    @staticmethod
    def create(defect_id: int, to_status: str, from_status: str = None,
               work_order_id: int = None, operator: str = "",
               change_note: str = "") -> int:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO defect_status_logs
                   (defect_id, work_order_id, from_status, to_status,
                   operator, change_note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (defect_id, work_order_id, from_status, to_status,
                 operator, change_note, now)
            )
            return cursor.lastrowid

    @staticmethod
    def get_by_defect(defect_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM defect_status_logs WHERE defect_id=? ORDER BY created_at ASC",
                (defect_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
