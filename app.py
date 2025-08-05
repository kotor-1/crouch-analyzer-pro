from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
import os
import uuid
from datetime import datetime
import mediapipe as mp
import cv2
import numpy as np
from PIL import Image
import io
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-key')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB制限

# アップロードフォルダが存在しない場合は作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 許可されるファイル拡張子
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        flash('ファイルがありません')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('ファイルが選択されていません')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # ユニークなファイル名を生成
        filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'message': 'アップロード成功',
            'filename': filename,
            'filepath': '/' + filepath
        })
    else:
        return jsonify({
            'success': False,
            'message': '許可されていないファイル形式です。PNG、JPG、WEBPのみ対応しています。'
        }), 400

@app.route('/detect_joints', methods=['POST'])
def detect_joints():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    img_bytes = file.read()
    
    # PILでの画像読み込み
    image = Image.open(io.BytesIO(img_bytes))
    image_np = np.array(image)
    
    # MediaPipe Pose検出の設定
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=True, 
                        model_complexity=2,
                        min_detection_confidence=0.5)
    
    # RGB形式に変換（MediaPipeの要件）
    # 注意: cv2はBGRで扱うが、PILからのnumpyアレイはRGBのため変換不要
    
    # ポーズ検出
    results = pose.process(image_np)
    
    if not results.pose_landmarks:
        return jsonify({'error': 'No pose detected'}), 400
    
    # 関節点の取得
    landmarks = results.pose_landmarks.landmark
    
    # クラウチングスタート姿勢に必要な関節点を抽出
    joint_points = {
        '1': {'x': landmarks[mp_pose.PoseLandmark.NOSE.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.NOSE.value].y},
        '2': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y},
        '3': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y},
        '4': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y},
        '5': {'x': landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y},
        '6': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y},
        '7': {'x': landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y},
        '8': {'x': landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y},
        '9': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, 
              'y': landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y}
    }
    
    return jsonify({'success': True, 'joints': joint_points})

@app.route('/analyze', methods=['POST'])
def analyze_posture():
    data = request.json
    joints = data.get('joints', {})
    
    if not joints:
        return jsonify({'error': '関節データがありません'}), 400
    
    # 以下は姿勢分析のロジック例
    analysis_result = {
        'score': calculate_score(joints),
        'feedback': generate_feedback(joints),
        'angles': calculate_angles(joints)
    }
    
    return jsonify({
        'success': True,
        'analysis': analysis_result
    })

def calculate_score(joints):
    # スコア計算のロジック（実際のアプリケーションに合わせて実装）
    # 例：理想的な角度との差分を計算
    try:
        angles = calculate_angles(joints)
        
        # 理想的な角度（例）
        ideal_angles = {
            'back_angle': 45,  # 背中の角度
            'knee_angle': 90,  # 膝の角度
            'ankle_angle': 80  # 足首の角度
        }
        
        # 各角度の差分を計算
        angle_diffs = {
            'back': abs(angles['back_angle'] - ideal_angles['back_angle']),
            'knee': abs(angles['knee_angle'] - ideal_angles['knee_angle']),
            'ankle': abs(angles['ankle_angle'] - ideal_angles['ankle_angle'])
        }
        
        # 重み付けを行い、スコアを計算（0-100）
        max_score = 100
        penalty = (angle_diffs['back'] * 0.5) + (angle_diffs['knee'] * 0.3) + (angle_diffs['ankle'] * 0.2)
        
        score = max(0, max_score - penalty)
        return round(score, 1)
    except Exception as e:
        print(f"スコア計算エラー: {str(e)}")
        return 0

def calculate_angles(joints):
    # 角度計算のロジック
    try:
        # 背中の角度（頭-肩-腰）
        back_angle = calculate_angle(
            (joints['1']['x'], joints['1']['y']),
            (joints['2']['x'], joints['2']['y']),
            (joints['3']['x'], joints['3']['y'])
        )
        
        # 膝の角度（腰-膝-足首）
        knee_angle = calculate_angle(
            (joints['3']['x'], joints['3']['y']),
            (joints['4']['x'], joints['4']['y']),
            (joints['6']['x'], joints['6']['y'])
        )
        
        # 足首の角度
        ankle_angle = calculate_angle(
            (joints['4']['x'], joints['4']['y']),
            (joints['6']['x'], joints['6']['y']),
            (joints['6']['x'] + 0.1, joints['6']['y'])  # 水平線を仮定
        )
        
        return {
            'back_angle': round(back_angle, 1),
            'knee_angle': round(knee_angle, 1),
            'ankle_angle': round(ankle_angle, 1)
        }
    except Exception as e:
        print(f"角度計算エラー: {str(e)}")
        return {'back_angle': 0, 'knee_angle': 0, 'ankle_angle': 0}

def calculate_angle(p1, p2, p3):
    # 3点間の角度を計算
    a = np.array([p1[0], p1[1]])
    b = np.array([p2[0], p2[1]])
    c = np.array([p3[0], p3[1]])
    
    ba = a - b
    bc = c - b
    
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    
    return np.degrees(angle)

def generate_feedback(joints):
    # フィードバック生成のロジック
    try:
        angles = calculate_angles(joints)
        feedback = []
        
        # 背中の角度チェック
        if angles['back_angle'] < 35:
            feedback.append("背中が丸まりすぎています。もう少し背筋を伸ばしましょう。")
        elif angles['back_angle'] > 55:
            feedback.append("上半身が立ちすぎています。もう少し前傾姿勢を取りましょう。")
        else:
            feedback.append("背中の角度は良好です。")
            
        # 膝の角度チェック
        if angles['knee_angle'] < 80:
            feedback.append("膝が曲がりすぎています。もう少し伸ばしましょう。")
        elif angles['knee_angle'] > 100:
            feedback.append("膝が伸びすぎています。もう少し曲げましょう。")
        else:
            feedback.append("膝の角度は良好です。")
            
        # 足首の角度チェック
        if angles['ankle_angle'] < 70:
            feedback.append("足首が過度に背屈しています。")
        elif angles['ankle_angle'] > 90:
            feedback.append("足首が過度に底屈しています。")
        else:
            feedback.append("足首の角度は良好です。")
            
        return feedback
    except Exception as e:
        print(f"フィードバック生成エラー: {str(e)}")
        return ["データ分析中にエラーが発生しました。関節点が正しく配置されているか確認してください。"]

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
