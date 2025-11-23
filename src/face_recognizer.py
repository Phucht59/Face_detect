import numpy as np
from deepface import DeepFace
from typing import List, Dict, Any, Optional, Tuple
import os
import cv2
from src.logger import get_logger

logger = get_logger(__name__)

class DeepFaceRecognizer:
    """
    Nhận diện khuôn mặt sử dụng DeepFace (ArcFace/FaceNet).
    Thay thế hoàn toàn PCA cũ.
    """
    
    def __init__(self, model_name="ArcFace", detector_backend="mediapipe"):
        """
        Args:
            model_name: "VGG-Face", "Facenet", "Facenet512", "OpenFace", "DeepFace", "DeepID", "ArcFace", "Dlib", "SFace"
            detector_backend: "opencv", "ssd", "dlib", "mtcnn", "retinaface", "mediapipe"
        """
        self.model_name = model_name
        self.detector_backend = detector_backend
        # Load model trước để tránh delay lần đầu
        logger.info(f"Initializing DeepFace model: {model_name}...")
        try:
            # Dummy build to load weights
            DeepFace.build_model(model_name)
            logger.info("DeepFace model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load DeepFace model: {e}")
            
    def extract_embedding(self, image: np.ndarray) -> Optional[List[float]]:
        """
        Tạo vector embedding từ ảnh khuôn mặt.
        """
        try:
            # DeepFace yêu cầu đường dẫn ảnh hoặc numpy array (BGR)
            # enforce_detection=False vì ta đã detect bằng class FaceDetector rồi
            # Nếu dùng ảnh raw chưa crop thì để True
            
            embedding_objs = DeepFace.represent(
                img_path=image,
                model_name=self.model_name,
                detector_backend="skip", # Đã crop rồi nên skip detection của DeepFace
                enforce_detection=False,
                align=False # Đã align rồi
            )
            
            if embedding_objs and len(embedding_objs) > 0:
                return embedding_objs[0]["embedding"]
            return None
            
        except Exception as e:
            logger.error(f"Error extracting embedding: {e}")
            return None

    @staticmethod
    def cosine_similarity(source_representation: List[float], test_representation: List[float]) -> float:
        """
        Tính độ tương đồng Cosine giữa 2 vector.
        Output: -1.0 đến 1.0 (1.0 là giống hệt nhau)
        """
        a = np.matmul(np.transpose(source_representation), test_representation)
        b = np.sum(np.multiply(source_representation, source_representation))
        c = np.sum(np.multiply(test_representation, test_representation))
        return 1 - (a / (np.sqrt(b) * np.sqrt(c))) # DeepFace trả về distance (càng nhỏ càng tốt), ta convert sang distance

    @staticmethod
    def find_best_match(
        target_embedding: List[float], 
        database_embeddings: Dict[int, List[float]],
        threshold: float = 0.4 # Ngưỡng distance (ArcFace thường là 0.68, nhưng ta để chặt hơn)
    ) -> Tuple[Optional[int], float]:
        """
        Tìm người giống nhất trong database.
        
        Args:
            target_embedding: Vector cần tìm
            database_embeddings: Dict {employee_id: vector}
            threshold: Ngưỡng chấp nhận (Cosine Distance). 
                       Với ArcFace: < 0.68 là cùng 1 người.
                       Càng thấp càng chặt chẽ.
        
        Returns:
            (employee_id, distance) hoặc (None, min_distance)
        """
        min_dist = float("inf")
        best_id = None
        
        for emp_id, db_emb in database_embeddings.items():
            # Tính Cosine Distance (DeepFace dùng distance, không phải similarity)
            # Distance = 1 - Cosine Similarity
            
            a = np.array(target_embedding)
            b = np.array(db_emb)
            
            # Manual cosine distance calculation to be safe
            dot = np.dot(a, b)
            norma = np.linalg.norm(a)
            normb = np.linalg.norm(b)
            cos_sim = dot / (norma * normb)
            dist = 1 - cos_sim
            
            if dist < min_dist:
                min_dist = dist
                best_id = emp_id
                
        if min_dist < threshold:
            return best_id, min_dist
        
        return None, min_dist
