document.addEventListener('DOMContentLoaded', function() {
    // DOM要素への参照
    const fileInput = document.getElementById('file-input');
    const uploadArea = document.getElementById('upload-area');
    const canvasContainer = document.getElementById('canvas-container');
    const uploadedImage = document.getElementById('uploaded-image');
    const uploadStatus = document.getElementById('upload-status');
    const jointButtons = document.querySelectorAll('.joint-btn');
    const selectedJointInfo = document.getElementById('selected-joint-info');
    const arrowBtns = document.querySelectorAll('.arrow-btn');
    const analyzeSetBtn = document.getElementById('analyze-set-btn');
    const analyzeTakeoffBtn = document.getElementById('analyze-takeoff-btn');
    const analysisPanel = document.getElementById('analysis-panel');
    const angleResults = document.getElementById('angle-results');
    const shareBtn = document.getElementById('share-btn');
    const downloadBtn = document.getElementById('download-btn');
    const loading = document.getElementById('loading');
    const notification = document.getElementById('notification');

    // 状態変数
    let keypoints = {};
    let selectedJoint = null;
    let uploadedImageUrl = null;
    let imageWidth = 0;
    let imageHeight = 0;
    let isDragging = false;

    // 関節点名のマッピング
    const jointLabels = {
        'LShoulder': '① 左肩',
        'RShoulder': '② 右肩',
        'C7': '③ C7',
        'LHip': '④ 左腰',
        'RHip': '⑤ 右腰',
        'LKnee': '⑥ 左膝',
        'RKnee': '⑦ 右膝',
        'LAnkle': '⑧ 左足首',
        'RAnkle': '⑨ 右足首'
    };

    // 関節点の数字マッピング
    const jointNumbers = {
        'LShoulder': '①',
        'RShoulder': '②',
        'C7': '③',
        'LHip': '④',
        'RHip': '⑤',
        'LKnee': '⑥',
        'RKnee': '⑦',
        'LAnkle': '⑧',
        'RAnkle': '⑨'
    };

    // 関節点間の接続定義
    const jointConnections = [
        ['LShoulder', 'LHip'],
        ['RShoulder', 'RHip'],
        ['LHip', 'LKnee'],
        ['RHip', 'RKnee'],
        ['LKnee', 'LAnkle'],
        ['RKnee', 'RAnkle'],
        ['LShoulder', 'RShoulder'],
        ['LHip', 'RHip'],
        ['LShoulder', 'C7'],
        ['RShoulder', 'C7']
    ];

    // アップロードエリアのクリックでファイル選択
    uploadArea.addEventListener('click', function(e) {
        // ボタンのクリックは別途処理されるのでそこを回避
        if (e.target.tagName.toLowerCase() !== 'button') {
            fileInput.click();
        }
    });

    // ドラッグ&ドロップイベントのハンドリング
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.style.backgroundColor = 'rgba(108, 92, 231, 0.1)';
    });

    uploadArea.addEventListener('dragleave', function() {
        this.style.backgroundColor = '';
    });

    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.style.backgroundColor = '';
        
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // ファイル選択イベント
    fileInput.addEventListener('change', function() {
        console.log('ファイル選択イベント発生', this.files);
        if (this.files.length) {
            const file = this.files[0];
            console.log('選択されたファイル:', file.name, file.type, file.size);
            handleFileUpload(file);
        }
    });

    // ファイルアップロード処理
    function handleFileUpload(file) {
        console.log('アップロード処理開始:', file);
        if (!file) {
            console.error('ファイルが選択されていません');
            return;
        }
        
        // ファイルタイプの検証
        if (!file.type.match('image.*')) {
            console.error('画像ファイルではありません:', file.type);
            showNotification('画像ファイルを選択してください', 'error');
            return;
        }
        
        // FormDataの作成
        const formData = new FormData();
        formData.append('file', file);
        console.log('FormData作成完了');
        
        // ローディング表示
        loading.style.display = 'flex';
        
        // サーバーにアップロード
        console.log('アップロードリクエスト送信');
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            console.log('サーバーレスポンス:', response.status);
            if (!response.ok) {
                throw new Error(`アップロードに失敗しました (${response.status})`);
            }
            return response.json();
        })
        .then(data => {
            console.log('サーバーからのデータ:', data);
            if (data.success) {
                // 画像と関節点データを保存
                uploadedImageUrl = data.image_url;
                imageWidth = data.image_width;
                imageHeight = data.image_height;
                keypoints = data.keypoints;
                
                // 画像を表示
                uploadedImage.src = data.image_url;
                uploadedImage.onload = function() {
                    uploadedImage.style.display = 'block';
                    canvasContainer.style.display = 'block';
                    
                    // 関節点を描画
                    renderJointPoints();
                    
                    // AI検出メッセージ
                    const statusClass = data.ai_detection_used ? 'badge-success' : 'badge-warning';
                    const statusMessage = data.ai_detection_used ? 
                        'AI姿勢検出を使用しました' : 
                        'デフォルト位置を使用しています - 手動調整を推奨します';
                    
                    uploadStatus.innerHTML = `<div class="status-badge ${statusClass}">${statusMessage}</div>`;
                    uploadStatus.style.display = 'block';
                    
                    showNotification('画像のアップロードに成功しました', 'success');
                };
                uploadedImage.onerror = function() {
                    console.error('画像の読み込みに失敗しました:', data.image_url);
                    showNotification('画像の読み込みに失敗しました', 'error');
                    loading.style.display = 'none';
                };
            } else {
                showNotification(data.error || 'アップロードに失敗しました', 'error');
                loading.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('アップロードエラー:', error);
            showNotification(error.message, 'error');
            loading.style.display = 'none';
        });
    }

    // 関節点の描画
    function renderJointPoints() {
        // 既存の関節点と線を削除
        clearJointElements();
        
        // 関節点間の線を描画
        renderJointLines();
        
        // 関節点を描画
        for (const jointName in keypoints) {
            const point = keypoints[jointName];
            
            // 要素の作成
            const jointElement = document.createElement('div');
            jointElement.className = 'joint-point';
            if (jointName === selectedJoint) {
                jointElement.classList.add('selected');
            }
            jointElement.id = `joint-${jointName}`;
            jointElement.setAttribute('data-joint', jointName);
            jointElement.textContent = jointNumbers[jointName] || '';
            
            // 位置の設定
            const x = point.x * canvasContainer.clientWidth / imageWidth;
            const y = point.y * canvasContainer.clientHeight / imageHeight;
            jointElement.style.left = `${x}px`;
            jointElement.style.top = `${y}px`;
            
            // ドラッグイベントの設定
            setupDragEvents(jointElement);
            
            // クリックイベント（選択）
            jointElement.addEventListener('click', function(e) {
                e.stopPropagation();
                selectJoint(jointName);
            });
            
            // キャンバスに追加
            canvasContainer.appendChild(jointElement);
        }
        
        // 関節ボタンの選択状態を更新
        updateJointButtons();
    }

    // 関節点間の線を描画
    function renderJointLines() {
        jointConnections.forEach(connection => {
            const [joint1, joint2] = connection;
            
            if (keypoints[joint1] && keypoints[joint2]) {
                const point1 = keypoints[joint1];
                const point2 = keypoints[joint2];
                
                // キャンバスサイズに合わせて座標を変換
                const x1 = point1.x * canvasContainer.clientWidth / imageWidth;
                const y1 = point1.y * canvasContainer.clientHeight / imageHeight;
                const x2 = point2.x * canvasContainer.clientWidth / imageWidth;
                const y2 = point2.y * canvasContainer.clientHeight / imageHeight;
                
                // 線の長さと角度を計算
                const length = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
                const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
                
                // 線の要素を作成
                const lineElement = document.createElement('div');
                lineElement.className = 'joint-line';
                lineElement.style.width = `${length}px`;
                lineElement.style.left = `${x1}px`;
                lineElement.style.top = `${y1}px`;
                lineElement.style.transform = `rotate(${angle}deg)`;
                
                // C7関連の線は特別な色に
                if (connection.includes('C7')) {
                    lineElement.style.backgroundColor = '#4834d4';
                }
                
                canvasContainer.appendChild(lineElement);
            }
        });
    }

    // 関節点のドラッグイベントを設定
    function setupDragEvents(element) {
        element.addEventListener('mousedown', startDrag);
        element.addEventListener('touchstart', startDrag, { passive: false });
        
        function startDrag(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const jointName = element.getAttribute('data-joint');
            selectJoint(jointName);
            
            isDragging = true;
            
            // マウスかタッチかに応じて座標を取得
            let clientX, clientY;
            if (e.type === 'mousedown') {
                clientX = e.clientX;
                clientY = e.clientY;
            } else {
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            }
            
            // マウス移動/タッチ移動イベント
            function moveHandler(e) {
                if (!isDragging) return;
                
                let moveX, moveY;
                if (e.type === 'mousemove') {
                    moveX = e.clientX;
                    moveY = e.clientY;
                } else {
                    moveX = e.touches[0].clientX;
                    moveY = e.touches[0].clientY;
                }
                
                // キャンバス座標系に変換
                const rect = canvasContainer.getBoundingClientRect();
                let x = moveX - rect.left;
                let y = moveY - rect.top;
                
                // キャンバス内に制限
                x = Math.max(0, Math.min(x, rect.width));
                y = Math.max(0, Math.min(y, rect.height));
                
                // 関節点の位置を更新
                updateJointPosition(jointName, x, y);
            }
            
            // ドラッグ終了時のハンドラ
            function endDrag() {
                isDragging = false;
                document.removeEventListener('mousemove', moveHandler);
                document.removeEventListener('touchmove', moveHandler);
                document.removeEventListener('mouseup', endDrag);
                document.removeEventListener('touchend', endDrag);
            }
            
            // イベントリスナーの設定
            document.addEventListener('mousemove', moveHandler);
            document.addEventListener('touchmove', moveHandler, { passive: false });
            document.addEventListener('mouseup', endDrag);
            document.addEventListener('touchend', endDrag);
        }
    }

    // 関節点位置の更新
    function updateJointPosition(jointName, canvasX, canvasY) {
        if (!keypoints[jointName]) return;
        
        // キャンバス座標から画像座標に変換
        const imageX = canvasX * imageWidth / canvasContainer.clientWidth;
        const imageY = canvasY * imageHeight / canvasContainer.clientHeight;
        
        // 座標を更新
        keypoints[jointName].x = imageX;
        keypoints[jointName].y = imageY;
        
        // DOM要素の位置を更新
        const jointElement = document.getElementById(`joint-${jointName}`);
        if (jointElement) {
            jointElement.style.left = `${canvasX}px`;
            jointElement.style.top = `${canvasY}px`;
        }
        
        // 関節点情報を更新
        updateSelectedJointInfo();
        
        // 線を再描画
        renderJointLines();
    }

    // 関節点の選択
    function selectJoint(jointName) {
        selectedJoint = jointName;
        
        // 関節点情報を更新
        updateSelectedJointInfo();
        
        // 関節点を再描画
        renderJointPoints();
    }

    // 選択中の関節点情報を更新
    function updateSelectedJointInfo() {
        if (selectedJoint && keypoints[selectedJoint]) {
            const point = keypoints[selectedJoint];
            const label = jointLabels[selectedJoint] || selectedJoint;
            selectedJointInfo.textContent = `${label}: X=${Math.round(point.x)}, Y=${Math.round(point.y)}`;
        } else {
            selectedJointInfo.textContent = '関節を選択して位置を調整';
        }
    }

    // 関節ボタンの選択状態を更新
    function updateJointButtons() {
        jointButtons.forEach(button => {
            const jointName = button.getAttribute('data-joint');
            if (jointName === selectedJoint) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    // 関節点と線の要素をクリア
    function clearJointElements() {
        document.querySelectorAll('.joint-point, .joint-line').forEach(el => el.remove());
    }

    // 関節ボタンのクリックイベント
    jointButtons.forEach(button => {
        button.addEventListener('click', function() {
            const jointName = this.getAttribute('data-joint');
            selectJoint(jointName);
        });
    });

    // 方向キーによる調整
    arrowBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            if (!selectedJoint || !keypoints[selectedJoint]) return;
            
            const direction = this.getAttribute('data-dir');
            const step = 5; // 移動量
            
            // キャンバスサイズに合わせて座標を取得
            const point = keypoints[selectedJoint];
            const x = point.x * canvasContainer.clientWidth / imageWidth;
            const y = point.y * canvasContainer.clientHeight / imageHeight;
            
            // 方向に応じて移動量を設定
            let dx = 0, dy = 0;
            
            switch (direction) {
                case 'n': dy = -step; break;
                case 's': dy = step; break;
                case 'e': dx = step; break;
                case 'w': dx = -step; break;
                case 'ne': dx = step; dy = -step; break;
                case 'nw': dx = -step; dy = -step; break;
                case 'se': dx = step; dy = step; break;
                case 'sw': dx = -step; dy = step; break;
                case 'c': break; // 中央ボタンは何もしない
            }
            
            // 位置を更新
            updateJointPosition(selectedJoint, x + dx, y + dy);
        });
    });

    // セット姿勢分析
    analyzeSetBtn.addEventListener('click', function() {
        analyzePosture('set');
    });

    // 飛び出し分析
    analyzeTakeoffBtn.addEventListener('click', function() {
        analyzePosture('takeoff');
    });

    // 姿勢分析の実行
    function analyzePosture(mode) {
        if (Object.keys(keypoints).length === 0) {
            showNotification('関節点データがありません。画像をアップロードしてください。', 'error');
            return;
        }
        
        // ローディング表示
        loading.style.display = 'flex';
        
        // 分析リクエスト
        fetch('/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                keypoints: keypoints,
                analysis_mode: mode
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 分析結果の表示
                displayAnalysisResults(data, mode);
                showNotification('分析完了！結果を確認してください。', 'success');
            } else {
                showNotification(data.error || '分析に失敗しました', 'error');
            }
        })
        .catch(error => {
            showNotification('通信エラー: ' + error.message, 'error');
        })
        .finally(() => {
            loading.style.display = 'none';
        });
    }

    // 分析結果の表示
    function displayAnalysisResults(data, mode) {
        // 結果パネルを表示
        analysisPanel.style.display = 'block';
        
        // 結果コンテナをクリア
        angleResults.innerHTML = '';
        
        if (mode === 'set') {
            // セット姿勢の結果表示
            if (data.front_angle !== undefined) {
                addAngleItem('前足膝角度', data.front_angle);
            }
            
            if (data.rear_angle !== undefined) {
                addAngleItem('後足膝角度', data.rear_angle);
            }
            
            if (data.front_hip_angle !== undefined) {
                addAngleItem('前足股関節角度', data.front_hip_angle);
            }
        } else {
            // 飛び出し分析の結果表示
            if (data.lower_angle !== undefined) {
                addAngleItem('下半身角度', data.lower_angle);
            }
            
            if (data.upper_angle !== undefined) {
                addAngleItem('上半身角度', data.upper_angle);
            }
            
            if (data.kunoji_angle !== undefined) {
                addAngleItem('くの字角度', data.kunoji_angle);
            }
        }
    }

    // 角度項目の追加
    function addAngleItem(name, value) {
        const item = document.createElement('div');
        item.className = 'angle-item';
        item.innerHTML = `
            <span class="angle-name">${name}</span>
            <span class="angle-value">${value}°</span>
        `;
        angleResults.appendChild(item);
    }

    // 共有ボタンのクリックイベント
    shareBtn.addEventListener('click', function() {
        // 実際の共有機能の実装（デモではアラート表示）
        const shareId = Math.random().toString(36).substring(2, 10);
        const shareUrl = window.location.origin + '/share/' + shareId;
        
        // クリップボードにコピー
        navigator.clipboard.writeText(shareUrl)
            .then(() => {
                showNotification('共有URLをクリップボードにコピーしました', 'success');
            })
            .catch(() => {
                showNotification('共有URLの生成に成功: ' + shareUrl, 'success');
            });
    });

    // ダウンロードボタンのクリックイベント
    downloadBtn.addEventListener('click', function() {
        if (!uploadedImageUrl) {
            showNotification('保存する画像がありません', 'error');
            return;
        }
        
        // キャンバスに画像と関節点を描画して保存
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // 元の画像サイズでキャンバスを作成
        canvas.width = imageWidth;
        canvas.height = imageHeight;
        
        // 画像の読み込みと描画
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = function() {
            // 画像を描画
            ctx.drawImage(img, 0, 0, imageWidth, imageHeight);
            
            // 関節点間の線を描画
            jointConnections.forEach(connection => {
                const [joint1, joint2] = connection;
                
                if (keypoints[joint1] && keypoints[joint2]) {
                    const point1 = keypoints[joint1];
                    const point2 = keypoints[joint2];
                    
                    ctx.beginPath();
                    ctx.moveTo(point1.x, point1.y);
                    ctx.lineTo(point2.x, point2.y);
                    
                    // C7関連の線は特別な色に
                    if (connection.includes('C7')) {
                        ctx.strokeStyle = '#4834d4';
                    } else {
                        ctx.strokeStyle = 'red';
                    }
                    
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            });
            
            // 関節点を描画
            for (const jointName in keypoints) {
                const point = keypoints[jointName];
                
                // 円を描画
                ctx.beginPath();
                ctx.arc(point.x, point.y, 8, 0, 2 * Math.PI);
                ctx.fillStyle = 'red';
                ctx.fill();
                ctx.strokeStyle = 'white';
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // 数字を描画
                ctx.fillStyle = 'white';
                ctx.font = '10px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(jointNumbers[jointName] || '', point.x, point.y);
            }
            
            // キャンバスを画像としてダウンロード
            const link = document.createElement('a');
            link.download = 'crouch-analysis.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
            
            showNotification('画像を保存しました', 'success');
        };
        img.onerror = function() {
            console.error('
