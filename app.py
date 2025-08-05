from flask import Flask, render_template, request, jsonify, send_from_directory
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image
import base64
import io
import os
import math
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB制限

# アップロードフォルダが存在しない場合は作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
print(f"Upload folder created at: {app.config['UPLOAD_FOLDER']}")

# MediaPipe初期化
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, model_complexity=1, min_detection_confidence=0.3)

class AngleCalculator:
    """角度計算クラス"""
    
    @staticmethod
    def calculate_angle(p1, p2, p3):
        """3点間の角度を計算"""
        try:
            a = np.array([p1['x'], p1['y']], dtype=np.float64)
            b = np.array([p2['x'], p2['y']], dtype=np.float64)
            c = np.array([p3['x'], p3['y']], dtype=np.float64)
            
            ab = a - b
            cb = c - b
            
            ab_norm = np.linalg.norm(ab)
            cb_norm = np.linalg.norm(cb)
            
            if ab_norm < 1e-10 or cb_norm < 1e-10:
                return None
                
            cosine = np.dot(ab, cb) / (ab_norm * cb_norm)
            cosine = np.clip(cosine, -1.0, 1.0)
            angle = np.degrees(np.arccos(cosine))
            
            return round(float(angle), 1)
        except Exception:
            return None
    
    @staticmethod
    def calculate_vector_angle_with_ground(p1, p2):
        """ベクトルと地面の角度を計算"""
        try:
            dx = p2['x'] - p1['x']
            dy = p2['y'] - p1['y']
            
            v = np.array([dx, dy], dtype=np.float64)
            ground = np.array([1, 0], dtype=np.float64)
            
            norm_v = np.linalg.norm(v)
            if norm_v < 1e-10:
                return None
                
            cos_theta = np.dot(v, ground) / norm_v
            cos_theta = np.clip(cos_theta, -1.0, 1.0)
            angle = np.degrees(np.arccos(cos_theta))
            
            return round(float(angle), 1)
        except Exception:
            return None

def detect_pose(image_path):
    """MediaPipeで姿勢推定"""
    try:
        # 画像読み込み
        image = cv2.imread(image_path)
        if image is None:
            return None
            
        # RGBに変換
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 姿勢推定実行
        results = pose.process(image_rgb)
        
        if not results.pose_landmarks:
            return None
        
        # 画像サイズ取得
        h, w = image.shape[:2]
        
        # 関節点座標を取得
        landmarks = results.pose_landmarks.landmark
        keypoints = {}
        
        landmark_map = {
            'LShoulder': mp_pose.PoseLandmark.LEFT_SHOULDER,
            'RShoulder': mp_pose.PoseLandmark.RIGHT_SHOULDER,
            'LHip': mp_pose.PoseLandmark.LEFT_HIP,
            'RHip': mp_pose.PoseLandmark.RIGHT_HIP,
            'LKnee': mp_pose.PoseLandmark.LEFT_KNEE,
            'RKnee': mp_pose.PoseLandmark.RIGHT_KNEE,
            'LAnkle': mp_pose.PoseLandmark.LEFT_ANKLE,
            'RAnkle': mp_pose.PoseLandmark.RIGHT_ANKLE
        }
        
        for name, landmark_idx in landmark_map.items():
            landmark = landmarks[landmark_idx]
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            keypoints[name] = {'x': x, 'y': y}
        
        # C7（第7頸椎）を肩の中点として計算
        if 'LShoulder' in keypoints and 'RShoulder' in keypoints:
            l_shoulder = keypoints['LShoulder']
            r_shoulder = keypoints['RShoulder']
            keypoints['C7'] = {
                'x': int((l_shoulder['x'] + r_shoulder['x']) / 2),
                'y': int((l_shoulder['y'] + r_shoulder['y']) / 2)
            }
        
        return keypoints
        
    except Exception as e:
        print(f"姿勢推定エラー: {e}")
        return None

def analyze_posture(keypoints, analysis_mode):
    """姿勢分析"""
    calculator = AngleCalculator()
    
    if analysis_mode == 'set':
        # セット姿勢分析
        required_joints = ['LKnee', 'RKnee', 'LHip', 'RHip', 'LAnkle', 'RAnkle']
        
        if not all(joint in keypoints for joint in required_joints):
            return {'error': '必要な関節点が不足しています'}
        
        # 前足・後足の判定（右足が前の場合）
        if keypoints['RKnee']['x'] < keypoints['LKnee']['x']:
            front_joints = ('RHip', 'RKnee', 'RAnkle')
            rear_joints = ('LHip', 'LKnee', 'LAnkle')
        else:
            front_joints = ('LHip', 'LKnee', 'LAnkle')
            rear_joints = ('RHip', 'RKnee', 'RAnkle')
        
        # 角度計算
        front_angle = calculator.calculate_angle(
            keypoints[front_joints[0]], 
            keypoints[front_joints[1]], 
            keypoints[front_joints[2]]
        )
        
        rear_angle = calculator.calculate_angle(
            keypoints[rear_joints[0]], 
            keypoints[rear_joints[1]], 
            keypoints[rear_joints[2]]
        )
        
        # 前足股関節角度
        front_hip_angle = calculator.calculate_vector_angle_with_ground(
            keypoints[front_joints[0]], 
            keypoints[front_joints[1]]
        )
        
        return {
            'success': True,
            'front_angle': front_angle,
            'rear_angle': rear_angle,
            'front_hip_angle': front_hip_angle,
            'analysis_type': 'set'
        }
    
    elif analysis_mode == 'takeoff':
        # 飛び出し分析
        required_joints = ['C7', 'RHip', 'LHip', 'RAnkle', 'LAnkle']
        
        if not all(joint in keypoints for joint in required_joints):
            return {'error': '必要な関節点が不足しています'}
        
        # 前足の判定
        if keypoints['RAnkle']['x'] > keypoints['LAnkle']['x']:
            hip = keypoints['RHip']
            ankle = keypoints['RAnkle']
        else:
            hip = keypoints['LHip']
            ankle = keypoints['LAnkle']
        
        c7 = keypoints['C7']
        
        # 角度計算
        lower_angle = calculator.calculate_vector_angle_with_ground(hip, ankle)
        upper_angle = calculator.calculate_vector_angle_with_ground(c7, hip)
        kunoji_angle = calculator.calculate_angle(c7, hip, ankle)
        
        return {
            'success': True,
            'lower_angle': lower_angle,
            'upper_angle': upper_angle,
            'kunoji_angle': kunoji_angle,
            'analysis_type': 'takeoff'
        }

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """画像アップロード処理"""
    try:
        print("=== アップロードリクエスト受信 ===")
        
        if 'file' not in request.files:
            print("'file'フィールドがありません")
            return jsonify({'error': 'ファイルが選択されていません'})
        
        file = request.files['file']
        if file.filename == '':
            print("ファイル名が空です")
            return jsonify({'error': 'ファイルが選択されていません'})
        
        if file:
            # ファイル保存
            filename = 'uploaded_image.jpg'
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            print(f"ファイル保存完了: {filepath}")
            
            # 姿勢推定実行
            print("姿勢推定開始...")
            keypoints = detect_pose(filepath)
            
            if keypoints is None:
                print("姿勢推定失敗 - デフォルト関節点を使用")
                # デフォルト関節点を設定
                image = cv2.imread(filepath)
                h, w = image.shape[:2]
                
                keypoints = {
                    'LShoulder': {'x': w // 4, 'y': h // 4},
                    'RShoulder': {'x': (w * 3) // 4, 'y': h // 4},
                    'LHip': {'x': w // 3, 'y': h // 2},
                    'RHip': {'x': (w * 2) // 3, 'y': h // 2},
                    'LKnee': {'x': w // 3, 'y': (h * 3) // 4},
                    'RKnee': {'x': (w * 2) // 3, 'y': (h * 3) // 4},
                    'LAnkle': {'x': w // 3, 'y': h - 50},
                    'RAnkle': {'x': (w * 2) // 3, 'y': h - 50},
                    'C7': {'x': w // 2, 'y': h // 6}
                }
            else:
                print("姿勢推定成功")
            
            # 画像サイズ取得
            image = cv2.imread(filepath)
            h, w = image.shape[:2]
            
            print("アップロード処理完了")
            return jsonify({
                'success': True,
                'keypoints': keypoints,
                'image_url': f'/static/uploads/{filename}',
                'image_width': w,
                'image_height': h
            })
    
    except Exception as e:
        print(f"アップロードエラー: {str(e)}")
        return jsonify({'error': f'エラーが発生しました: {str(e)}'})

@app.route('/analyze', methods=['POST'])
def analyze():
    """姿勢分析処理"""
    try:
        data = request.get_json()
        keypoints = data.get('keypoints')
        analysis_mode = data.get('analysis_mode', 'set')
        
        if not keypoints:
            return jsonify({'error': '関節点データがありません'})
        
        result = analyze_posture(keypoints, analysis_mode)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': f'分析エラー: {str(e)}'})

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """アップロードされた画像を配信"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/test')
def test_endpoint():
    """テスト用エンドポイント"""
    return jsonify({
        'status': 'ok',
        'message': 'サーバーは正常に動作しています'
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
