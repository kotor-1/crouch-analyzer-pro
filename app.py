from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
import os
import cv2
import numpy as np
import uuid
from datetime import datetime
import mediapipe as mp
import math
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-key')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB制限

# アップロードフォルダが存在しない場合は作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MediaPipe Poseモデルの初期化
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

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
    
    # 画像をOpenCVで読み込む
    file_bytes = np.asarray(bytearray(file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # MediaPipe Poseで関節検出
    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.5) as pose:
        
        # BGR画像をRGBに変換
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = pose.process(img_rgb)
        
        if not results.pose_landmarks:
            return jsonify({'error': 'No pose detected'}), 400
        
        # 検出された関節点を正規化された座標で取得
        height, width, _ = img.shape
        landmarks = results.pose_landmarks.landmark
        
        # 必要な関節点をマッピング
        joint_points = {
            '1': {'x': landmarks[mp_pose.PoseLandmark.NOSE.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.NOSE.value].y},
            '2': {'x': landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y},
            '3': {'x': landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y},
            '4': {'x': landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y},
            '5': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y},
            '6': {'x': landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y},
            '7': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y},
            '8': {'x': landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y},
            '9': {'x': landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, 
                  'y': landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y},
        }
        
        return jsonify({'success': True, 'joints': joint_points})

@app.route('/analyze', methods=['POST'])
def analyze_posture():
    data = request.json
    joints = data.get('joints', {})
    
    if not joints:
        return jsonify({'error': '関節データがありません'}), 400
    
    # 姿勢分析のロジック
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
    # スコア計算のロジック
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
    a = (p1[0], p1[1])
    b = (p2[0], p2[1])
    c = (p3[0], p3[1])
    
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    
    # ドット積
    dot_product = ba[0] * bc[0] + ba[1] * bc[1]
    
    # ベクトルの長さ
    len_ba = math.sqrt(ba[0]**2 + ba[1]**2)
    len_bc = math.sqrt(bc[0]**2 + bc[1]**2)
    
    # コサイン
    cosine = dot_product / (len_ba * len_bc)
    cosine = max(-1.0, min(1.0, cosine))  # -1.0から1.0の範囲に制限
    
    # 角度（ラジアン）を度に変換
    angle = math.acos(cosine) * 180 / math.pi
    
    return angle

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

@app.route('/healthz')
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
