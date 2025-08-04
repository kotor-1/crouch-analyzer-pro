from flask import Flask, render_template, request, jsonify, send_from_directory
import cv2
import mediapipe as mp
import numpy as np
import math
from PIL import Image
import io
import base64
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# アップロードフォルダが存在しない場合は作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MediaPipe姿勢推定の初期化
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)

# 関節点の名前とインデックスのマッピング
POSE_LANDMARKS = {
    0: "鼻", 1: "左目（内側）", 2: "左目", 3: "左目（外側）", 4: "右目（内側）", 5: "右目", 6: "右目（外側）",
    7: "左耳", 8: "右耳", 9: "口（左）", 10: "口（右）",
    11: "左肩", 12: "右肩", 13: "左肘", 14: "右肘", 15: "左手首", 16: "右手首",
    17: "左小指", 18: "右小指", 19: "左人差し指", 20: "右人差し指", 21: "左親指", 22: "右親指",
    23: "左腰", 24: "右腰", 25: "左膝", 26: "右膝", 27: "左足首", 28: "右足首",
    29: "左かかと", 30: "右かかと", 31: "左つま先", 32: "右つま先"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def calculate_angle(point1, point2, point3):
    """3点から角度を計算する関数"""
    try:
        # ベクトルを計算
        vector1 = np.array([point1[0] - point2[0], point1[1] - point2[1]])
        vector2 = np.array([point3[0] - point2[0], point3[1] - point2[1]])
        
        # 内積を計算
        dot_product = np.dot(vector1, vector2)
        
        # ベクトルの大きさを計算
        magnitude1 = np.linalg.norm(vector1)
        magnitude2 = np.linalg.norm(vector2)
        
        # ゼロ除算を避ける
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        # cosθを計算
        cos_theta = dot_product / (magnitude1 * magnitude2)
        
        # 数値誤差を修正（-1から1の範囲に制限）
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        
        # 角度を計算（ラジアンから度に変換）
        angle = math.degrees(math.acos(cos_theta))
        
        return round(angle, 1)
    except:
        return 0

def analyze_crouch_start(landmarks, analysis_type="set"):
    """クラウチングスタートの分析を行う"""
    analysis_result = {}
    
    if analysis_type == "set":
        # セット姿勢の分析
        # 前足の膝角度（左膝を前足と仮定）
        if all(idx in landmarks for idx in [23, 25, 27]):  # 左腰、左膝、左足首
            front_knee_angle = calculate_angle(landmarks[23], landmarks[25], landmarks[27])
            analysis_result['前足の膝角度'] = {
                'value': front_knee_angle,
                'ideal_min': 80,
                'ideal_max': 100,
                'status': 'good' if 80 <= front_knee_angle <= 100 else 'needs_adjustment'
            }
        
        # 後足の膝角度（右膝を後足と仮定）
        if all(idx in landmarks for idx in [24, 26, 28]):  # 右腰、右膝、右足首
            back_knee_angle = calculate_angle(landmarks[24], landmarks[26], landmarks[28])
            analysis_result['後足の膝角度'] = {
                'value': back_knee_angle,
                'ideal_min': 120,
                'ideal_max': 135,
                'status': 'good' if 120 <= back_knee_angle <= 135 else 'needs_adjustment'
            }
        
        # 前足股関節角度
        if all(idx in landmarks for idx in [11, 23, 25]):  # 左肩、左腰、左膝
            front_hip_angle = calculate_angle(landmarks[11], landmarks[23], landmarks[25])
            analysis_result['前足股関節角度'] = {
                'value': front_hip_angle,
                'ideal_min': 40,
                'ideal_max': 60,
                'status': 'good' if 40 <= front_hip_angle <= 60 else 'needs_adjustment'
            }
            
    elif analysis_type == "start":
        # 飛び出し分析
        # 下半身角度（腰-膝-足首）
        if all(idx in landmarks for idx in [23, 25, 27]):
            lower_body_angle = calculate_angle(landmarks[23], landmarks[25], landmarks[27])
            analysis_result['下半身角度'] = {
                'value': lower_body_angle,
                'ideal_min': 30,
                'ideal_max': 60,
                'status': 'good' if 30 <= lower_body_angle <= 60 else 'needs_adjustment'
            }
        
        # 上半身角度（肩-腰-膝）
        if all(idx in landmarks for idx in [11, 23, 25]):
            upper_body_angle = calculate_angle(landmarks[11], landmarks[23], landmarks[25])
            analysis_result['上半身角度'] = {
                'value': upper_body_angle,
                'ideal_min': 25,
                'ideal_max': 55,
                'status': 'good' if 25 <= upper_body_angle <= 55 else 'needs_adjustment'
            }
        
        # くの字角度（肩-腰-足首）
        if all(idx in landmarks for idx in [11, 23, 27]):
            kuno_angle = calculate_angle(landmarks[11], landmarks[23], landmarks[27])
            analysis_result['くの字角度'] = {
                'value': kuno_angle,
                'ideal_min': 150,
                'ideal_max': 180,
                'status': 'good' if 150 <= kuno_angle <= 180 else 'needs_adjustment'
            }
    
    return analysis_result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # ファイルを保存
            filename = secure_filename(file.filename)
            if not filename:
                filename = 'uploaded_image.jpg'
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # MediaPipeで姿勢推定
            image = cv2.imread(filepath)
            if image is None:
                return jsonify({'error': '画像の読み込みに失敗しました'}), 400
                
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)
            
            landmarks_data = {}
            if results.pose_landmarks:
                height, width = image.shape[:2]
                for idx, landmark in enumerate(results.pose_landmarks.landmark):
                    x = int(landmark.x * width)
                    y = int(landmark.y * height)
                    landmarks_data[idx] = [x, y]
            
            return jsonify({
                'success': True,
                'filename': filename,
                'landmarks': landmarks_data,
                'image_size': {'width': image.shape[1], 'height': image.shape[0]}
            })
            
        except Exception as e:
            return jsonify({'error': f'画像処理中にエラーが発生しました: {str(e)}'}), 500
    
    return jsonify({'error': '無効なファイル形式です'}), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        landmarks = data.get('landmarks', {})
        analysis_type = data.get('analysis_type', 'set')
        
        # 文字列キーを整数に変換
        landmarks_int = {}
        for key, value in landmarks.items():
            landmarks_int[int(key)] = value
        
        result = analyze_crouch_start(landmarks_int, analysis_type)
        return jsonify({'success': True, 'analysis': result})
        
    except Exception as e:
        return jsonify({'error': f'分析中にエラーが発生しました: {str(e)}'}), 500

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)