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
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-key')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB制限

# アップロードフォルダが存在しない場合は作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MediaPipe Pose初期化
mp_pose = mp.solutions.pose

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
    with mp_pose.Pose(
        static_image_mode=True, 
        model_complexity=2,
        min_detection_confidence=0.5
    ) as pose:
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
            # 関節点のマッピング
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
                'y': landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y},
            # C7（第7頸椎）の位置を計算
            '10': {'x': (landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x + 
                        landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x) / 2,
                  'y': (landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y + 
                        landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y) / 2}
        }
        
        return jsonify({'success': True, 'joints': joint_points})

@app.route('/analyze', methods=['POST'])
def analyze_posture():
    data = request.json
    joints = data.get('joints', {})
    mode = data.get('mode', 'set')  # 'set'または'start'
    
    if not joints:
        return jsonify({'error': '関節データがありません'}), 400
    
    # モードに応じた分析
    if mode == 'set':
        analysis_result = analyze_set_posture(joints)
    else:  # 'start'
        analysis_result = analyze_start_posture(joints)
    
    return jsonify({
        'success': True,
        'analysis': analysis_result
    })

def analyze_set_posture(joints):
    """セット姿勢の分析"""
    # 前足・後足の判定（膝の左右位置で判断）
    if float(joints['4']['x']) < float(joints['5']['x']):  # 右膝が左側
        front_points = ('3', '4', '6')  # 右腰-右膝-右足首
        rear_points = ('3', '5', '7')   # 右腰-左膝-左足首
        front_hip_points = ('3', '4')   # 右腰-右膝
    else:
        front_points = ('3', '5', '7')  # 右腰-左膝-左足首
        rear_points = ('3', '4', '6')   # 右腰-右膝-右足首
        front_hip_points = ('3', '5')   # 右腰-左膝
    
    # 角度計算
    front_angle = calculate_angle(
        (float(joints[front_points[0]]['x']), float(joints[front_points[0]]['y'])),
        (float(joints[front_points[1]]['x']), float(joints[front_points[1]]['y'])),
        (float(joints[front_points[2]]['x']), float(joints[front_points[2]]['y']))
    )
    
    rear_angle = calculate_angle(
        (float(joints[rear_points[0]]['x']), float(joints[rear_points[0]]['y'])),
        (float(joints[rear_points[1]]['x']), float(joints[rear_points[1]]['y'])),
        (float(joints[rear_points[2]]['x']), float(joints[rear_points[2]]['y']))
    )
    
    # 股関節角度の計算
    hip_angle = calculate_hip_ground_angle(
        (float(joints[front_hip_points[0]]['x']), float(joints[front_hip_points[0]]['y'])),
        (float(joints[front_hip_points[1]]['x']), float(joints[front_hip_points[1]]['y']))
    )
    
    angles = {
        'front_angle': round(front_angle, 1),
        'rear_angle': round(rear_angle, 1),
        'hip_angle': round(hip_angle, 1)
    }
    
    # スコア計算
    score = calculate_set_score(front_angle, rear_angle, hip_angle)
    
    # フィードバック生成
    feedback = generate_set_feedback(front_angle, rear_angle, hip_angle)
    
    return {
        'score': score,
        'angles': angles,
        'feedback': feedback
    }

def analyze_start_posture(joints):
    """飛び出し姿勢の分析"""
    # 前足の判定（足首の左右位置で判断）
    if float(joints['6']['x']) > float(joints['7']['x']):  # 右足首が右側
        hip = (float(joints['3']['x']), float(joints['3']['y']))  # 右腰
        ankle = (float(joints['6']['x']), float(joints['6']['y']))  # 右足首
    else:
        hip = (float(joints['3']['x']), float(joints['3']['y']))  # 右腰
        ankle = (float(joints['7']['x']), float(joints['7']['y']))  # 左足首
    
    c7 = (float(joints['10']['x']), float(joints['10']['y']))  # C7（第7頸椎）
    
    # 角度計算
    lower_angle = calculate_vector_angle_with_ground(hip, ankle)
    upper_angle = calculate_vector_angle_with_ground(c7, hip)
    kunoji_angle = calculate_angle(c7, hip, ankle)
    
    angles = {
        'lower_angle': round(lower_angle, 1),
        'upper_angle': round(upper_angle, 1),
        'kunoji_angle': round(kunoji_angle, 1)
    }
    
    # スコア計算
    score = calculate_start_score(lower_angle, upper_angle, kunoji_angle)
    
    # フィードバック生成
    feedback = generate_start_feedback(lower_angle, upper_angle, kunoji_angle)
    
    return {
        'score': score,
        'angles': angles,
        'feedback': feedback
    }

def calculate_angle(p1, p2, p3):
    """3点間の角度を計算"""
    a = np.array([p1[0], p1[1]])
    b = np.array([p2[0], p2[1]])
    c = np.array([p3[0], p3[1]])
    
    ba = a - b
    bc = c - b
    
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)  # 数値誤差対策
    angle = np.arccos(cosine_angle)
    
    return np.degrees(angle)

def calculate_hip_ground_angle(hip_pos, knee_pos):
    """股関節と地面の角度を計算"""
    dx = knee_pos[0] - hip_pos[0]
    dy = knee_pos[1] - hip_pos[1]
    
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)
    
    if angle_deg < 0:
        angle_deg = abs(angle_deg)
    elif angle_deg > 90:
        angle_deg = 180 - angle_deg
    
    return angle_deg

def calculate_vector_angle_with_ground(p1, p2):
    """ベクトルと地面の角度を計算"""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    
    v = np.array([dx, dy])
    ground = np.array([1, 0])
    
    v_norm = np.linalg.norm(v)
    cosine = np.dot(v, ground) / v_norm
    cosine = np.clip(cosine, -1.0, 1.0)  # 数値誤差対策
    angle = np.degrees(np.arccos(cosine))
    
    return angle

def calculate_set_score(front_angle, rear_angle, hip_angle):
    """セット姿勢のスコアを計算"""
    # 理想的な角度
    ideal_front = 90
    ideal_rear = 125
    ideal_hip = 50
    
    # 差分を計算
    front_diff = abs(front_angle - ideal_front)
    rear_diff = abs(rear_angle - ideal_rear)
    hip_diff = abs(hip_angle - ideal_hip)
    
    # 重み付け
    total_diff = (front_diff * 0.4) + (rear_diff * 0.3) + (hip_diff * 0.3)
    
    # スコア計算（100点満点）
    max_diff = 50  # 最大許容差
    score = max(0, 100 - (total_diff * 100 / max_diff))
    
    return round(score, 1)

def calculate_start_score(lower_angle, upper_angle, kunoji_angle):
    """飛び出し姿勢のスコアを計算"""
    # 理想的な角度
    ideal_lower = 45
    ideal_upper = 40
    ideal_kunoji = 160
    
    # 差分を計算
    lower_diff = abs(lower_angle - ideal_lower)
    upper_diff = abs(upper_angle - ideal_upper)
    kunoji_diff = abs(kunoji_angle - ideal_kunoji)
    
    # 重み付け
    total_diff = (lower_diff * 0.3) + (upper_diff * 0.3) + (kunoji_diff * 0.4)
    
    # スコア計算（100点満点）
    max_diff = 50  # 最大許容差
    score = max(0, 100 - (total_diff * 100 / max_diff))
    
    return round(score, 1)

def generate_set_feedback(front_angle, rear_angle, hip_angle):
    """セット姿勢のフィードバックを生成"""
    feedback = []
    
    # 前足の膝角度
    if abs(front_angle - 90) > 10:
        feedback.append(f"前足の膝角度 {front_angle:.1f}° → 90°に近づけましょう。")
    else:
        feedback.append(f"前足の膝角度 {front_angle:.1f}° → 理想的です！")
    
    # 後足の膝角度
    if rear_angle < 120 or rear_angle > 135:
        feedback.append(f"後足の膝角度 {rear_angle:.1f}° → 適正範囲(120-135°)を意識しましょう。")
    else:
        feedback.append(f"後足の膝角度 {rear_angle:.1f}° → 理想的です！")
    
    # 股関節角度
    if hip_angle < 40 or hip_angle > 60:
        feedback.append(f"前足股関節角度 {hip_angle:.1f}° → 適正範囲(40-60°)を意識しましょう。")
    else:
        feedback.append(f"前足股関節角度 {hip_angle:.1f}° → 理想的です！")
    
    return feedback

def generate_start_feedback(lower_angle, upper_angle, kunoji_angle):
    """飛び出し姿勢のフィードバックを生成"""
    feedback = []
    
    # 下半身角度
    if lower_angle < 30 or lower_angle > 60:
        feedback.append(f"下半身角度 {lower_angle:.1f}° → 30-60°が目安です。")
    else:
        feedback.append(f"下半身角度 {lower_angle:.1f}° → 理想的です！")
    
    # 上半身角度
    if upper_angle < 25 or upper_angle > 55:
        feedback.append(f"上半身角度 {upper_angle:.1f}° → 25-55°が目安です。")
    else:
        feedback.append(f"上半身角度 {upper_angle:.1f}° → 理想的です！")
    
    # くの字角度
    if kunoji_angle < 150:
        feedback.append(f"くの字角度 {kunoji_angle:.1f}° → 150°以上が目安です。")
    else:
        feedback.append(f"くの字角度 {kunoji_angle:.1f}° → 理想的です！")
    
    return feedback

@app.route('/healthz')
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
