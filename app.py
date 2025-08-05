# app.pyに追加
@app.route('/simple', methods=['GET'])
def simple_form():
    return render_template('simple_upload.html')

@app.route('/simple_upload', methods=['POST'])
def simple_upload():
    print("=== シンプルアップロードリクエスト ===")
    print(f"リクエストファイル: {list(request.files.keys())}")
    
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
        return f"エラーが発生しました: {str(e)}"
