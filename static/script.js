// 関節点のドラッグ機能を追加する部分
document.addEventListener('DOMContentLoaded', function() {
    // 関節点がドラッグ可能になるように設定
    enableJointDragging();
    
    // 「AI自動検出」ボタンのイベントリスナー
    const autoDetectBtn = document.getElementById('autoDetectBtn');
    if (autoDetectBtn) {
        autoDetectBtn.addEventListener('click', detectJointsFromImage);
    }
    
    // 「姿勢分析」ボタンのイベントリスナー
    const analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzePosture);
    }
});

// 関節点のドラッグ機能を有効にする
function enableJointDragging() {
    document.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('joint-marker')) {
            const marker = e.target;
            
            // ドラッグ開始位置
            const startX = e.clientX;
            const startY = e.clientY;
            const origLeft = parseInt(marker.style.left);
            const origTop = parseInt(marker.style.top);
            
            // マーカー移動関数
            function moveMarker(e) {
                const newLeft = origLeft + (e.clientX - startX);
                const newTop = origTop + (e.clientY - startY);
                
                // コンテナ内に収まるように制限
                const container = document.getElementById('imageContainer');
                const maxLeft = container.offsetWidth - marker.offsetWidth;
                const maxTop = container.offsetHeight - marker.offsetHeight;
                
                marker.style.left = Math.max(0, Math.min(newLeft, maxLeft)) + 'px';
                marker.style.top = Math.max(0, Math.min(newTop, maxTop)) + 'px';
            }
            
            // ドラッグ終了時のクリーンアップ
            function cleanUp() {
                document.removeEventListener('mousemove', moveMarker);
                document.removeEventListener('mouseup', cleanUp);
            }
            
            document.addEventListener('mousemove', moveMarker);
            document.addEventListener('mouseup', cleanUp);
        }
    });
}

// 画像から関節点を検出する
function detectJointsFromImage() {
    const uploadedImage = document.getElementById('uploadedImage');
    if (!uploadedImage || !uploadedImage.src) {
        alert('先に画像をアップロードしてください');
        return;
    }
    
    // 画像データを取得してAPIに送信
    fetch(uploadedImage.src)
        .then(res => res.blob())
        .then(blob => {
            const formData = new FormData();
            formData.append('image', blob, 'image.jpg');
            
            // ローディング表示
            showLoading(true);
            
            return fetch('/detect_joints', {
                method: 'POST',
                body: formData
            });
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // 関節点を配置
                placeJointMarkers(data.joints);
            } else {
                alert('関節検出エラー: ' + (data.error || '不明なエラー'));
            }
        })
        .catch(err => {
            console.error('Error:', err);
            alert('関節検出処理中にエラーが発生しました');
        })
        .finally(() => {
            showLoading(false);
        });
}

// 関節点マーカーを配置
function placeJointMarkers(joints) {
    // 既存のマーカーをクリア
    clearMarkers();
    
    // 画像コンテナの取得または作成
    const imageElement = document.getElementById('uploadedImage');
    let container = document.getElementById('imageContainer');
    
    if (!container) {
        container = document.createElement('div');
        container.id = 'imageContainer';
        container.style.position = 'relative';
        container.style.display = 'inline-block';
        
        // 画像を囲むようにコンテナを配置
        imageElement.parentNode.insertBefore(container, imageElement);
        container.appendChild(imageElement);
    }
    
    // 画像サイズを取得
    const imageWidth = imageElement.width;
    const imageHeight = imageElement.height;
    
    // 各関節点をマーカーとして配置
    Object.keys(joints).forEach(key => {
        const joint = joints[key];
        const x = joint.x * imageWidth;
        const y = joint.y * imageHeight;
        
        // マーカー要素を作成
        const marker = document.createElement('div');
        marker.className = 'joint-marker';
        marker.id = 'joint-' + key;
        marker.dataset.jointId = key;
        marker.style.left = x + 'px';
        marker.style.top = y + 'px';
        
        // マーカーのスタイル
        marker.style.position = 'absolute';
        marker.style.width = '12px';
        marker.style.height = '12px';
        marker.style.borderRadius = '50%';
        marker.style.backgroundColor = 'red';
        marker.style.cursor = 'move';
        marker.style.zIndex = '100';
        marker.style.transform = 'translate(-50%, -50%)';
        
        // マーカーにラベル表示
        const jointNames = {
            '1': '頭', '2': '肩', '3': '腰',
            '4': '右膝', '5': '左膝', 
            '6': '右足首', '7': '左足首',
            '8': '左手首', '9': '右手首'
        };
        
        const label = document.createElement('span');
        label.textContent = jointNames[key] || key;
        label.style.position = 'absolute';
        label.style.top = '15px';
        label.style.left = '0';
        label.style.fontSize = '10px';
        label.style.whiteSpace = 'nowrap';
        
        marker.appendChild(label);
        container.appendChild(marker);
    });
    
    // 関節点を線で結ぶ
    drawJointConnections();
}

// 姿勢を分析する
function analyzePosture() {
    // 現在の関節点の位置データを収集
    const joints = collectJointPositions();
    
    if (Object.keys(joints).length === 0) {
        alert('関節点が配置されていません。先に「AI自動検出」ボタンをクリックするか、手動で関節点を配置してください。');
        return;
    }
    
    // ローディング表示
    showLoading(true);
    
    // 分析APIを呼び出し
    fetch('/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ joints: joints })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // 分析結果を表示
            displayAnalysisResults(data.analysis);
        } else {
            alert('分析エラー: ' + (data.error || '不明なエラー'));
        }
    })
    .catch(err => {
        console.error('Error:', err);
        alert('姿勢分析処理中にエラーが発生しました');
    })
    .finally(() => {
        showLoading(false);
    });
}

// ローディング表示の制御
function showLoading(show) {
    let loader = document.getElementById('loader');
    
    if (show) {
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'loader';
            loader.innerHTML = '<div class="spinner"></div><p>処理中...</p>';
            loader.style.position = 'fixed';
            loader.style.top = '0';
            loader.style.left = '0';
            loader.style.width = '100%';
            loader.style.height = '100%';
            loader.style.backgroundColor = 'rgba(0,0,0,0.5)';
            loader.style.display = 'flex';
            loader.style.justifyContent = 'center';
            loader.style.alignItems = 'center';
            loader.style.zIndex = '1000';
            document.body.appendChild(loader);
        }
    } else if (loader) {
        loader.remove();
    }
}

// その他の必要な関数...
