import cv2
import numpy as np
import time
from typing import Tuple, List, Optional

class LivenessDetector:
    """
    Phát hiện thực thể sống.
    Phiên bản rút gọn: Tạm thời disable check do thiếu thư viện MediaPipe trên Python 3.13.
    """
    
    def __init__(self):
        pass
        
    def check_liveness(self, image: np.ndarray) -> Tuple[bool, str]:
        """
        Kiểm tra liveness.
        """
        # Tạm thời bypass
        return True, "Liveness check disabled (Python 3.13 compatibility)"
