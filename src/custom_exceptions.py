# src/custom_exceptions.py

"""Custom exceptions cho hệ thống chấm công."""


class FaceAttendanceException(Exception):
    """Base exception cho hệ thống."""
    pass


class FaceDetectionError(FaceAttendanceException):
    """Lỗi khi không phát hiện được khuôn mặt."""
    pass


class ModelNotTrainedError(FaceAttendanceException):
    """Lỗi khi model chưa được train."""
    pass


class InsufficientDataError(FaceAttendanceException):
    """Lỗi khi không đủ dữ liệu để train."""
    pass


class InvalidImageError(FaceAttendanceException):
    """Lỗi khi ảnh không hợp lệ."""
    pass


class EmployeeNotFoundError(FaceAttendanceException):
    """Lỗi khi không tìm thấy nhân viên."""
    pass


class AttendanceValidationError(FaceAttendanceException):
    """Lỗi validation khi chấm công (ví dụ: quá nhanh)."""
    pass

