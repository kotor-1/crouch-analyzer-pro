from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB制限

# アップロードフォルダの作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # ファイル保存
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 画像サイズ取得
            with Image.open(filepath) as img:
                width, height = img.size
            
            # デフォルト関節点の設定
            keypoints = {
                'LShoulder': {'x': width//4, 'y': height//4},
                'RShoulder': {'x': width*3//4, 'y': height//4},
                'C7': {'x': width//2, 'y': height//5},
                'LHip': {'x': width//3, 'y': height//2},
                'RHip': {'x': width*2//3, 'y': height//2},
                'LKnee': {'x': width//3, 'y': height*3//4},
                'RKnee': {'x': width*2//3, 'y': height*3//4},
                'LAnkle': {'x': width//3, 'y': height-50},
                'RAnkle': {'x': width*2//3, 'y': height-50}
            }
            
            return jsonify({
                'success': True,
                'filename': filename,
                'keypoints': keypoints,
                'image_url': f'/static/uploads/{filename}',
                'image_width': width,
                'image_height': height
            })
            
        except Exception as e:
            return jsonify({'error': f'Error: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file format. Supported: JPG, PNG'}), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        keypoints = data.get('keypoints', {})
        mode = data.get('analysis_mode', 'set')
        
        # ダミー分析結果
        if mode == 'set':
            return jsonify({
                'success': True, 
                'front_angle': 95.5,
                'rear_angle': 120.2,
                'front_hip_angle': 45.8,
                'analysis_type': 'set'
            })
        else:
            return jsonify({
                'success': True,
                'lower_angle': 42.1,
                'upper_angle': 38.6,
                'kunoji_angle': 155.3,
                'analysis_type': 'takeoff'
            })
            
    except Exception as e:
        return jsonify({'error': f'Analysis error: {str(e)}'}), 500

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
