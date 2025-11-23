# DEPLOYMENT GUIDE - Face Attendance System

## 🚀 Production Deployment Guide

### Option 1: Local Server (Development/Testing)

#### Requirements
- Python 3.10+
- SQLite 3
- Webcam (optional for enrollment)

#### Steps

1. **Clone/Extract project**
```bash
cd C:\path\to\face_attendance_project
```

2. **Setup environment**
```bash
# Option A: Conda
conda env create -f env/environment.yml
conda activate face_attendance

# Option B: pip + venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. **Initialize database**
```bash
python -c "from src.db_utils import init_db; init_db()"
```

4. **Run server**
```bash
python app/web_app.py
```

5. **Access**: http://localhost:5000

---

### Option 2: Production Server (Linux/Ubuntu)

#### 1. Install system dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv sqlite3
sudo apt install -y libopencv-dev python3-opencv
```

#### 2. Setup project
```bash
cd /opt
sudo git clone <your-repo> face_attendance
cd face_attendance
sudo chown -R www-data:www-data .
```

#### 3. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configure Gunicorn
```bash
pip install gunicorn

# Test
gunicorn --bind 0.0.0.0:8000 app.web_app:app
```

#### 5. Create systemd service
```bash
sudo nano /etc/systemd/system/face-attendance.service
```

```ini
[Unit]
Description=Face Attendance System
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/face_attendance
Environment="PATH=/opt/face_attendance/venv/bin"
ExecStart=/opt/face_attendance/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --log-level info \
    --access-logfile /var/log/face_attendance/access.log \
    --error-logfile /var/log/face_attendance/error.log \
    app.web_app:app

[Install]
WantedBy=multi-user.target
```

#### 6. Start service
```bash
sudo mkdir -p /var/log/face_attendance
sudo chown www-data:www-data /var/log/face_attendance
sudo systemctl daemon-reload
sudo systemctl enable face-attendance
sudo systemctl start face-attendance
sudo systemctl status face-attendance
```

---

### Option 3: Nginx Reverse Proxy

#### 1. Install Nginx
```bash
sudo apt install nginx
```

#### 2. Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/face-attendance
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /static {
        alias /opt/face_attendance/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

#### 3. Enable site
```bash
sudo ln -s /etc/nginx/sites-available/face-attendance /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 4. SSL with Let's Encrypt (Optional but Recommended)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

### Option 4: Docker Deployment

#### 1. Create Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p data/employees_faces models logs

# Expose port
EXPOSE 5000

# Run app
CMD ["python", "app/web_app.py"]
```

#### 2. Create docker-compose.yml
```yaml
version: '3.8'

services:
  face-attendance:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
```

#### 3. Build and run
```bash
docker-compose up -d
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` file:
```bash
# Flask
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=your-secret-key-here

# Database
DATABASE_PATH=data/attendance.db

# Model
MODEL_PATH=models/face_recognizer_from_db.joblib
PCA_COMPONENTS=100
ENROLL_IMAGES=10

# Server
HOST=0.0.0.0
PORT=5000
WORKERS=4
```

### Security Recommendations

1. **Change default ports**
2. **Enable HTTPS** (SSL/TLS)
3. **Use strong SECRET_KEY**
4. **Implement authentication** (if multi-user)
5. **Regular backups** of database
6. **Monitor logs** for suspicious activity
7. **Update dependencies** regularly

---

## 📊 Monitoring

### Logs Location
- Application: `/var/log/face_attendance/`
- Nginx: `/var/log/nginx/`
- Systemd: `journalctl -u face-attendance -f`

### Health Check Endpoint
Add to `web_app.py`:
```python
@app.route("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "database": os.path.exists(DB_PATH),
        "model": recognizer is not None
    })
```

### Monitoring Script
```bash
#!/bin/bash
# check_health.sh

RESPONSE=$(curl -s http://localhost:5000/health)
STATUS=$(echo $RESPONSE | jq -r '.status')

if [ "$STATUS" != "ok" ]; then
    echo "Service down! Restarting..."
    sudo systemctl restart face-attendance
    # Send alert (email, SMS, etc.)
fi
```

Add to crontab:
```bash
*/5 * * * * /opt/face_attendance/check_health.sh
```

---

## 🔄 Backup & Restore

### Automated Backup Script
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/face_attendance"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
sqlite3 data/attendance.db ".backup '$BACKUP_DIR/attendance_$DATE.db'"

# Backup employee images
tar -czf $BACKUP_DIR/images_$DATE.tar.gz data/employees_faces/

# Backup models
cp models/face_recognizer_from_db.joblib $BACKUP_DIR/model_$DATE.joblib

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

Add to crontab (daily at 2 AM):
```bash
0 2 * * * /opt/face_attendance/backup.sh
```

### Restore
```bash
# Restore database
cp /backup/face_attendance/attendance_YYYYMMDD_HHMMSS.db data/attendance.db

# Restore images
tar -xzf /backup/face_attendance/images_YYYYMMDD_HHMMSS.tar.gz -C data/

# Restore model
cp /backup/face_attendance/model_YYYYMMDD_HHMMSS.joblib models/face_recognizer_from_db.joblib

# Restart service
sudo systemctl restart face-attendance
```

---

## 🔍 Troubleshooting

### Issue: Permission denied on database
```bash
sudo chown www-data:www-data data/attendance.db
sudo chmod 664 data/attendance.db
```

### Issue: Model not loading
```bash
# Check file exists
ls -lh models/face_recognizer_from_db.joblib

# Check permissions
sudo chown www-data:www-data models/face_recognizer_from_db.joblib

# Retrain if corrupted
python -c "from src.train_from_db import train_and_save_model_from_db; train_and_save_model_from_db()"
```

### Issue: High memory usage
```bash
# Monitor
htop

# Reduce PCA components in config (100 → 50)
# Reduce Gunicorn workers (4 → 2)
```

### Issue: Slow recognition
```bash
# Check CPU usage
# Consider upgrading hardware
# Reduce image quality/size
# Optimize database indexes
```

---

## 📈 Scaling

### Horizontal Scaling
1. Use external database (PostgreSQL instead of SQLite)
2. Shared file storage (NFS, S3) for images
3. Load balancer (Nginx, HAProxy)
4. Multiple Gunicorn instances

### Vertical Scaling
1. More CPU cores → More workers
2. More RAM → Higher PCA components
3. SSD storage → Faster I/O

---

## 🛡️ Security Hardening

1. **Firewall**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

2. **Fail2ban** (against brute force)
```bash
sudo apt install fail2ban
```

3. **Regular updates**
```bash
sudo apt update && sudo apt upgrade
pip install --upgrade -r requirements.txt
```

4. **Database encryption** (if sensitive data)

5. **HTTPS only** (no HTTP)

---

**Production Ready! 🎉**

