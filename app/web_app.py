# app/web_app.py

import base64
import os
import sys
import time
from datetime import datetime
from typing import Tuple, Optional

import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.face_recognizer import DeepFaceRecognizer
from src.face_detector import FaceDetector
from src.liveness import LivenessDetector
import src.db_utils as db
from src.logger import get_logger
from src.custom_exceptions import (
    FaceDetectionError,
    AttendanceValidationError,
    InvalidImageError,
)

logger = get_logger(__name__)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# Khởi tạo DB (nếu chưa có)
db.init_db()

# Khởi tạo AI Models
face_detector = FaceDetector()
liveness_detector = LivenessDetector()
recognizer = DeepFaceRecognizer(model_name="ArcFace")

logger.info("AI Models initialized (Detector, Liveness, Recognizer)")

def decode_base64_image(base64_string):

    try:
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        img_bytes = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

def _handle_attendance(employee_id: Optional[int], score: float) -> dict:
    """
    Xử lý kết quả nhận diện và log chấm công.
    Returns: dictionary with attendance info for frontend.
    """
    # Recognition threshold
    # Score is converted from distance: score = 1 - distance
    # With new threshold 0.40: score must be > 0.60 (60% similarity)
    RECOGNITION_THRESHOLD = 0.60 
    
    if employee_id is None or score < RECOGNITION_THRESHOLD:
        # Unknown person
        db.log_attendance_event(
            employee_id=None,
            code=None,
            name="Unknown",
            check_type="IN",
            score=score,
            is_unknown=True,
            validate_timing=False
        )
        return {
            "name": "Unknown",
            "message": "Không nhận diện được",
            "score": score,
            "is_unknown": True
        }
    
    # Known employee
    emp = db.get_employee_by_id(employee_id)
    if not emp:
        return {"name": "Unknown", "message": "Lỗi dữ liệu", "score": score, "is_unknown": True}
    
    # Determine check type (IN/OUT) - simple toggle logic
    last_log = db.get_last_attendance_for_employee(employee_id)
    check_type = "OUT" if last_log and last_log.get('check_type') == "IN" else "IN"
    
    # Log attendance
    try:
        db.log_attendance_event(
            employee_id=employee_id,
            code=emp['code'],
            name=emp['name'],
            check_type=check_type,
            score=score,
            is_unknown=False,
            validate_timing=True  # This will enforce 30s gap
        )
        
        # Get late info (if any)
        last_log = db.get_last_attendance_for_employee(employee_id)
        late_minutes = last_log.get('late_minutes', 0) if last_log else 0
        
        status_msg = f"Trễ {late_minutes:.0f} phút" if late_minutes > 0 else "Đúng giờ"
        
        return {
            "name": emp['name'],
            "message": f"Chấm công {check_type} - {status_msg}",
            "score": score,
            "check_type": check_type,
            "late_minutes": late_minutes,
            "is_unknown": False
        }
    except AttendanceValidationError as e:
        # Gap validation failed (e.g., too soon)
        return {
            "name": emp['name'],
            "message": str(e),
            "score": score,
            "validation_failed": True,
            "is_unknown": False
        }

# ========= ROUTES
# --- Routes ---

@app.route('/')
def index():
    """Dashboard chính."""
    stats = db.get_daily_sessions(limit_days=7)
    return render_template('index.html', stats=stats)

@app.route('/employees')
def employees_page():
    """Trang quản lý nhân viên."""
    employees = db.list_employees(active_only=False)
    return render_template('employees.html', employees=employees)

@app.route('/history')
def history_page():
    """Trang lịch sử chấm công."""
    employees = db.list_employees(active_only=False)
    return render_template('history.html', employees=employees)

# --- API Endpoints ---

@app.route('/api/employees', methods=['GET', 'POST'])
def api_employees():
    if request.method == 'GET':
        employees = db.list_employees(active_only=False)
        return jsonify(employees)
    
    if request.method == 'POST':
        data = request.json
        code = data.get('code')
        name = data.get('name')
        gender = data.get('gender')
        
        if not code or not name:
            return jsonify({"error": "Missing code or name"}), 400
            
        try:
            emp_id = db.create_employee(code, name, gender)
            return jsonify({"success": True, "id": emp_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
def api_delete_employee(emp_id):
    """Xóa vĩnh viễn nhân viên."""
    try:
        db.delete_employee_permanently(emp_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/shifts', methods=['POST'])
def api_assign_shift():
    """Gán ca làm việc."""
    data = request.json
    emp_id = data.get('employee_id')
    day = data.get('day_of_week') # 0-6
    start = data.get('start_time') # HH:MM
    end = data.get('end_time') # HH:MM
    
    if not all([emp_id, day is not None, start, end]):
        return jsonify({"error": "Missing data"}), 400
        
    try:
        db.assign_shift(emp_id, int(day), start, end)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/shifts/<int:emp_id>', methods=['GET'])
def api_get_shifts(emp_id):
    """Lấy danh sách ca làm của nhân viên."""
    try:
        shifts = db.get_shifts_for_employee(emp_id)
        return jsonify(shifts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def api_get_history():
    """Lấy lịch sử chấm công (có filter)."""
    emp_id = request.args.get('employee_id', type=int)
    try:
        history = db.get_attendance_history(employee_id=emp_id, limit=200)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/capture_face', methods=['POST'])
def api_capture_face():
    """
    Enrollment: Capture face -> Align -> Extract Embedding -> Save to DB.
    """
    data = request.json
    image_data = data.get('image')
    employee_id = data.get('employee_id')
    
    if not image_data or not employee_id:
        return jsonify({"error": "Missing image or employee_id"}), 400

    try:
        # 1. Decode Base64 -> BGR
        bgr_image = decode_base64_image(image_data)
        
        # 2. Detect & Align
        aligned_face = face_detector.align_face(bgr_image)
        if aligned_face is None:
             return jsonify({"error": "No face detected. Please look straight at the camera."}), 400

        # 3. Save Image (Optional, for reference)
        filename = f"{employee_id}_{int(time.time())}.jpg"
        rel_path = os.path.join("data", "faces", filename)
        abs_path = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        cv2.imwrite(abs_path, aligned_face) # Save aligned face
        
        db.add_face_image(employee_id, rel_path)

        # 4. Extract Embedding & Save to DB
        embedding = recognizer.extract_embedding(aligned_face)
        if embedding is None:
             return jsonify({"error": "Could not extract face features."}), 400
             
        db.save_embedding(employee_id, embedding)
        
        logger.info(f"Enrolled employee {employee_id}: Saved image & embedding.")
        return jsonify({"success": True, "image_path": rel_path})

    except Exception as e:
        logger.error(f"Error in capture_face: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/recognize_webcam', methods=['POST'])
def api_recognize_webcam():
    """
    Real-time Recognition:
    1. Liveness Check (Disabled/Placeholder)
    2. Detect & Align
    3. Extract Embedding
    4. Compare with DB Embeddings (Cosine Similarity)
    5. Log Attendance (with Shift Logic)
    """
    data = request.json
    image_data = data.get('image')
    
    if not image_data:
        return jsonify({"error": "No image data"}), 400

    try:
        bgr = decode_base64_image(image_data)
        
        # 1. Liveness Check
        is_alive, liveness_msg = liveness_detector.check_liveness(bgr)
        if not is_alive:
             return jsonify({"success": False, "message": liveness_msg, "liveness_failed": True})

        # 2. Detect & Align
        aligned_face = face_detector.align_face(bgr)
        if aligned_face is None:
            return jsonify({"success": False, "message": "No face detected"})

        # 3. Extract Embedding
        target_embedding = recognizer.extract_embedding(aligned_face)
        if target_embedding is None:
             return jsonify({"success": False, "message": "Could not extract features"})

        # 4. Compare with DB
        db_embeddings = db.get_all_embeddings() # {emp_id: vector}
        # Threshold updated: 0.40 is safe for ArcFace with aligned faces.
        # Previous 0.15 was too strict (workaround for unaligned faces).
        # NOTE: You MUST re-enroll employees for this to work effectively!
        best_id, min_dist = recognizer.find_best_match(target_embedding, db_embeddings, threshold=0.40)
        
        # DEBUG: Log recognition results
        logger.info(f"Recognition result: best_id={best_id}, distance={min_dist:.4f}, threshold=0.40")
        if best_id:
            emp = db.get_employee_by_id(best_id)
            logger.info(f"✓ Matched to: {emp.get('name')} (ID: {best_id})")
        else:
            logger.info(f"✗ No match found (distance {min_dist:.4f} > threshold 0.40)")
        
        # Convert distance to score (0 -> 1) cho frontend dễ hiển thị
        # Distance càng nhỏ càng tốt (0 là giống hệt)
        # Score = 1 - distance (gần đúng)
        score = 1.0 - min_dist
        
        # 5. Handle Result
        info = _handle_attendance(best_id, score)
        info["success"] = True
        info["liveness"] = liveness_msg
        
        return jsonify(info)

    except (FaceDetectionError, AttendanceValidationError, InvalidImageError) as e:
        logger.warning(f"Recognition failed: {e}")
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Lỗi server: {str(e)}"}), 500


# ----- LỊCH SỬ CHẤM CÔNG ----- #

@app.route("/api/history_sessions", methods=["GET"])
def api_history_sessions():
    limit_days = int(request.args.get("limit_days", 7))
    sessions = get_daily_sessions(limit_days=limit_days)
    return jsonify({"success": True, "data": sessions})


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Starting Face Attendance Web Application (DeepFace + MediaPipe)")
    logger.info(f"Database: {db.DB_PATH}")
    # Initialize DB
    db.init_db()
    app.run(debug=True, port=5000)
