from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    university = db.Column(db.String(100))
    faculty = db.Column(db.String(100))
    grade = db.Column(db.Integer)
    # ... id, email などの定義はそのまま ...
    classes = db.relationship('Class', backref='user', lazy=True, cascade="all, delete-orphan")
    tasks = db.relationship('Task', backref='user', lazy=True, cascade="all, delete-orphan") # この行を追加

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    teacher = db.Column(db.String(100))
    room = db.Column(db.String(100))
    period = db.Column(db.Integer, nullable=False) # 1-5限など
    day_of_week = db.Column(db.Integer, nullable=False) # 0:月, 1:火, ...
    attendances = db.relationship('Attendance', backref='class_obj', lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship('Review', backref='class_obj', lazy=True, cascade="all, delete-orphan")
    materials = db.relationship('Material', backref='class_obj', lazy=True, cascade="all, delete-orphan") # この行を追加

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False) # '出席', '欠席', '遅刻', '休講'

    # models.py の一番下に追加

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    # 評価項目
    difficulty = db.Column(db.Integer, nullable=False) # テストの難易度 (5段階)
    assignments = db.Column(db.Integer, nullable=False) # 課題の量 (5段階)
    interest = db.Column(db.Integer, nullable=False) # 内容の面白さ (5段階)
    comment = db.Column(db.Text, nullable=True) # コメント
    created_at = db.Column(db.DateTime, default=db.func.now()) # 投稿日時

    # models.py の一番下に追加

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=True) # 関連する授業 (任意)
    title = db.Column(db.String(200), nullable=False) # タスクの内容
    due_date = db.Column(db.Date, nullable=True) # 締切日
    completed = db.Column(db.Boolean, default=False) # 完了したかどうか
    
    # 授業との関連を定義 (TaskからClassの情報を参照しやすくするため)
    class_obj = db.relationship('Class', backref='tasks')


 # models.py の一番下に追加
class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False) # 保存するファイル名
    description = db.Column(db.String(200), nullable=True) # ファイルの説明（任意）
    uploaded_at = db.Column(db.DateTime, default=db.func.now())   