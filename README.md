# Face Detect - Hệ thống chấm công bằng nhận diện khuôn mặt

Đây là project xây dựng hệ thống chấm công bằng nhận diện khuôn mặt sử dụng **Python, Flask, OpenCV, DeepFace/ArcFace và SQLite**.

Project cho phép thêm nhân viên, lưu dữ liệu khuôn mặt, nhận diện khuôn mặt qua webcam và ghi nhận lịch sử chấm công vào database.

---

## Chức năng chính

* Thêm, xem và xoá nhân viên
* Chụp ảnh khuôn mặt nhân viên bằng webcam
* Lưu ảnh khuôn mặt và vector đặc trưng
* Nhận diện khuôn mặt theo thời gian thực
* Tự động ghi nhận chấm công vào / ra
* Quản lý lịch sử chấm công
* Có hỗ trợ phân ca làm việc
* Lưu log trong quá trình chạy hệ thống

---

## Công nghệ sử dụng

* Python
* Flask
* OpenCV
* DeepFace
* ArcFace
* SQLite
* HTML, CSS, JavaScript

---

## Cấu trúc thư mục

```text
Face_detect/
│
├── app/
│   └── web_app.py              # File chạy chính của Flask
│
├── src/
│   ├── face_detector.py        # Xử lý phát hiện khuôn mặt
│   ├── face_recognizer.py      # Nhận diện khuôn mặt
│   ├── db_utils.py             # Xử lý database
│   ├── logger.py               # Ghi log hệ thống
│   ├── liveness.py             # Kiểm tra khuôn mặt thật/giả
│   └── custom_exceptions.py    # Xử lý lỗi riêng
│
├── templates/                  # Giao diện HTML
├── static/                     # File CSS, JS
├── data/                       # Lưu database và ảnh khuôn mặt
├── logs/                       # File log
├── models/                     # Thư mục model
│
├── requirements.txt            # Danh sách thư viện
├── DEPLOYMENT.md               # Hướng dẫn deploy
└── README.md
```

---

## Cách cài đặt

### 1. Clone project

```bash
git clone https://github.com/Phucht59/Face_detect.git
cd Face_detect
```

### 2. Tạo môi trường ảo

Trên Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Trên macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Cài thư viện

```bash
pip install -r requirements.txt
```

### 4. Khởi tạo database

```bash
python -c "from src.db_utils import init_db; init_db()"
```

### 5. Chạy project

```bash
python app/web_app.py
```

Sau đó mở trình duyệt và truy cập:

```text
http://localhost:5000
```

---

## Cách sử dụng

### Thêm nhân viên

Vào trang quản lý nhân viên và nhập thông tin nhân viên như mã nhân viên, họ tên, giới tính.

### Lưu khuôn mặt

Sau khi thêm nhân viên, sử dụng webcam để chụp ảnh khuôn mặt.
Hệ thống sẽ lưu ảnh và tạo vector đặc trưng để phục vụ cho bước nhận diện.

### Nhận diện và chấm công

Khi mở camera, hệ thống sẽ nhận diện khuôn mặt.
Nếu khuôn mặt trùng với dữ liệu đã lưu, hệ thống sẽ ghi nhận chấm công vào hoặc ra.

### Xem lịch sử

Có thể xem lại lịch sử chấm công gồm tên nhân viên, mã nhân viên, thời gian, loại chấm công và điểm nhận diện.

---

## Cách hoạt động

Quy trình xử lý chính của hệ thống:

```text
Webcam
  ↓
Phát hiện khuôn mặt
  ↓
Căn chỉnh khuôn mặt
  ↓
Trích xuất đặc trưng bằng DeepFace / ArcFace
  ↓
So sánh với dữ liệu đã lưu
  ↓
Trả về kết quả nhận diện
  ↓
Lưu lịch sử chấm công
```

---

## API chính

| Method | Endpoint                | Mô tả                         |
| ------ | ----------------------- | ----------------------------- |
| GET    | `/`                     | Trang chính                   |
| GET    | `/employees`            | Trang quản lý nhân viên       |
| GET    | `/history`              | Trang lịch sử chấm công       |
| GET    | `/api/employees`        | Lấy danh sách nhân viên       |
| POST   | `/api/employees`        | Thêm nhân viên                |
| DELETE | `/api/employees/<id>`   | Xoá nhân viên                 |
| POST   | `/api/capture_face`     | Lưu ảnh khuôn mặt             |
| POST   | `/api/recognize_webcam` | Nhận diện khuôn mặt           |
| GET    | `/api/history`          | Lấy lịch sử chấm công         |
| POST   | `/api/shifts`           | Thêm ca làm việc              |
| GET    | `/api/shifts/<id>`      | Lấy ca làm việc của nhân viên |

---

## Database

Project sử dụng SQLite để lưu dữ liệu.

Các bảng chính:

* `employees`: lưu thông tin nhân viên
* `face_images`: lưu đường dẫn ảnh khuôn mặt
* `embeddings`: lưu vector khuôn mặt
* `attendance_log`: lưu lịch sử chấm công
* `shifts`: lưu thông tin ca làm việc

---

## Ghi chú

* Nên chụp ảnh khuôn mặt rõ, đủ sáng để nhận diện tốt hơn.
* Nếu nhận diện chưa ổn định, nên chụp lại dữ liệu khuôn mặt.
* Kết quả nhận diện có thể bị ảnh hưởng bởi ánh sáng, góc mặt, chất lượng webcam.
* Phần liveness detection hiện tại còn cơ bản, có thể cải thiện thêm trong tương lai.
* Project phù hợp để học tập, làm portfolio và trình bày kỹ năng về Python, Flask và Computer Vision.

---

## Hướng phát triển

* Thêm chức năng đăng nhập cho admin
* Cải thiện giao diện web
* Xuất lịch sử chấm công ra Excel / CSV
* Cải thiện chống giả mạo bằng ảnh hoặc video
* Thêm thống kê chấm công theo ngày / tháng
* Tối ưu tốc độ nhận diện khuôn mặt

