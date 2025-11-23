// Face Attendance System - Frontend JavaScript
// Professional CV Engineer Implementation

// Global state
let videoStream = null;
let isWebcamActive = false;
let enrollEmployeeId = null;
let enrollCount = 0;
const ENROLL_TARGET = 10;

// DOM Elements
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    await loadEmployees();
    await loadHistory();
    await updateStats();
    setupEventListeners();
    
    // Auto refresh every 30 seconds
    setInterval(() => {
        loadHistory();
        updateStats();
    }, 30000);
}

// ============ Event Listeners ============

function setupEventListeners() {
    // Upload form
    document.getElementById('form-upload').addEventListener('submit', handleUploadSubmit);
    
    // Webcam controls
    document.getElementById('btn-start-webcam').addEventListener('click', toggleWebcam);
    document.getElementById('btn-capture').addEventListener('click', captureAndRecognize);
    
    // Employee management
    document.getElementById('form-add-employee').addEventListener('submit', handleAddEmployee);
    document.getElementById('enroll-employee-select').addEventListener('change', handleEnrollSelectChange);
    document.getElementById('btn-enroll-capture').addEventListener('click', startEnrollCapture);
    document.getElementById('btn-retrain-model').addEventListener('click', retrainModel);
}

// ============ Upload Recognition ============

async function handleUploadSubmit(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('input-image');
    const file = fileInput.files[0];
    
    if (!file) {
        showMessage('upload-result', 'Vui lòng chọn ảnh!', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('image', file);
    
    showMessage('upload-result', '⏳ Đang nhận diện...', 'info');
    
    try {
        const response = await fetch('/api/recognize_upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayRecognitionResult('upload-result', data);
            await loadHistory();
            await updateStats();
        } else {
            showMessage('upload-result', `❌ ${data.message}`, 'error');
        }
    } catch (error) {
        showMessage('upload-result', `❌ Lỗi: ${error.message}`, 'error');
    }
    
    fileInput.value = '';
}

// ============ Webcam ============

// Check if we're on localhost (required for webcam)
function isLocalhost() {
    const hostname = window.location.hostname;
    return hostname === 'localhost' || 
           hostname === '127.0.0.1' || 
           hostname === '[::1]' ||
           hostname.startsWith('127.') ||
           window.location.protocol === 'https:';
}

// Check browser support for getUserMedia
function checkWebcamSupport() {
    // Check if we're on localhost or HTTPS
    if (!isLocalhost()) {
        return 'not_localhost';
    }
    
    // Modern API
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        return 'modern';
    }
    // Legacy API
    if (navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia) {
        return 'legacy';
    }
    return false;
}

// Get user media with fallback
function getUserMedia(constraints) {
    const support = checkWebcamSupport();
    
    if (support === 'modern') {
        return navigator.mediaDevices.getUserMedia(constraints);
    } else if (support === 'legacy') {
        // Legacy API wrapper
        const getUserMedia = navigator.getUserMedia || 
                            navigator.webkitGetUserMedia || 
                            navigator.mozGetUserMedia || 
                            navigator.msGetUserMedia;
        
        return new Promise((resolve, reject) => {
            getUserMedia.call(navigator, constraints, resolve, reject);
        });
    } else {
        return Promise.reject(new Error('Trình duyệt không hỗ trợ webcam. Vui lòng dùng Chrome, Firefox, Edge hoặc Safari mới nhất.'));
    }
}

async function toggleWebcam() {
    const btn = document.getElementById('btn-start-webcam');
    const captureBtn = document.getElementById('btn-capture');
    
    if (!isWebcamActive) {
        // Check support first
        const support = checkWebcamSupport();
        
        if (support === 'not_localhost') {
            const currentUrl = window.location.href;
            const localhostUrl = currentUrl.replace(window.location.hostname, 'localhost');
            showMessage('webcam-result', 
                '❌ Webcam chỉ hoạt động với localhost hoặc HTTPS!\n\n' +
                `Bạn đang truy cập: ${window.location.hostname}\n\n` +
                `👉 Vui lòng truy cập qua:\n` +
                `   ${localhostUrl}\n\n` +
                `Hoặc dùng Upload ảnh (không cần webcam)`, 
                'error'
            );
            return;
        }
        
        if (!support) {
            showMessage('webcam-result', 
                '❌ Trình duyệt không hỗ trợ webcam!\n' +
                'Vui lòng:\n' +
                '1. Dùng Chrome, Firefox, Edge hoặc Safari mới nhất\n' +
                '2. Truy cập qua HTTPS hoặc localhost\n' +
                '3. Cho phép quyền truy cập camera', 
                'error'
            );
            return;
        }
        
        try {
            videoStream = await getUserMedia({
                video: { 
                    width: { ideal: 640 }, 
                    height: { ideal: 480 },
                    facingMode: 'user'  // Front camera
                }
            });
            
            video.srcObject = videoStream;
            isWebcamActive = true;
            btn.textContent = '🛑 Tắt Webcam';
            captureBtn.disabled = false;
            showMessage('webcam-result', '✅ Webcam đã bật!', 'success');
        } catch (error) {
            let errorMsg = '❌ Không thể bật webcam: ';
            
            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                errorMsg += 'Bạn đã từ chối quyền truy cập camera. Vui lòng cho phép trong cài đặt trình duyệt.';
            } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                errorMsg += 'Không tìm thấy camera. Vui lòng kiểm tra camera đã được kết nối.';
            } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                errorMsg += 'Camera đang được sử dụng bởi ứng dụng khác.';
            } else if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') {
                errorMsg += 'Camera không hỗ trợ yêu cầu.';
            } else if (error.message) {
                errorMsg += error.message;
            } else {
                errorMsg += 'Lỗi không xác định. Vui lòng thử lại.';
            }
            
            showMessage('webcam-result', errorMsg, 'error');
            console.error('Webcam error:', error);
        }
    } else {
        stopWebcam();
        btn.textContent = '🎥 Bật Webcam';
        captureBtn.disabled = true;
    }
}

function stopWebcam() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
        videoStream = null;
        isWebcamActive = false;
    }
}

async function captureAndRecognize() {
    if (!isWebcamActive) return;
    
    const imageData = captureFrame();
    showMessage('webcam-result', '⏳ Đang nhận diện...', 'info');
    
    try {
        const response = await fetch('/api/recognize_webcam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayRecognitionResult('webcam-result', data);
            await loadHistory();
            await updateStats();
        } else {
            showMessage('webcam-result', `❌ ${data.message}`, 'error');
        }
    } catch (error) {
        showMessage('webcam-result', `❌ Lỗi: ${error.message}`, 'error');
    }
}

function captureFrame() {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);
    return canvas.toDataURL('image/jpeg');
}

// ============ Employee Management ============

async function loadEmployees() {
    try {
        const response = await fetch('/api/employees');
        const data = await response.json();
        
        if (data.success) {
            renderEmployeeTable(data.data);
            populateEnrollSelect(data.data.filter(e => e.active));
            updateStats();
        }
    } catch (error) {
        console.error('Error loading employees:', error);
    }
}

function renderEmployeeTable(employees) {
    const tbody = document.getElementById('employees-table-body');
    
    if (employees.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--color-text-muted); padding: 2rem;">
                    Chưa có nhân viên nào
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = employees.map(emp => `
        <tr>
            <td><strong>${escapeHtml(emp.code)}</strong></td>
            <td>${escapeHtml(emp.name)}</td>
            <td>${escapeHtml(emp.gender || '-')}</td>
            <td>
                <span class="badge ${emp.active ? 'badge-active' : 'badge-inactive'}">
                    <span class="status-dot ${emp.active ? 'active' : 'inactive'}"></span>
                    ${emp.active ? 'Hoạt động' : 'Vô hiệu'}
                </span>
            </td>
            <td>
                ${emp.active ? 
                    `<button class="btn-icon" onclick="deactivateEmployee(${emp.id})">🗑️ Xóa</button>` : 
                    '<span style="color: var(--color-text-muted);">-</span>'
                }
            </td>
        </tr>
    `).join('');
}

function populateEnrollSelect(activeEmployees) {
    const select = document.getElementById('enroll-employee-select');
    select.innerHTML = '<option value="">-- Chọn nhân viên để enroll --</option>' +
        activeEmployees.map(emp => 
            `<option value="${emp.id}">${emp.code} - ${escapeHtml(emp.name)}</option>`
        ).join('');
}

async function handleAddEmployee(e) {
    e.preventDefault();
    
    const code = document.getElementById('emp-code').value.trim();
    const name = document.getElementById('emp-name').value.trim();
    const gender = document.getElementById('emp-gender').value.trim();
    
    if (!code || !name) {
        showMessage('employee-form-result', 'Vui lòng nhập đầy đủ mã và tên!', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/employees', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, name, gender: gender || null })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage('employee-form-result', `✅ Đã thêm nhân viên: ${name}`, 'success');
            document.getElementById('form-add-employee').reset();
            await loadEmployees();
        } else {
            showMessage('employee-form-result', `❌ ${data.message}`, 'error');
        }
    } catch (error) {
        showMessage('employee-form-result', `❌ Lỗi: ${error.message}`, 'error');
    }
}

async function deactivateEmployee(employeeId) {
    if (!confirm('Bạn có chắc muốn vô hiệu hóa nhân viên này?')) return;
    
    try {
        const response = await fetch(`/api/employees/${employeeId}/deactivate`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage('employee-form-result', '✅ Đã vô hiệu hóa nhân viên', 'success');
            await loadEmployees();
        } else {
            showMessage('employee-form-result', `❌ ${data.message}`, 'error');
        }
    } catch (error) {
        showMessage('employee-form-result', `❌ Lỗi: ${error.message}`, 'error');
    }
}

// ============ Enrollment ============

function handleEnrollSelectChange(e) {
    const employeeId = e.target.value;
    const btn = document.getElementById('btn-enroll-capture');
    
    if (employeeId) {
        enrollEmployeeId = parseInt(employeeId);
        btn.disabled = !isWebcamActive;
    } else {
        enrollEmployeeId = null;
        btn.disabled = true;
    }
}

async function startEnrollCapture() {
    if (!enrollEmployeeId || !isWebcamActive) {
        showMessage('enroll-result', 'Vui lòng chọn nhân viên và bật webcam!', 'error');
        return;
    }
    
    enrollCount = 0;
    document.getElementById('enroll-progress').classList.add('show');
    document.getElementById('btn-enroll-capture').disabled = true;
    showMessage('enroll-result', '📸 Đang thu thập ảnh... Giữ khuôn mặt ổn định!', 'info');
    
    // Capture 10 images with 500ms interval
    for (let i = 0; i < ENROLL_TARGET; i++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        await captureEnrollImage();
        
        if (enrollCount !== i + 1) {
            // Error occurred
            break;
        }
    }
    
    if (enrollCount === ENROLL_TARGET) {
        showMessage('enroll-result', `✅ Hoàn thành! Đã thu thập ${ENROLL_TARGET} ảnh. Hãy train lại model!`, 'success');
    }
    
    document.getElementById('btn-enroll-capture').disabled = false;
}

async function captureEnrollImage() {
    const imageData = captureFrame();
    
    try {
        const response = await fetch(`/api/employees/${enrollEmployeeId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        
        const data = await response.json();
        
        if (data.success) {
            enrollCount++;
            updateEnrollProgress();
        } else {
            showMessage('enroll-result', `❌ ${data.message}`, 'error');
            document.getElementById('enroll-progress').classList.remove('show');
        }
    } catch (error) {
        showMessage('enroll-result', `❌ Lỗi: ${error.message}`, 'error');
        document.getElementById('enroll-progress').classList.remove('show');
    }
}

function updateEnrollProgress() {
    const percent = (enrollCount / ENROLL_TARGET) * 100;
    document.getElementById('progress-fill').style.width = `${percent}%`;
    document.getElementById('progress-text').textContent = `${enrollCount} / ${ENROLL_TARGET} ảnh`;
}

async function retrainModel() {
    const btn = document.getElementById('btn-retrain-model');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Đang train...';
    showMessage('enroll-result', '⏳ Đang train model... Vui lòng đợi (có thể mất 30s-1p)', 'info');
    
    try {
        const response = await fetch('/api/retrain_model', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            const metrics = data.metrics;
            showMessage('enroll-result', 
                `✅ Train thành công! Nhân viên: ${metrics.n_employees}, Ảnh: ${metrics.n_images}, Threshold: ${metrics.threshold.toFixed(4)}`, 
                'success'
            );
        } else {
            showMessage('enroll-result', `❌ ${data.message}`, 'error');
        }
    } catch (error) {
        showMessage('enroll-result', `❌ Lỗi: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ============ History ============

async function loadHistory() {
    try {
        const response = await fetch('/api/history_sessions');
        const data = await response.json();
        
        if (data.success) {
            renderHistory(data.data);
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function renderHistory(sessions) {
    const historyList = document.getElementById('history-list');
    
    if (!sessions || sessions.length === 0) {
        historyList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-text">Chưa có lịch sử chấm công</div>
                <div class="empty-state-subtext">Lịch sử sẽ hiển thị khi có chấm công</div>
            </div>
        `;
        return;
    }
    
    historyList.innerHTML = sessions.map(session => `
        <div class="history-item fade-in">
            <div class="history-header">
                <div>
                    <div class="history-name">📅 ${formatDate(session.date)}</div>
                </div>
                <div>
                    <span class="badge badge-in">${session.known_checks} nhận diện</span>
                    ${session.unknown_checks > 0 ? `<span class="badge badge-unknown">${session.unknown_checks} unknown</span>` : ''}
                </div>
            </div>
            <div class="history-time">
                <span style="color: var(--color-text-secondary);">Tổng: ${session.total_checks} lượt chấm công</span>
            </div>
        </div>
    `).join('');
}

// ============ Stats ============

async function updateStats() {
    try {
        const [employeesRes, historyRes] = await Promise.all([
            fetch('/api/employees'),
            fetch('/api/history_sessions?limit_days=1')
        ]);
        
        const employeesData = await employeesRes.json();
        const historyData = await historyRes.json();
        
        if (employeesData.success) {
            const activeCount = employeesData.data.filter(e => e.active).length;
            document.getElementById('stat-employees').textContent = activeCount;
        }
        
        if (historyData.success && historyData.data.length > 0) {
            const today = historyData.data[0];
            document.getElementById('stat-total').textContent = today.total_checks || 0;
            document.getElementById('stat-known').textContent = today.known_checks || 0;
            document.getElementById('stat-unknown').textContent = today.unknown_checks || 0;
        } else {
            document.getElementById('stat-total').textContent = '0';
            document.getElementById('stat-known').textContent = '0';
            document.getElementById('stat-unknown').textContent = '0';
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// ============ UI Helpers ============

function showMessage(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.className = `info-box ${type} show`;
    element.textContent = message;
    
    setTimeout(() => {
        element.classList.remove('show');
    }, 5000);
}

function displayRecognitionResult(elementId, data) {
    let message, type;
    
    if (data.is_unknown) {
        message = `⚠️ ${data.message} (Score: ${data.score.toFixed(3)})`;
        type = 'warning';
    } else {
        message = `✅ ${data.message}\n📊 Score: ${data.score.toFixed(3)}`;
        type = 'success';
    }
    
    showMessage(elementId, message, type);
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) {
        return 'Hôm nay';
    } else if (date.toDateString() === yesterday.toDateString()) {
        return 'Hôm qua';
    } else {
        return date.toLocaleDateString('vi-VN', { 
            weekday: 'short', 
            day: '2-digit', 
            month: '2-digit',
            year: 'numeric'
        });
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expose deactivateEmployee to global scope for inline onclick
window.deactivateEmployee = deactivateEmployee;
