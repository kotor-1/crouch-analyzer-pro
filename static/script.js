// グローバル変数
let currentKeypoints = {};
let selectedJoint = null;
let imageLoaded = false;
let canvas = null;
let ctx = null;
let img = null;
let adjustmentMode = 'click';
let angleChart = null;

// 関節点の日本語名マッピング（正しい順序で定義）
const jointNames = {
    'LShoulder': '① 左肩',
    'RShoulder': '② 右肩',
    'LHip': '③ 左股関節',
    'RHip': '④ 右股関節',
    'LKnee': '⑤ 左膝',
    'RKnee': '⑥ 右膝',
    'LAnkle': '⑦ 左足首',
    'RAnkle': '⑧ 右足首',
    'C7': '⑨ 第7頸椎'
};

// 関節点の表示順序を固定
const jointOrder = ['LShoulder', 'RShoulder', 'LHip', 'RHip', 'LKnee', 'RKnee', 'LAnkle', 'RAnkle', 'C7'];

// DOM読み込み後に実行
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    canvas = document.getElementById('imageCanvas');
    ctx = canvas.getContext('2d');
    
    // イベントリスナーの設定
    setupDropArea();
    document.getElementById('imageUpload').addEventListener('change', handleImageUpload);
    document.getElementById('adjustmentMode').addEventListener('change', handleModeChange);
    document.getElementById('analyzeBtn').addEventListener('click', analyzePosture);
    document.getElementById('downloadBtn').addEventListener('click', downloadResults);
    
    // キャンバスクリックイベント
    canvas.addEventListener('click', handleCanvasClick);
    
    // 方向キーのイベントリスナー
    document.getElementById('moveUp').addEventListener('click', () => moveJoint(0, -getMovementStep()));
    document.getElementById('moveDown').addEventListener('click', () => moveJoint(0, getMovementStep()));
    document.getElementById('moveLeft').addEventListener('click', () => moveJoint(-getMovementStep(), 0));
    document.getElementById('moveRight').addEventListener('click', () => moveJoint(getMovementStep(), 0));
    
    // 数値入力のイベントリスナー
    document.getElementById('xCoord').addEventListener('input', handleNumericAdjustment);
    document.getElementById('yCoord').addEventListener('input', handleNumericAdjustment);
    
    console.log('アプリケーションが初期化されました');
}

function setupDropArea() {
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('imageUpload');
    
    // ドロップエリアクリックでファイル選択
    dropArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // ドラッグ&ドロップイベント
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    dropArea.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    document.getElementById('dropArea').classList.add('dragover');
}

function unhighlight(e) {
    document.getElementById('dropArea').classList.remove('dragover');
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    if (files.length > 0) {
        handleFileUpload(files[0]);
    }
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    handleFileUpload(file);
}

function handleFileUpload(file) {
    if (!file.type.startsWith('image/')) {
        showError('❌ 画像ファイルを選択してください');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // ローディング表示
    showLoading('画像をアップロード中...');
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        
        if (data.success) {
            currentKeypoints = data.keypoints;
            loadImageToCanvas(data.image_url, data.image_width, data.image_height);
            createJointButtons();
            updateModeDisplay();
            document.getElementById('analyzeBtn').disabled = false;
            showSuccess('✅ 画像アップロード完了！手動調整で正確分析できます');
        } else {
            showError('❌ ' + data.error);
        }
    })
    .catch(error => {
        hideLoading();
        showError('❌ アップロードエラー: ' + error.message);
    });
}

function loadImageToCanvas(imageUrl, width, height) {
    img = new Image();
    img.onload = function() {
        // キャンバスサイズを画像に合わせて調整
        const maxWidth = 800;
        const maxHeight = 600;
        
        let canvasWidth = width;
        let canvasHeight = height;
        
        if (width > maxWidth) {
            canvasWidth = maxWidth;
            canvasHeight = (height * maxWidth) / width;
        }
        
        if (canvasHeight > maxHeight) {
            canvasWidth = (canvasWidth * maxHeight) / canvasHeight;
            canvasHeight = maxHeight;
        }
        
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
        canvas.style.display = 'block';
        
        // 関節点座標をキャンバスサイズに合わせてスケール
        const scaleX = canvasWidth / width;
        const scaleY = canvasHeight / height;
        
        for (let joint in currentKeypoints) {
            currentKeypoints[joint].x *= scaleX;
            currentKeypoints[joint].y *= scaleY;
        }
        
        imageLoaded = true;
        drawCanvas();
        
        document.getElementById('imageContainer').innerHTML = '';
        document.getElementById('imageContainer').appendChild(canvas);
    };
    
    img.src = imageUrl;
}

function drawCanvas() {
    if (!imageLoaded || !img) return;
    
    // キャンバスをクリア
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 画像を描画
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    // 骨格線を描画
    drawSkeleton();
    
    // 関節点を描画
    drawJoints();
}

function drawSkeleton() {
    const lines = [
        ['LShoulder', 'LHip'],
        ['LHip', 'LKnee'],
        ['LKnee', 'LAnkle'],
        ['RShoulder', 'RHip'],
        ['RHip', 'RKnee'],
        ['RKnee', 'RAnkle'],
        ['LShoulder', 'RShoulder'],
        ['LHip', 'RHip'],
    ];
    
    // C7から骨盤への線
    if (currentKeypoints['C7'] && currentKeypoints['RHip'] && currentKeypoints['LHip']) {
        const pelvisJoint = currentKeypoints['RAnkle'].x > currentKeypoints['LAnkle'].x ? 'RHip' : 'LHip';
        lines.push(['C7', pelvisJoint]);
    }
    
    ctx.strokeStyle = '#ff0000';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    lines.forEach(([joint1, joint2]) => {
        if (currentKeypoints[joint1] && currentKeypoints[joint2]) {
            const p1 = currentKeypoints[joint1];
            const p2 = currentKeypoints[joint2];
            
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
        }
    });
    
    ctx.stroke();
}

function drawJoints() {
    // 固定された順序で関節点を描画
    jointOrder.forEach((jointName, index) => {
        if (currentKeypoints[jointName]) {
            const point = currentKeypoints[jointName];
            const isSelected = jointName === selectedJoint;
            
            // 外側の円
            ctx.beginPath();
            ctx.arc(point.x, point.y, isSelected ? 12 : 8, 0, 2 * Math.PI);
            ctx.fillStyle = isSelected ? '#00ff00' : '#ffff00';
            ctx.fill();
            ctx.strokeStyle = '#ff0000';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // 正しい番号を描画（1から始まる）
            ctx.fillStyle = '#000000';
            ctx.font = 'bold 12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(
                (index + 1).toString(), // 1から始まる番号
                point.x,
                point.y + 4
            );
        }
    });
}

function handleCanvasClick(event) {
    if (!imageLoaded || !selectedJoint || adjustmentMode !== 'click') return;
    
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    // 選択中の関節点を新しい位置に移動
    currentKeypoints[selectedJoint] = { x: x, y: y };
    
    // キャンバスを再描画
    drawCanvas();
    
    // 数値入力フィールドを更新
    updateNumericInputs();
    
    // 自動分析
    if (document.getElementById('analyzeBtn').disabled === false) {
        analyzePosture();
    }
    
    showSuccess(`✅ ${jointNames[selectedJoint]}を移動しました`);
}

function handleModeChange() {
    adjustmentMode = document.getElementById('adjustmentMode').value;
    updateModeDisplay();
}

function updateModeDisplay() {
    // 全ての調整コントロールを隠す
    document.getElementById('directionControls').style.display = 'none';
    document.getElementById('dropdownSelection').style.display = 'none';
    document.getElementById('numericAdjustment').style.display = 'none';
    document.getElementById('batchAdjustment').style.display = 'none';
    document.getElementById('jointButtonsContainer').style.display = 'none';
    
    // モードに応じて表示
    switch (adjustmentMode) {
        case 'click':
            document.getElementById('jointButtonsContainer').style.display = 'block';
            document.getElementById('numericAdjustment').style.display = 'block';
            canvas.style.cursor = selectedJoint ? 'crosshair' : 'default';
            break;
            
        case 'direction':
            document.getElementById('jointButtonsContainer').style.display = 'block';
            document.getElementById('directionControls').style.display = 'block';
            document.getElementById('numericAdjustment').style.display = 'block';
            canvas.style.cursor = 'default';
            break;
            
        case 'dropdown':
            document.getElementById('dropdownSelection').style.display = 'block';
            document.getElementById('numericAdjustment').style.display = 'block';
            createJointDropdown();
            canvas.style.cursor = 'default';
            break;
            
        case 'batch':
            document.getElementById('batchAdjustment').style.display = 'block';
            createBatchControls();
            canvas.style.cursor = 'default';
            break;
    }
}

function createJointButtons() {
    const container = document.getElementById('jointButtons');
    container.innerHTML = '';
    
    // 固定された順序でボタンを作成
    jointOrder.forEach(jointName => {
        if (currentKeypoints[jointName]) {
            const button = document.createElement('button');
            button.className = 'btn btn-outline-primary joint-button';
            button.textContent = jointNames[jointName];
            button.onclick = () => selectJoint(jointName);
            button.setAttribute('data-joint', jointName);
            container.appendChild(button);
        }
    });
}

function createJointDropdown() {
    const dropdown = document.getElementById('jointDropdown');
    dropdown.innerHTML = '';
    
    // 固定された順序でオプションを作成
    jointOrder.forEach(jointName => {
        if (currentKeypoints[jointName]) {
            const option = document.createElement('option');
            option.value = jointName;
            option.textContent = jointNames[jointName];
            dropdown.appendChild(option);
        }
    });
    
    dropdown.addEventListener('change', function() {
        selectJoint(this.value);
    });
}

function createBatchControls() {
    const container = document.getElementById('batchControls');
    container.innerHTML = '';
    
    // 固定された順序で一括調整コントロールを作成
    jointOrder.forEach(jointName => {
        if (currentKeypoints[jointName]) {
            const div = document.createElement('div');
            div.className = 'mb-2';
            div.innerHTML = `
                <label class="form-label">${jointNames[jointName]}</label>
                <div class="row">
                    <div class="col-6">
                        <input type="number" class="form-control" 
                               value="${Math.round(currentKeypoints[jointName].x)}" 
                               onchange="updateJointFromBatch('${jointName}', 'x', this.value)">
                    </div>
                    <div class="col-6">
                        <input type="number" class="form-control" 
                               value="${Math.round(currentKeypoints[jointName].y)}" 
                               onchange="updateJointFromBatch('${jointName}', 'y', this.value)">
                    </div>
                </div>
            `;
            container.appendChild(div);
        }
    });
}

function selectJoint(jointName) {
    selectedJoint = jointName;
    
    // ボタンの選択状態を更新
    document.querySelectorAll('.joint-button').forEach(btn => {
        btn.classList.remove('selected');
        if (btn.getAttribute('data-joint') === jointName) {
            btn.classList.add('selected');
        }
    });
    
    // 選択情報を更新
    document.getElementById('selectedJointInfo').innerHTML = 
        `🎯 選択中: <strong>${jointNames[jointName]}</strong>`;
    
    // 数値入力を更新
    updateNumericInputs();
    
    // キャンバスを再描画
    drawCanvas();
    
    // カーソルを更新
    if (adjustmentMode === 'click') {
        canvas.style.cursor = 'crosshair';
    }
}

function updateNumericInputs() {
    if (!selectedJoint || !currentKeypoints[selectedJoint]) return;
    
    document.getElementById('xCoord').value = Math.round(currentKeypoints[selectedJoint].x);
    document.getElementById('yCoord').value = Math.round(currentKeypoints[selectedJoint].y);
}

function handleNumericAdjustment() {
    if (!selectedJoint) return;
    
    const x = parseInt(document.getElementById('xCoord').value);
    const y = parseInt(document.getElementById('yCoord').value);
    
    if (!isNaN(x) && !isNaN(y)) {
        currentKeypoints[selectedJoint] = { x: x, y: y };
        drawCanvas();
        
        // 自動分析
        if (document.getElementById('analyzeBtn').disabled === false) {
            analyzePosture();
        }
    }
}

function moveJoint(dx, dy) {
    if (!selectedJoint) {
        showError('❌ 関節点を選択してください');
        return;
    }
    
    const current = currentKeypoints[selectedJoint];
    const newX = Math.max(0, Math.min(canvas.width, current.x + dx));
    const newY = Math.max(0, Math.min(canvas.height, current.y + dy));
    
    currentKeypoints[selectedJoint] = { x: newX, y: newY };
    
    drawCanvas();
    updateNumericInputs();
    
    // 自動分析
    if (document.getElementById('analyzeBtn').disabled === false) {
        analyzePosture();
    }
}

function getMovementStep() {
    return parseInt(document.getElementById('moveStep').value);
}

function updateJointFromBatch(jointName, coord, value) {
    const numValue = parseInt(value);
    if (!isNaN(numValue)) {
        currentKeypoints[jointName][coord] = numValue;
        drawCanvas();
        
        // 自動分析
        if (document.getElementById('analyzeBtn').disabled === false) {
            analyzePosture();
        }
    }
}

function analyzePosture() {
    if (!imageLoaded || Object.keys(currentKeypoints).length === 0) return;
    
    const analysisMode = document.getElementById('analysisMode').value;
    
    fetch('/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            keypoints: currentKeypoints,
            analysis_mode: analysisMode
        })
    })
    .then(response => response.json())
    .then(data => {
        displayAnalysisResults(data);
        createAngleChart(data);
        document.getElementById('downloadBtn').style.display = 'block';
    })
    .catch(error => {
        showError('❌ 分析エラー: ' + error.message);
    });
}

function displayAnalysisResults(data) {
    const container = document.getElementById('analysisResults');
    
    if (data.error) {
        container.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
        return;
    }
    
    let html = '<h6>📊 分析結果</h6>';
    
    if (data.analysis_type === 'set') {
        if (data.front_angle !== undefined) {
            html += createMetricCard('前足の膝角度', data.front_angle, '°', 80, 100);
        }
        if (data.rear_angle !== undefined) {
            html += createMetricCard('後足の膝角度', data.rear_angle, '°', 120, 135);
        }
        if (data.front_hip_angle !== undefined) {
            html += createMetricCard('前足股関節角度', data.front_hip_angle, '°', 40, 60);
        }
    } else if (data.analysis_type === 'takeoff') {
        if (data.lower_angle !== undefined) {
            html += createMetricCard('下半身角度', data.lower_angle, '°', 30, 60);
        }
        if (data.upper_angle !== undefined) {
            html += createMetricCard('上半身角度', data.upper_angle, '°', 25, 55);
        }
        if (data.kunoji_angle !== undefined) {
            html += createMetricCard('くの字角度', data.kunoji_angle, '°', 150, 180);
        }
    }
    
    container.innerHTML = html;
}

function createAngleChart(data) {
    const ctx = document.getElementById('angleChart').getContext('2d');
    
    // 既存のチャートを破棄
    if (angleChart) {
        angleChart.destroy();
    }
    
    const labels = [];
    const angles = [];
    const idealMin = [];
    const idealMax = [];
    
    if (data.analysis_type === 'set') {
        if (data.front_angle !== undefined) {
            labels.push('前足膝');
            angles.push(data.front_angle);
            idealMin.push(80);
            idealMax.push(100);
        }
        if (data.rear_angle !== undefined) {
            labels.push('後足膝');
            angles.push(data.rear_angle);
            idealMin.push(120);
            idealMax.push(135);
        }
        if (data.front_hip_angle !== undefined) {
            labels.push('前足股関節');
            angles.push(data.front_hip_angle);
            idealMin.push(40);
            idealMax.push(60);
        }
    } else if (data.analysis_type === 'takeoff') {
        if (data.lower_angle !== undefined) {
            labels.push('下半身');
            angles.push(data.lower_angle);
            idealMin.push(30);
            idealMax.push(60);
        }
        if (data.upper_angle !== undefined) {
            labels.push('上半身');
            angles.push(data.upper_angle);
            idealMin.push(25);
            idealMax.push(55);
        }
        if (data.kunoji_angle !== undefined) {
            labels.push('くの字');
            angles.push(data.kunoji_angle);
            idealMin.push(150);
            idealMax.push(180);
        }
    }
    
    angleChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '測定値',
                    data: angles,
                    backgroundColor: 'rgba(102, 126, 234, 0.6)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 2
                },
                {
                    label: '理想範囲(最小)',
                    data: idealMin,
                    backgroundColor: 'rgba(40, 167, 69, 0.3)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1,
                    type: 'line'
                },
                {
                    label: '理想範囲(最大)',
                    data: idealMax,
                    backgroundColor: 'rgba(40, 167, 69, 0.3)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1,
                    type: 'line'
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '角度 (度)'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: '角度分析グラフ'
                }
            }
        }
    });
    
    document.getElementById('chartCard').style.display = 'block';
}

function downloadResults() {
    // 結果画像を生成してダウンロード
    const canvas = document.getElementById('imageCanvas');
    const link = document.createElement('a');
    link.download = 'crouch_analysis_result.png';
    link.href = canvas.toDataURL();
    link.click();
    
    showSuccess('✅ 結果画像をダウンロードしました');
}

function createMetricCard(label, value, unit, minGood, maxGood) {
    if (value === null || value === undefined) {
        return `
            <div class="metric-card">
                <div class="metric-label">${label}</div>
                <div class="metric-value">測定不可</div>
            </div>
        `;
    }
    
    let status = 'status-warning';
    let statusText = '要確認';
    
    if (value >= minGood && value <= maxGood) {
        status = 'status-success';
        statusText = '理想的';
    } else {
        status = 'status-error';
        statusText = '要改善';
    }
    
    return `
        <div class="metric-card ${status}">
            <div class="metric-label">${label}</div>
            <div class="metric-value">${value.toFixed(1)}${unit}</div>
            <small class="text-muted">${statusText}</small>
        </div>
    `;
}

// ユーティリティ関数
function showLoading(message) {
    const container = document.getElementById('imageContainer');
    container.innerHTML = `
        <div class="text-center">
            <div class="loading"></div>
            <p class="mt-2">${message}</p>
        </div>
    `;
}

function hideLoading() {
    // ローディングは画像読み込み時に自動的に隠れる
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'danger');
}

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed fade-in`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
    toast.innerHTML = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}