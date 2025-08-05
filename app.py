from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import math
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# アップロードフォルダの作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("アップロードリクエスト受信")
    
    if 'file' not in request.files:
        print("fileフィールドがありません")
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("ファイル名が空です")
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # ファイルを保存
            filename = secure_filename(file.filename)
            if not filename:
                filename = 'uploaded_image.jpg'
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            print(f"ファイル保存: {filepath}")
            
            # 画像サイズを取得
            with Image.open(filepath) as img:
                width, height = img.size
            
            # デフォルトの関節点位置を設定
            default_points = {
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
            
            return jsonify({
                'success': True,
                'filename': filename,
                'keypoints': default_points,
                'image_url': f'/static/uploads/{filename}',
                'image_width': width,
                'image_height': height
            })
            
        except Exception as e:
            print(f"エラー: {e}")
            return jsonify({'error': f'処理エラー: {str(e)}'}), 500
    
    return jsonify({'error': '無効なファイル形式です。JPG、PNG、WEBP形式をサポートしています。'}), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    keypoints = data.get('keypoints', {})
    mode = data.get('mode', 'set')
    
    # ダミー分析結果を返す
    if mode == 'set':
        return jsonify({
            'success': True,
            'front_angle': 90.5,
            'rear_angle': 130.2,
            'front_hip_angle': 45.8
        })
    else:
        return jsonify({
            'success': True,
            'lower_angle': 42.1,
            'upper_angle': 38.6,
            'kunoji_angle': 155.3
        })

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
