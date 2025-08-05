from flask import Flask, render_template, request, jsonify, send_from_directory
import math
from PIL import Image
import io
import base64
import os
import sys
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# アップロードフォルダが存在しない場合は作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 依存関係が失敗してもアプリが動作するように修正
DEPENDENCIES_AVAILABLE = True
try:
    import cv2
    import mediapipe as mp
    import numpy as np
    print("✅ All dependencies loaded successfully")
    
    # MediaPipe姿勢推定の初期化
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
    MEDIAPIPE_AVAILABLE = True
    print("✅ MediaPipe initialized successfully")
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    MEDIAPIPE_AVAILABLE = False
    print(f"⚠️ Dependencies not available: {e}")
    print("🔧 Running in basic mode - manual joint point setting will be available")
    # 基本機能のみで動作させる
    cv2 = None
    mp = None
    pose = None
    np = None

# MediaPipe landmark indices to frontend joint mapping
MEDIAPIPE_TO_FRONTEND = {
    11: 'LShoulder',  # 左肩
    12: 'RShoulder',  # 右肩
    23: 'LHip',       # 左腰
    24: 'RHip',       # 右腰
    25: 'LKnee',      # 左膝
    26: 'RKnee',      # 右膝
    27: 'LAnkle',     # 左足首
    28: 'RAnkle',     # 右足首
    0: 'C7'           # 鼻（第7頸椎の代用）
}

# Default joint positions for when MediaPipe is not available
DEFAULT_JOINTS = {
    'LShoulder': {'x': 150, 'y': 100},
    'RShoulder': {'x': 250, 'y': 100},
    'LHip': {'x': 170, 'y': 200},
    'RHip': {'x': 230, 'y': 200},
    'LKnee': {'x': 180, 'y': 300},
    'RKnee': {'x': 220, 'y': 300},
    'LAnkle': {'x': 190, 'y': 400},
    'RAnkle': {'x': 210, 'y': 400},
    'C7': {'x': 200, 'y': 50}
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def calculate_angle(point1, point2, point3):
    """3点から角度を計算する関数"""
    try:
        # ベクトルを計算
        vector1 = [point1[0] - point2[0], point1[1] - point2[1]]
        vector2 = [point3[0] - point2[0], point3[1] - point2[1]]
        
        # 内積を計算
        if DEPENDENCIES_AVAILABLE and np is not None:
            # numpy利用可能な場合
            vector1 = np.array(vector1)
            vector2 = np.array(vector2)
            dot_product = np.dot(vector1, vector2)
            magnitude1 = np.linalg.norm(vector1)
            magnitude2 = np.linalg.norm(vector2)
        else:
            # numpy無しの基本計算
            dot_product = vector1[0] * vector2[0] + vector1[1] * vector2[1]
            magnitude1 = math.sqrt(vector1[0]**2 + vector1[1]**2)
            magnitude2 = math.sqrt(vector2[0]**2 + vector2[1]**2)
        
        # ゼロ除算を避ける
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        # cosθを計算
        cos_theta = dot_product / (magnitude1 * magnitude2)
        
        # 数値誤差を修正（-1から1の範囲に制限）
        cos_theta = max(-1.0, min(1.0, cos_theta))
        
        # 角度を計算（ラジアンから度に変換）
        angle = math.degrees(math.acos(cos_theta))
        
        return round(angle, 1)
    except Exception as e:
        print(f"⚠️ Angle calculation error: {e}")
        return 0

def analyze_crouch_angles(keypoints, analysis_type="set"):
    """クラウチングスタートの角度分析を行う"""
    analysis_result = {}
    
    try:
        if analysis_type == "set":
            # セット姿勢の分析
            # 前足の膝角度（左膝を前足と仮定）
            if all(joint in keypoints for joint in ['LHip', 'LKnee', 'LAnkle']):
                hip = keypoints['LHip']
                knee = keypoints['LKnee']
                ankle = keypoints['LAnkle']
                front_angle = calculate_angle([hip['x'], hip['y']], [knee['x'], knee['y']], [ankle['x'], ankle['y']])
                analysis_result['front_angle'] = front_angle
            
            # 後足の膝角度（右膝を後足と仮定）
            if all(joint in keypoints for joint in ['RHip', 'RKnee', 'RAnkle']):
                hip = keypoints['RHip']
                knee = keypoints['RKnee']
                ankle = keypoints['RAnkle']
                rear_angle = calculate_angle([hip['x'], hip['y']], [knee['x'], knee['y']], [ankle['x'], ankle['y']])
                analysis_result['rear_angle'] = rear_angle
            
            # 前足股関節角度
            if all(joint in keypoints for joint in ['LShoulder', 'LHip', 'LKnee']):
                shoulder = keypoints['LShoulder']
                hip = keypoints['LHip']
                knee = keypoints['LKnee']
                front_hip_angle = calculate_angle([shoulder['x'], shoulder['y']], [hip['x'], hip['y']], [knee['x'], knee['y']])
                analysis_result['front_hip_angle'] = front_hip_angle
                
        elif analysis_type == "takeoff":
            # 飛び出し分析
            # 下半身角度（腰-膝-足首）
            if all(joint in keypoints for joint in ['LHip', 'LKnee', 'LAnkle']):
                hip = keypoints['LHip']
                knee = keypoints['LKnee']
                ankle = keypoints['LAnkle']
                lower_angle = calculate_angle([hip['x'], hip['y']], [knee['x'], knee['y']], [ankle['x'], ankle['y']])
                analysis_result['lower_angle'] = lower_angle
            
            # 上半身角度（肩-腰-膝）
            if all(joint in keypoints for joint in ['LShoulder', 'LHip', 'LKnee']):
                shoulder = keypoints['LShoulder']
                hip = keypoints['LHip']
                knee = keypoints['LKnee']
                upper_angle = calculate_angle([shoulder['x'], shoulder['y']], [hip['x'], hip['y']], [knee['x'], knee['y']])
                analysis_result['upper_angle'] = upper_angle
            
            # くの字角度（肩-腰-足首）
            if all(joint in keypoints for joint in ['LShoulder', 'LHip', 'LAnkle']):
                shoulder = keypoints['LShoulder']
                hip = keypoints['LHip']
                ankle = keypoints['LAnkle']
                kunoji_angle = calculate_angle([shoulder['x'], shoulder['y']], [hip['x'], hip['y']], [ankle['x'], ankle['y']])
                analysis_result['kunoji_angle'] = kunoji_angle
        
        analysis_result['analysis_type'] = analysis_type
        return analysis_result
        
    except Exception as e:
        return {'error': f'角度計算エラー: {str(e)}', 'analysis_type': analysis_type}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # デバッグ出力を追加
    print("=== アップロードリクエスト受信 ===")
    print(f"リクエストファイル: {list(request.files.keys())}")
    print(f"アップロードフォルダ: {app.config['UPLOAD_FOLDER']}")
    
    # アップロードフォルダの再確認
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        print(f"アップロードフォルダ作成/確認完了: {app.config['UPLOAD_FOLDER']}")
    except Exception as e:
        print(f"フォルダ作成エラー: {str(e)}")
        return jsonify({'error': f'アップロードフォルダの作成に失敗しました: {str(e)}'}), 500
    
    if 'file' not in request.files:
        print("'file'フィールドが見つかりません")
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("ファイル名が空です")
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    print(f"ファイル名: {file.filename}, タイプ: {file.content_type}")
    
    if file and allowed_file(file.filename):
        try:
            # ファイルを保存
            filename = secure_filename(file.filename)
            if not filename:
                filename = 'uploaded_image.jpg'
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"保存先パス: {filepath}")
            file.save(filepath)
            print(f"ファイル保存完了: {filename}")
            
            # ファイルの存在確認
            if not os.path.exists(filepath):
                print(f"エラー: 保存したファイルが見つかりません: {filepath}")
                return jsonify({'error': 'ファイルの保存に失敗しました'}), 500
            
            # 画像の情報を取得
            with Image.open(filepath) as img:
                width, height = img.size
                print(f"画像サイズ: {width}x{height}")
            
            keypoints_data = {}
            ai_detection_used = False
            
            if MEDIAPIPE_AVAILABLE and cv2 is not None:
                # MediaPipeで姿勢推定
                try:
                    print("MediaPipeで姿勢推定を開始...")
                    image = cv2.imread(filepath)
                    if image is not None:
                        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        results = pose.process(image_rgb)
                        
                        if results.pose_landmarks:
                            # MediaPipeの関節点をフロントエンド形式に変換
                            for mp_idx, frontend_name in MEDIAPIPE_TO_FRONTEND.items():
                                if mp_idx < len(results.pose_landmarks.landmark):
                                    landmark = results.pose_landmarks.landmark[mp_idx]
                                    x = int(landmark.x * width)
                                    y = int(landmark.y * height)
                                    keypoints_data[frontend_name] = {'x': x, 'y': y}
                            ai_detection_used = True
                            print(f"✅ AI姿勢検出成功: {len(keypoints_data)}個の関節点を検出")
                        else:
                            print("⚠️ MediaPipeがランドマークを検出できませんでした")
                except Exception as e:
                    print(f"⚠️ AI姿勢検出失敗: {e}")
            
            # MediaPipeが利用できない場合またはランドマークが検出されない場合のデフォルト
            if not keypoints_data:
                print("🔧 デフォルト関節点位置を使用します")
                # デフォルトの関節点位置を画像サイズに合わせてスケール
                scale_x = width / 400  # 基準サイズ400px
                scale_y = height / 500  # 基準サイズ500px
                
                for joint_name, default_pos in DEFAULT_JOINTS.items():
                    keypoints_data[joint_name] = {
                        'x': int(default_pos['x'] * scale_x),
                        'y': int(default_pos['y'] * scale_y)
                    }
            
            result = {
                'success': True,
                'filename': filename,
                'keypoints': keypoints_data,
                'image_url': f'/static/uploads/{filename}',
                'image_width': width,
                'image_height': height,
                'ai_detection_used': ai_detection_used,
                'detection_method': 'AI pose detection' if ai_detection_used else 'Default positions (manual adjustment recommended)',
                'dependencies_available': DEPENDENCIES_AVAILABLE
            }
            
            print(f"アップロード処理完了: {result['image_url']}")
            return jsonify(result)
            
        except Exception as e:
            print(f"⚠️ 画像処理中にエラー: {str(e)}")
            return jsonify({'error': f'画像処理中にエラーが発生しました: {str(e)}'}), 500
    
    print(f"⚠️ 無効なファイル形式: {file.filename}")
    return jsonify({'error': '無効なファイル形式です。JPG, PNG, WEBP形式をサポートしています。'}), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        keypoints = data.get('keypoints', {})
        analysis_mode = data.get('analysis_mode', 'set')
        
        result = analyze_crouch_angles(keypoints, analysis_mode)
        return jsonify({'success': True, **result})
        
    except Exception as e:
        return jsonify({'error': f'分析中にエラーが発生しました: {str(e)}'}), 500

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/share/<analysis_id>')
def share_analysis(analysis_id):
    """チーム共有用のURL"""
    # 実際の実装では分析結果をデータベースに保存し、analysis_idで取得
    # ここではデモ用に基本ページを返す
    return render_template('index.html', shared_analysis_id=analysis_id)

@app.route('/api/test')
def test_endpoint():
    """テスト用エンドポイント - 基本機能の動作確認"""
    try:
        # Test basic functionality
        test_keypoints = {
            'LShoulder': {'x': 150, 'y': 100},
            'LHip': {'x': 170, 'y': 200},
            'LKnee': {'x': 180, 'y': 300},
            'LAnkle': {'x': 190, 'y': 400}
        }
        
        # Test angle calculation
        test_angle = calculate_angle([150, 100], [170, 200], [180, 300])
        
        # Test analysis
        analysis_result = analyze_crouch_angles(test_keypoints, "set")
        
        return jsonify({
            'status': 'success',
            'message': 'Basic functionality test passed',
            'dependencies_available': DEPENDENCIES_AVAILABLE,
            'mediapipe_available': MEDIAPIPE_AVAILABLE,
            'test_results': {
                'angle_calculation': test_angle,
                'analysis_function': analysis_result,
                'default_joints_available': len(DEFAULT_JOINTS) > 0
            },
            'deployment_info': {
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'app_mode': 'AI-enabled' if DEPENDENCIES_AVAILABLE else 'Basic mode'
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Test failed: {str(e)}',
            'dependencies_available': DEPENDENCIES_AVAILABLE,
            'mediapipe_available': MEDIAPIPE_AVAILABLE
        }), 500

@app.route('/test_upload')
def test_upload_page():
    """シンプルなアップロードテスト用ページ"""
    return render_template('test_upload.html')

@app.route('/api/health')
def health_check():
    """ヘルスチェック用エンドポイント"""
    status_info = {
        'status': 'healthy',
        'dependencies_available': DEPENDENCIES_AVAILABLE,
        'mediapipe_available': MEDIAPIPE_AVAILABLE,
        'version': '1.0.0',
        'features': {
            'manual_joint_setting': True,  # 常に利用可能
            'ai_pose_detection': MEDIAPIPE_AVAILABLE,
            'angle_analysis': True  # numpy非依存の基本計算は常に利用可能
        }
    }
    
    if not DEPENDENCIES_AVAILABLE:
        status_info['message'] = 'Running in basic mode - AI features disabled'
    else:
        status_info['message'] = 'All features available'
    
    return jsonify(status_info)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
