import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Class, Attendance, Review, Task, Material
import requests

# --- アプリケーションの初期設定 ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_change_this'

# --- 正しい順序 ---
# 1. 基準となるパス(basedir)を先に定義します
basedir = os.path.abspath(os.path.dirname(__file__))

# 2. basedir を使って、データベースとアップロードフォルダのパスを設定します
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')

# --- ここから下は変更なし ---
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt'}

# アップロードフォルダがなければ作成
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ユーザー認証関連のルート ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('timetable'))

    if request.method == 'POST':
        action = request.form.get('action')
        email = request.form.get('email')
        password = request.form.get('password')

        if action == 'register':
            user = User.query.filter_by(email=email).first()
            if user:
                flash('このメールアドレスは既に使用されています。', 'danger')
                return redirect(url_for('login'))
            new_user = User(email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('登録が完了しました。ログインしてください。', 'success')
            return redirect(url_for('login'))
        
        elif action == 'login':
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user, remember=True)
                return redirect(url_for('timetable'))
            else:
                flash('メールアドレスまたはパスワードが正しくありません。', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- メイン機能のルート ---
@app.route('/')
@login_required
def index():
    return redirect(url_for('timetable'))

# app.py の timetable 関数を置き換え

@app.route('/timetable', methods=['GET', 'POST'])
@login_required
def timetable():
    if request.method == 'POST':
        # (POST時の授業登録・編集ロジックは変更なし)
        class_id = request.form.get('class_id')
        class_name = request.form.get('name')
        teacher = request.form.get('teacher')
        room = request.form.get('room')
        period = request.form.get('period')
        day_of_week = request.form.get('day_of_week')

        if class_id:
            class_to_update = Class.query.get(class_id)
            if class_to_update and class_to_update.user_id == current_user.id:
                class_to_update.name = class_name
                class_to_update.teacher = teacher
                class_to_update.room = room
                class_to_update.period = period
                class_to_update.day_of_week = day_of_week
        else:
             new_class = Class(
                user_id=current_user.id, name=class_name, teacher=teacher,
                room=room, period=period, day_of_week=day_of_week
            )
             db.session.add(new_class)
        
        db.session.commit()
        return redirect(url_for('timetable'))

    # --- ここからGET時の処理（難易度計算を追加） ---
    
    # 1. 天気情報を取得
    weather_data = None
    try:
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        # ここに、先ほど取得したあなた自身のAPIキーを入力してください
        API_KEY = "5c61bab668d19b29574df8af9fc2b9df"
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        
        # 都市名を指定（例: 東京）
        city_name = "Tokyo"
        api_url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_KEY}&units=metric&lang=ja"
        
        response = requests.get(api_url)
        response.raise_for_status() # エラーがあれば例外を発生させる
        weather_data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"APIリクエストエラー: {e}")
    except Exception as e:
        print(f"予期せぬエラー: {e}")

    # 2. ユーザーの授業と時間割データを準備
    classes = Class.query.filter_by(user_id=current_user.id).all()
    timetable_data = [[None for _ in range(5)] for _ in range(5)]
    for c in classes:
        timetable_data[int(c.day_of_week)][int(c.period)-1] = c
    
    # 3. 出席難易度を計算
    difficulty_scores = {}
    if weather_data and date.today().weekday() < 5: # 天気情報があり、かつ平日である場合
        temp = weather_data['main']['temp']
        weather_main = weather_data['weather'][0]['main']
        
        for c in classes:
            # 今日の曜日と授業の曜日が一致する場合のみ計算
            if int(c.day_of_week) == date.today().weekday():
                score = 0
                # 時限による補正 (1限は+2)
                if int(c.period) == 1:
                    score += 2
                # 天気による補正 (雨や雪は+3)
                if weather_main in ["Rain", "Snow", "Drizzle", "Thunderstorm"]:
                    score += 3
                # 気温による補正 (10度未満は+2)
                if temp < 10:
                    score += 2
                
                # スコアに応じた難易度テキストを決定
                if score >= 5:
                    difficulty_text = "頑張りが必要"
                elif score >= 3:
                    difficulty_text = "やや大変"
                else:
                    difficulty_text = "楽勝！"
                
                difficulty_scores[c.id] = difficulty_text

    return render_template('timetable.html', timetable=timetable_data, difficulties=difficulty_scores)

@app.route('/class/delete/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_id):
    class_to_delete = Class.query.get(class_id)
    if class_to_delete and class_to_delete.user_id == current_user.id:
        db.session.delete(class_to_delete)
        db.session.commit()
    return redirect(url_for('timetable'))

# app.py の attendance 関数を置き換え

@app.route('/attendance/<int:class_id>', methods=['GET', 'POST'])
@login_required
def attendance(class_id):
    target_class = Class.query.get_or_404(class_id)
    if target_class.user_id != current_user.id:
        return redirect(url_for('timetable'))

    if request.method == 'POST':
        # --- フォームの種類を判定 ---
        if 'status' in request.form: # 出席登録フォーム
            # (省略) 以前の出席登録ロジックと同じ
            status = request.form.get('status')
            attendance_date = date.today()
            existing_attendance = Attendance.query.filter_by(class_id=class_id, date=attendance_date).first()
            if existing_attendance:
                existing_attendance.status = status
            else:
                new_attendance = Attendance(class_id=class_id, date=attendance_date, status=status)
                db.session.add(new_attendance)

        elif 'difficulty' in request.form: # 授業評価フォーム
            # (省略) 以前のレビュー投稿ロジックと同じ
            new_review = Review(
                class_id=class_id,
                difficulty=int(request.form.get('difficulty')),
                assignments=int(request.form.get('assignments')),
                interest=int(request.form.get('interest')),
                comment=request.form.get('comment')
            )
            db.session.add(new_review)

        elif 'material' in request.files: # ★★★ 資料アップロードフォームの場合 ★★★
            file = request.files['material']
            description = request.form.get('description')
            
            if file and file.filename != '' and allowed_file(file.filename):
                # ファイル名を安全な名前に変換
                filename = secure_filename(file.filename)
                # ファイルを UPLOAD_FOLDER に保存
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                # データベースに情報を保存
                new_material = Material(
                    class_id=class_id,
                    filename=filename,
                    description=description
                )
                db.session.add(new_material)
                flash('資料をアップロードしました。', 'success')
            else:
                flash('ファイルのアップロードに失敗しました。許可されている形式か確認してください。', 'danger')

        db.session.commit()
        return redirect(url_for('attendance', class_id=class_id))

    # --- GETリクエストの場合の処理 ---
    # (省略) 以前のコードから変更なし
    attendances = Attendance.query.filter_by(class_id=class_id).order_by(Attendance.date.desc()).all()
    reviews = Review.query.filter_by(class_id=class_id).order_by(Review.created_at.desc()).all()
    avg_scores = {'difficulty': 0, 'assignments': 0}
    if reviews:
        avg_scores['difficulty'] = sum(r.difficulty for r in reviews) / len(reviews)
        avg_scores['assignments'] = sum(r.assignments for r in reviews) / len(reviews)
    
    # ★★★ アップロードされた資料のリストを取得する処理を追加 ★★★
    materials = Material.query.filter_by(class_id=class_id).order_by(Material.uploaded_at.desc()).all()

    return render_template(
        'attendance.html',
        class_obj=target_class, 
        attendances=attendances, 
        today=date.today(),
        reviews=reviews,
        avg_scores=avg_scores,
        materials=materials # ★★★ 資料リストを渡す ★★★
    )

# app.py の一番下に追加（if __name__ ... の前に）
from datetime import datetime

@app.route('/todo', methods=['GET', 'POST'])
@login_required
def todo():
    if request.method == 'POST':
        title = request.form.get('title')
        due_date_str = request.form.get('due_date')
        class_id = request.form.get('class_id')

        new_task = Task(
            user_id=current_user.id,
            title=title
        )
        if due_date_str:
            new_task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        if class_id:
            new_task.class_id = int(class_id)
        
        db.session.add(new_task)
        db.session.commit()
        flash('新しいタスクを追加しました。', 'success')
        return redirect(url_for('todo'))

    # GETリクエストの場合
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.due_date.asc()).all()
    classes = Class.query.filter_by(user_id=current_user.id).order_by(Class.name.asc()).all()
    return render_template('todo.html', tasks=tasks, classes=classes)

@app.route('/todo/toggle/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    task.completed = not task.completed
    db.session.commit()
    return jsonify({'success': True, 'completed': task.completed})

@app.route('/todo/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return redirect(url_for('todo'))
        
    db.session.delete(task)
    db.session.commit()
    flash('タスクを削除しました。', 'info')
    return redirect(url_for('todo'))

# app.py の一番下に追加（if __name__ ... の前に）

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- アプリケーションの実行 ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # データベースファイルがなければ作成
    app.run(debug=True)