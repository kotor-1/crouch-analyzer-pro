// 既存のコードはそのまま残し、以下を追加

// 関節点検出APIを呼び出す関数
function detectJoints(imageFile) {
    const formData = new FormData();
    formData.append('image', imageFile);
    
    // ローディング表示
    showLoading(true);
    
    fetch('/detect_joints', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert('関節検出エラー: ' + (data.error || '不明なエラー'));
            return;
        }
        
        // 検出された関節点を配置
        placeJointMarkers(data.joints);
        
        // 自動分析を実行
        analyzePosture(data.joints);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('関節検出中にエラーが発生しました');
    })
    .finally(() => {
        showLoading(false);
    });
}

// ローディング表示を制御する関数
function showLoading(show) {
    let loadingElement = document.getElementById('loadingOverlay');
    if (!loadingElement && show) {
        loadingElement = document.createElement('div');
        loadingElement.id = 'loadingOverlay';
        loadingElement.innerHTML = '<div class="spinner"></div><p>関節を検出中...</p>';
        document.body.appendChild(loadingElement);
    } else if (loadingElement && !show) {
        loadingElement.remove();
    }
}

// 画像アップロード後の処理に自動検出を追加
// 既存のアップロード処理関数を探し、その中で detectJoints(file) を呼び出す
// 例：
/*
const fileInput = document.getElementById('fileInput');
if (fileInput) {
    fileInput.addEventListener('change', function() {
        if (this.files.length) {
            const file = this.files[0];
            // ここに追加
            detectJoints(file);
        }
    });
}
*/

// 必要に応じて、既存の関数に自動検出機能を統合してください
        toast.remove();
    }, 3000);
}
