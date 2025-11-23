import cv2
import numpy as np
from deepface import DeepFace
from typing import Tuple, Optional, List, Dict, Any

class FaceDetector:
    """
    Phát hiện khuôn mặt sử dụng DeepFace backends (RetinaFace/OpenCV/SSD).
    Fallback từ MediaPipe do vấn đề tương thích Python 3.13.
    """
    
    def __init__(self, backend="opencv"):
        """
        Args:
            backend: "opencv", "ssd", "dlib", "mtcnn", "retinaface", "yolov8"
        """
        self.backend = backend
        
    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Phát hiện khuôn mặt trong ảnh.
        """
        if image is None:
            return []
            
        try:
            # DeepFace.extract_faces trả về list các dict
            # enforce_detection=False để không crash nếu không thấy mặt
            results = DeepFace.extract_faces(
                img_path=image,
                detector_backend=self.backend,
                enforce_detection=False,
                align=False
            )
            
            faces = []
            for res in results:
                # DeepFace result: {'face': np.array, 'facial_area': {'x': int, 'y': int, 'w': int, 'h': int}, 'confidence': float}
                area = res['facial_area']
                faces.append({
                    'bbox': (area['x'], area['y'], area['w'], area['h']),
                    'score': res.get('confidence', 0.0),
                    'keypoints': {} # DeepFace basic backends don't always return keypoints easily
                })
            return faces
        except Exception:
            return []

    def detect_largest_face(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """Lấy khuôn mặt lớn nhất (chính)."""
        faces = self.detect_faces(image)
        if not faces:
            return None
        
        # Sắp xếp theo diện tích (w * h) giảm dần
        largest = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
        return largest

    def extract_face(
        self, 
        image: np.ndarray, 
        padding: float = 0.0,
        target_size: Optional[Tuple[int, int]] = None
    ) -> Optional[np.ndarray]:
        """
        Cắt ảnh khuôn mặt.
        """
        face = self.detect_largest_face(image)
        if face is None:
            return None
            
        x, y, w, h = face['bbox']
        
        # Thêm padding
        pad_w = int(w * padding)
        pad_h = int(h * padding)
        
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(image.shape[1], x + w + pad_w)
        y2 = min(image.shape[0], y + h + pad_h)
        
        face_img = image[y1:y2, x1:x2]
        
        if target_size is not None and face_img.size > 0:
            face_img = cv2.resize(face_img, target_size)
            
        return face_img

    def align_face(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect and align face using DeepFace.
        Returns the aligned face image (RGB/BGR depending on DeepFace output, usually RGB normalized 0-1 or uint8).
        Note: DeepFace.extract_faces returns normalized float image (0-1) by default. 
        We need to convert it back to uint8 (0-255) for consistency.
        """
        try:
            # Use DeepFace to extract and align
            results = DeepFace.extract_faces(
                img_path=image,
                detector_backend=self.backend,
                enforce_detection=True, # Force detection for alignment
                align=True,
                grayscale=False
            )
            
            if not results:
                return None

            # Get the first/largest face
            # DeepFace returns a list of dicts. We take the one with highest confidence or area.
            # But extract_faces sorts by size usually? Let's just take the first one.
            
            # Find largest face if multiple
            largest_face = max(results, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])
            
            face_img = largest_face['face']
            
            # DeepFace returns image in range [0, 1] float. Convert to [0, 255] uint8
            if face_img.max() <= 1.0:
                face_img = (face_img * 255).astype(np.uint8)
            
            # DeepFace returns RGB. If our system uses BGR (OpenCV), we might need to swap.
            # However, DeepFace models expect RGB usually.
            # But wait, extract_embedding in face_recognizer uses DeepFace.represent which expects path or numpy array.
            # If we pass numpy array, DeepFace expects BGR by default if it's from cv2.imread?
            # DeepFace.extract_faces input is expected to be BGR if numpy array.
            # The output of extract_faces is RGB.
            
            # Let's convert to BGR to maintain consistency with the rest of the app (OpenCV pipeline)
            face_img = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
            
            return face_img
            
        except Exception as e:
            # Fallback to simple crop if alignment fails
            # print(f"Alignment failed: {e}")
            return self.extract_face(image)

