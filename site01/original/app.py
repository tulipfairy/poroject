from flask import Flask, redirect, render_template, request, url_for, session, flash
from datetime import datetime
import mysql.connector
import os
from models import PostsMansger
from functools import wraps
# import bcrypt
# from werkzeug.security import generate_password_hash


app = Flask(__name__)

# 비밀 키 설정 (세션을 사용하려면 필요)
app.secret_key = 'your_secret_key'

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

mana = PostsMansger()

# 간단한 사용자 예시 (실제 서비스에서는 데이터베이스 사용)
users = {'user1': 'password123', 'user2': 'mypassword'}

# 로그인 여부를 확인하는 데코레이터
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('user_id'):  # 세션에 user_id가 없는 경우 (로그인 안됨)
            flash('로그인이 필요합니다.', 'error')
            return redirect(url_for('login'))  # 로그인 화면으로 리디렉션
        return view_func(*args, **kwargs)  # 로그인된 경우 뷰 실행
    return wrapped_view

@app.route('/')
def index():
    posts = mana.all_posts()
    return render_template('index.html', posts=posts)

@app.route('/post/<int:id>')
def view_post(id):
    # 로그인이 되어있지 않은 경우 로그인 화면으로 이동
    if not session.get('user_id'):
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('login'))

    # 로그인이 되어 있는 경우 게시글 보기
    try:
        mana.connect()
        sql = "SELECT * FROM posts WHERE id = %s"
        mana.cursor.execute(sql, (id,))
        post = mana.cursor.fetchone()

        if not post:
            flash('게시글을 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))

        return render_template('view.html', post=post)
    except mysql.connector.Error as error:
        print(f"게시글 조회 실패: {error}")
        flash('게시글을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))
    finally:
        mana.disconnect()

@app.route('/post/add', methods=['GET', 'POST'])
@login_required  # 로그인된 사용자만 접근 가능
def add_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        file = request.files.get('file')
        filename = file.filename if file else None

        if filename:
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)

        # 필수 입력값 확인
        if not title or not content:
            flash('제목과 내용을 입력해주세요.', 'error')
            return redirect(url_for('add_post'))

        user_id = session['user_id']  # 세션에서 사용자 ID 가져오기

        # 데이터베이스에 게시글 추가
        try:
            mana.connect()
            sql = """
                INSERT INTO posts (title, content, user_id, filename, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
            """
            mana.cursor.execute(sql, (title, content, user_id, filename))
            mana.connection.commit()
            flash('글이 성공적으로 작성되었습니다.', 'success')
            return redirect(url_for('index'))
        except mysql.connector.Error as error:
            print(f"게시글 추가 실패: {error}")
            flash('글 작성 중 오류가 발생했습니다.', 'error')
        finally:
            mana.disconnect()

    return render_template('add.html')


@app.route('/post/edit/<int:id>', methods=['GET', 'POST'])
def edit_post(id):
    if 'user_id' not in session:
        flash('로그인 후 게시글을 수정할 수 있습니다.', 'error')
        return redirect(url_for('login'))  # 로그인하지 않으면 로그인 페이지로 리다이렉트

    try:
        mana.connect()
        # 게시글 조회 (user_id를 가져옴)
        sql = "SELECT id, title, content, user_id FROM posts WHERE id = %s"
        mana.cursor.execute(sql, (id,))
        post = mana.cursor.fetchone()

        if not post:
            flash('게시글을 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))

        # user_id로 작성자 정보를 조회
        user_sql = "SELECT id, uname FROM users WHERE user_id = %s"
        mana.cursor.execute(user_sql, (post['user_id'],))
        user = mana.cursor.fetchone()

        if not user:
            flash('작성자를 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))

        # 게시글 작성자가 아니면 수정할 수 없도록 제한
        if post['user_id'] != session['user_id']:
            flash('자신이 작성한 게시글만 수정할 수 있습니다.', 'error')
            return redirect(url_for('index'))

    except mysql.connector.Error as error:
        print(f"게시글 조회 실패: {error}")
        flash('게시글을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))
    finally:
        mana.disconnect()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        visit = request.form.get('visit', 0)  # 기본값 0으로 설정
        user_id = session['user_id']  # author 대신 user_id 사용설정
        
        file = request.files['file']
        filename = file.filename if file else None

        if filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        if mana.update_post(id, title, content, filename, visit, user_id):
            return redirect('/')
        return "게시글 수정 실패", 400

    return render_template('edit.html', post=post, user=user)

@app.route('/post/delete/<int:id>')
def delete_post(id):
    if 'user_id' not in session:
        flash('로그인 후 게시글을 삭제할 수 있습니다.', 'error')
        return redirect(url_for('login'))  # 로그인하지 않으면 로그인 페이지로 리다이렉트

    post = mana.get_post_by_id(id)
    if not post:
        return "게시글을 찾을 수 없습니다.", 404

    # 게시글 작성자가 아니면 삭제할 수 없도록 제한
    if post['user_id'] != session['user_id']:
        flash('자신이 작성한 게시글만 삭제할 수 있습니다.', 'error')
        return redirect(url_for('index'))

    if mana.delete_post(id):
        return redirect(url_for('index'))
    return "게시글 삭제 실패", 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']  # `uid`를 `user_id`로 변경
        pwd = request.form['password']

        # 데이터베이스에서 사용자 정보를 가져옴
        try:
            mana.connect()
            sql = "SELECT * FROM users WHERE user_id = %s"  # `uid`를 `user_id`로 변경
            mana.cursor.execute(sql, (user_id,))
            user = mana.cursor.fetchone()
        except mysql.connector.Error as error:
            print(f"사용자 확인 실패: {error}")
            flash('오류가 발생했습니다. 다시 시도해주세요.', 'error')
            return redirect(url_for('login'))  # 오류 발생 시 로그인 페이지로 리다이렉트
        finally:
            mana.disconnect()

        # 사용자와 비밀번호가 일치하는지 텍스트로 비교
        if user and user['pwd'] == pwd:  # 비밀번호 확인
            session['user_id'] = user['user_id']  # `uid`를 `user_id`로 변경
            session['user'] = user['uname']  # 세션에 사용자 이름 저장
            flash('로그인 성공!', 'success')
            return redirect(url_for('index'))  # 로그인 성공 후 홈 페이지로 리다이렉트
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
            return redirect(url_for('login'))  # 로그인 실패 시 로그인 페이지로 리다이렉트

    return render_template('login.html')  # GET 요청 시 로그인 페이지 렌더링


@app.route('/logout')
def logout():
    # 세션 초기화 (로그아웃)
    session.clear()
    flash('로그아웃 되었습니다.', 'success')
    return redirect(url_for('index'))  # 홈 페이지로 리다이렉트

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 폼 데이터 가져오기
        user_id = request.form.get('user_id')  # `uid`를 `user_id`로 변경
        pwd = request.form.get('password')
        email = request.form.get('email')
        uname = request.form.get('username')

        # 필수 입력값 확인
        if not user_id or not pwd or not email or not uname:
            flash('모든 필드를 입력해주세요.', 'error')
            return redirect(url_for('register'))

        # 중복 사용자 확인
        try:
            mana.connect()
            sql = "SELECT * FROM users WHERE user_id = %s"  # `uid`를 `user_id`로 변경
            mana.cursor.execute(sql, (user_id,))
            existing_user = mana.cursor.fetchone()
        except mysql.connector.Error as error:
            print(f"사용자 확인 실패: {error}")
            flash('오류가 발생했습니다. 다시 시도해주세요.', 'error')
            return redirect(url_for('register'))
        finally:
            mana.disconnect()

        # 중복 사용자 처리
        if existing_user:
            flash('이미 존재하는 아이디입니다.', 'error')
            return redirect(url_for('register'))

        # 새 사용자 추가 (비밀번호 해싱 없이 저장)
        try:
            mana.connect()
            sql = """
                INSERT INTO users (user_id, uname, pwd, email, created_at) 
                VALUES (%s, %s, %s, %s, NOW())
            """  # `uid`를 `user_id`로 변경
            mana.cursor.execute(sql, (user_id, uname, pwd, email))
            mana.connection.commit()
            flash('회원가입 성공! 로그인해주세요.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as error:
            print(f"회원가입 실패: {error}")
            flash('회원가입에 실패했습니다. 다시 시도해주세요.', 'error')
        finally:
            mana.disconnect()

    return render_template('register.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5003, debug=True)
