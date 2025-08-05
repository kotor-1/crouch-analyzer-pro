from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import math
from PIL import Image
from werkzeug.utils import secure_filename

# デバッグ情報の出力
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Directory listing: {os.listdir('.')}")

# アプリケーション初期化
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB制限
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# アップロードフォルダの作成と権限確認
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print(f"Upload folder created/exists: {app.config['UPLOAD_FOLDER']}")
    print(f"Upload folder is writable: {os.access(app.config['UPLOAD_FOLDER'], os.W_OK)}")
    print(f"Upload folder contents: {os.listdir(app.config['UPLOAD_FOLDER']) if os.path.exists(app.config['UPLOAD_FOLDER']) else 'not exists'}")
except Exception as e:
    print(f"Error with upload folder: {str(e)}")

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
    print("=== アップロードリクエスト受信 ===")
    print(f"リクエストメソッド: {request.method}")
    print(f"リクエストファイル: {list(request.files.keys()) if request.files else 'なし'}")
    print(f"リクエストフォーム: {list(request.form.keys()) if request.form else 'なし'}")
    
    if 'file' not in request.files:
        print("'file'フィールドがありません")
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    print(f"ファイル: {file}, 名前: {file.filename}, タイプ: {file.content_type if hasattr(file, 'content_type') else 'unknown'}")
    
    if file.filename == '':
        print("ファイル名が空です")
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # ファイル保存
            filename = secure_filename(file.filename)
            if not filename:
                filename = 'uploaded_image.jpg'
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"保存先パス: {filepath}")
            file.save(filepath)
            print(f"ファイル保存完了: {filename}")
            
            # ファイル存在確認
            if not os.path.exists(filepath):
                print(f"エラー: ファイルが見つかりません: {filepath}")
                return jsonify({'error': 'ファイルの保存に失敗しました'}), 500
                
            print(f"ファイルサイズ: {os.path.getsize(filepath)} bytes")
            
            # 画像サイズ取得
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
                keypoints_data = {
                    'LShoulder': {'x': width // 4, 'y': height // 4},
                    'RShoulder': {'x': (width * 3) // 4, 'y': height // 4},
                    'LHip': {'x': width // 3, 'y': height // 2},
                    'RHip': {'x': (width * 2) // 3, 'y': height // 2},
                    'LKnee': {'x': width // 3, 'y': (height * 3) // 4},
                    'RKnee': {'x': (width * 2) // 3, 'y': (height * 3) // 4},
                    'LAnkle': {'x': width // 3, 'y': height - 50},
                    'RAnkle': {'x': (width * 2) // 3, 'y': height - 50},
                    'C7': {'x': width // 2, 'y': height // 6}
                }
            
            result = {
                'success': True,
                'filename': filename,
                'keypoints': keypoints_data,
                'image_url': f'/static/uploads/{filename}',
                'image_width': width,
                'image_height': height,
                'ai_detection_used': ai_detection_used
            }
            
            print(f"レスポンス: {result}")
            return jsonify(result)
            
        except Exception as e:
            print(f"エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'処理中にエラーが発生しました: {str(e)}'}), 500
    
    print("無効なファイル形式")
    return jsonify({'error': '無効なファイル形式です。JPG、PNG、WEBP形式をサポートしています。'}), 400

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

@app.route('/simple')
def simple_form():
    return render_template('simple_upload.html')

@app.route('/simple_upload', methods=['POST'])
def simple_upload():
    print("=== シンプルアップロードリクエスト ===")
    print(f"リクエストファイル: {list(request.files.keys()) if request.files else 'なし'}")
    
    if 'file' not in request.files:
        return "ファイルが選択されていません"
    
    file = request.files['file']
    if file.filename == '':
        return "ファイル名が空です"
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        return f"ファイル {filename} をアップロードしました。<br><img src='/static/uploads/{filename}' style='max-width: 500px'>"
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"エラーが発生しました: {str(e)}<br><pre>{error_details}</pre>"

@app.route('/test')
def test_endpoint():
    """簡単なテスト用エンドポイント"""
    try:
        # 基本的な情報収集
        info = {
            'python_version': sys.version,
            'current_directory': os.getcwd(),
            'upload_folder': app.config['UPLOAD_FOLDER'],
            'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
            'upload_folder_writable': os.access(app.config['UPLOAD_FOLDER'], os.W_OK) if os.path.exists(app.config['UPLOAD_FOLDER']) else False,
        }
        
        # テストファイルの作成を試みる
        test_file = os.path.join(app.config['UPLOAD_FOLDER'], 'test.txt')
        with open(test_file, 'w') as f:
            f.write('Test file to check write permissions')
        info['test_file_created'] = os.path.exists(test_file)
        
        return jsonify({
            'status': 'success',
            'message': 'Basic functionality test passed',
            'system_info': info
        })
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'message': f'Test failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
