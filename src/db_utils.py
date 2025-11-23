# src/db_utils.py

import os
import sqlite3
import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from src.logger import get_logger
from src.custom_exceptions import AttendanceValidationError, EmployeeNotFoundError

logger = get_logger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "attendance.db")

# Configuration
MIN_CHECKIN_GAP_MINUTES = 1  # Minimum time gap giữa 2 lần chấm công liên tiếp


def get_connection():
    """Tạo connection đến SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db_connection():
    """
    Context manager cho database connection với transaction support.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()  # Auto commit nếu không có exception
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Khởi tạo database với các bảng cần thiết và indexes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Bảng employees
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                gender TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bảng face_images (lưu đường dẫn ảnh khuôn mặt của nhân viên)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        """)

        # Bảng attendance_log (lịch sử chấm công)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                code TEXT,
                name TEXT,
                check_type TEXT NOT NULL,
                score REAL,
                is_unknown INTEGER DEFAULT 0,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
            )
        """)

        # Bảng embeddings (lưu vector khuôn mặt)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                vector TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        """)
        
        # Bảng shifts (ca làm việc)
        # day_of_week: 0=Monday, 6=Sunday
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                start_time TEXT NOT NULL, -- HH:MM
                end_time TEXT NOT NULL,   -- HH:MM
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        """)

        # Cập nhật bảng attendance_log để thêm cột late_minutes nếu chưa có
        try:
            cursor.execute("ALTER TABLE attendance_log ADD COLUMN late_minutes REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Cột đã tồn tại
            
        try:
            cursor.execute("ALTER TABLE attendance_log ADD COLUMN shift_id INTEGER")
        except sqlite3.OperationalError:
            pass

        # Tạo indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shifts_employee ON shifts(employee_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shifts_day ON shifts(day_of_week)")

    logger.info(f"Database initialized at: {DB_PATH}")


def create_employee(code: str, name: str, gender: Optional[str] = None) -> int:
    """Tạo nhân viên mới. Trả về employee_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO employees (code, name, gender) VALUES (?, ?, ?)",
            (code, name, gender)
        )
        employee_id = cursor.lastrowid
        logger.info(f"Created employee: {code} - {name} (ID: {employee_id})")
        return employee_id


def get_employee_by_id(employee_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin nhân viên theo ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_employee_permanently(employee_id: int):
    """Xóa vĩnh viễn nhân viên và toàn bộ dữ liệu liên quan."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Delete face images
        cursor.execute("DELETE FROM face_images WHERE employee_id = ?", (employee_id,))
        
        # Delete embeddings
        cursor.execute("DELETE FROM embeddings WHERE employee_id = ?", (employee_id,))
        
        # Delete attendance logs (optional, clean up)
        cursor.execute("DELETE FROM attendance_log WHERE employee_id = ?", (employee_id,))
        
        # Delete shifts
        cursor.execute("DELETE FROM shifts WHERE employee_id = ?", (employee_id,))
        
        # Delete employee
        cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        
        logger.info(f"Permanently deleted employee ID: {employee_id} and all related data")


def list_employees(active_only: bool = True) -> List[Dict[str, Any]]:
    """Lấy danh sách nhân viên."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees ORDER BY code")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# --- SHIFT MANAGEMENT ---

def assign_shift(employee_id: int, day_of_week: int, start_time: str, end_time: str):
    """Gán ca làm việc cho nhân viên."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Xóa ca cũ cùng ngày (nếu mỗi ngày chỉ 1 ca)
        cursor.execute(
            "DELETE FROM shifts WHERE employee_id = ? AND day_of_week = ?",
            (employee_id, day_of_week)
        )
        cursor.execute(
            "INSERT INTO shifts (employee_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)",
            (employee_id, day_of_week, start_time, end_time)
        )
        logger.info(f"Assigned shift for emp {employee_id}: Day {day_of_week}, {start_time}-{end_time}")

def get_shifts_for_employee(employee_id: int) -> List[Dict[str, Any]]:
    """Lấy danh sách ca làm của nhân viên."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM shifts WHERE employee_id = ? ORDER BY day_of_week",
            (employee_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_active_shift(employee_id: int, check_time: datetime) -> Optional[Dict[str, Any]]:
    """Tìm ca làm việc khớp với thời gian hiện tại (hoặc gần nhất trong ngày)."""
    day_of_week = check_time.weekday() # 0=Mon, 6=Sun
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM shifts WHERE employee_id = ? AND day_of_week = ?",
            (employee_id, day_of_week)
        )
        # Giả sử mỗi ngày 1 ca, nếu nhiều ca cần logic phức tạp hơn
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- ATTENDANCE LOGGING ---

def log_attendance_event(
    employee_id: Optional[int],
    code: Optional[str],
    name: Optional[str],
    check_type: str,
    score: float,
    is_unknown: bool = False,
    validate_timing: bool = True,
):
    """
    Ghi log chấm công có tính toán trễ giờ.
    """
    # Validate timing (30s gap)
    if not is_unknown and employee_id and validate_timing:
        validate_attendance_timing(employee_id)
    
    late_minutes = 0.0
    shift_id = None
    
    if not is_unknown and employee_id and check_type == "IN":
        now = datetime.now()
        shift = get_active_shift(employee_id, now)
        if shift:
            shift_id = shift['id']
            # Parse start_time (HH:MM)
            sh_h, sh_m = map(int, shift['start_time'].split(':'))
            shift_start = now.replace(hour=sh_h, minute=sh_m, second=0, microsecond=0)
            
            # Tính trễ
            if now > shift_start:
                diff = (now - shift_start).total_seconds() / 60.0
                # Cho phép trễ 5 phút (grace period) - tùy chọn
                if diff > 0:
                    late_minutes = diff

    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            """INSERT INTO attendance_log 
               (employee_id, code, name, check_type, score, is_unknown, timestamp, late_minutes, shift_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (employee_id, code, name, check_type, score, 1 if is_unknown else 0, timestamp, late_minutes, shift_id)
        )
        
        status_msg = f"Late {late_minutes:.1f}m" if late_minutes > 0 else "On Time"
        if is_unknown:
            logger.warning(f"Unknown attendance logged")
        else:
            logger.info(f"Attendance: {name} ({check_type}) - {status_msg}")


def validate_attendance_timing(employee_id: int) -> None:
    """Validate thời gian chấm công (30s gap)."""
    last_record = get_last_attendance_for_employee(employee_id)
    if last_record:
        last_time = datetime.fromisoformat(last_record['timestamp'])
        now = datetime.now()
        time_diff = (now - last_time).total_seconds() # seconds
        
        if time_diff < 30: # 30 seconds gap
            raise AttendanceValidationError(
                f"Chấm công quá nhanh! Vui lòng đợi 30 giây. (Còn {30 - time_diff:.0f}s)"
            )

# --- HISTORY ---

def get_attendance_history(employee_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Lấy lịch sử chấm công, filter theo nhân viên (loại trừ Unknown)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if employee_id:
            cursor.execute("""
                SELECT * FROM attendance_log 
                WHERE employee_id = ? AND is_unknown = 0
                ORDER BY timestamp DESC LIMIT ?
            """, (employee_id, limit))
        else:
            # Exclude unknown entries from general history
            cursor.execute("""
                SELECT * FROM attendance_log 
                WHERE is_unknown = 0
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()



def get_last_attendance_for_employee(employee_id: int) -> Optional[Dict[str, Any]]:
    """Lấy bản ghi chấm công gần nhất của nhân viên."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM attendance_log 
               WHERE employee_id = ? AND is_unknown = 0
               ORDER BY timestamp DESC LIMIT 1""",
            (employee_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_daily_sessions(limit_days: int = 7) -> List[Dict[str, Any]]:
    """Lấy lịch sử chấm công theo ngày (group by ngày)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_checks,
                SUM(CASE WHEN is_unknown = 0 THEN 1 ELSE 0 END) as known_checks,
                SUM(CASE WHEN is_unknown = 1 THEN 1 ELSE 0 END) as unknown_checks
            FROM attendance_log
            WHERE DATE(timestamp) >= DATE('now', '-' || ? || ' days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, (limit_days,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# --- EXTENDED FUNCTIONS ---

def add_face_image(employee_id: int, image_path: str):
    """Thêm ảnh khuôn mặt cho nhân viên."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO face_images (employee_id, image_path) VALUES (?, ?)",
            (employee_id, image_path)
        )
        logger.debug(f"Added face image for employee {employee_id}: {image_path}")


def save_embedding(employee_id: int, vector):
    """Lưu vector embedding vào database."""
    vector_json = json.dumps(vector.tolist() if hasattr(vector, 'tolist') else vector)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO embeddings (employee_id, vector) VALUES (?, ?)",
            (employee_id, vector_json)
        )
        logger.debug(f"Saved embedding for employee {employee_id}")


def get_all_embeddings() -> Dict[int, List[float]]:
    """
    Lấy tất cả embedding của nhân viên.
    Returns: {employee_id: vector}
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id, emb.vector
            FROM embeddings emb
            JOIN employees e ON emb.employee_id = e.id
            WHERE e.active = 1
            ORDER BY emb.created_at DESC
        """)
        rows = cursor.fetchall()
        
        # Collect ALL embeddings for each employee
        employee_embeddings = {}  # {emp_id: [vector1, vector2, ...]}
        for row in rows:
            emp_id = row['id']
            vector = json.loads(row['vector'])
            if emp_id not in employee_embeddings:
                employee_embeddings[emp_id] = []
            employee_embeddings[emp_id].append(vector)
        
        # Average embeddings for each employee (better accuracy)
        embeddings = {}
        for emp_id, vectors in employee_embeddings.items():
            if len(vectors) == 1:
                embeddings[emp_id] = vectors[0]
            else:
                # Average multiple embeddings
                avg_vector = np.mean(np.array(vectors), axis=0).tolist()
                embeddings[emp_id] = avg_vector
                logger.debug(f"Employee {emp_id}: averaged {len(vectors)} embeddings")
        
        return embeddings
    finally:
        conn.close()
