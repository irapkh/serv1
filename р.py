from flask import Flask, render_template, request, redirect, url_for, session
import numpy as np
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
import io
import base64
import sqlite3
import hashlib
import warnings
from functools import wraps
from datetime import datetime

warnings.filterwarnings('ignore')

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_123456789'


# === РАБОТА С БАЗОЙ ДАННЫХ ===

def init_db():
    """Создаёт базу данных пользователей"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def hash_password(password):
    """Хеширует пароль"""
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(password, hashed):
    """Проверяет пароль"""
    return hash_password(password) == hashed


# Инициализируем базу данных
init_db()


# === ДЕКОРАТОР ДЛЯ ЗАЩИТЫ СТРАНИЦ ===

def login_required(f):
    """Декоратор - требует авторизации для доступа к странице"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('welcome'))
        return f(*args, **kwargs)

    return decorated_function


# === СТРАНИЦЫ АВТОРИЗАЦИИ ===

@app.route('/welcome')
def welcome():
    """Начальная страница с кнопками Войти и Зарегистрироваться"""
    # Если пользователь уже авторизован, отправляем на главную
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('welcome.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации с 3 полями: nickname, password, was born"""
    error = None

    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')
        birth_date = request.form.get('birth_date', '')

        # Проверки
        if not nickname or not password or not birth_date:
            error = 'Пожалуйста, заполните все поля'
        elif len(password) < 4:
            error = 'Пароль должен содержать минимум 4 символа'
        else:
            try:
                # Проверяем корректность даты
                datetime.strptime(birth_date, '%Y-%m-%d')

                conn = sqlite3.connect('users.db')
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (nickname, password, birth_date) VALUES (?, ?, ?)',
                    (nickname, hash_password(password), birth_date)
                )
                conn.commit()
                conn.close()

                # После успешной регистрации перенаправляем на страницу входа
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = 'Пользователь с таким nickname уже существует'
            except ValueError:
                error = 'Неверный формат даты (используйте ГГГГ-ММ-ДД)'

    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа с 2 полями: nickname, password"""
    error = None

    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, nickname, password FROM users WHERE nickname = ?', (nickname,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password(password, user[2]):
            session['user_id'] = user[0]
            session['nickname'] = user[1]
            return redirect(url_for('index'))
        else:
            error = 'Неверный nickname или пароль'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    return redirect(url_for('welcome'))


# === ОСНОВНЫЕ СТРАНИЦЫ ПРИЛОЖЕНИЯ (с защитой) ===

def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)
    return img_base64


@app.route('/')
@login_required
def index():
    """Главная страница приложения после входа"""
    return render_template('index.html', nickname=session.get('nickname'))


@app.route('/linear', methods=['GET', 'POST'])
@login_required
def linear():
    image = None
    k = b = None
    error = None

    if request.method == 'POST':
        try:
            k = float(request.form.get('k', 2))
            b = float(request.form.get('b', 3))

            x = np.linspace(-10, 10, 100)
            y = k * x + b

            fig = Figure(figsize=(10, 6))
            ax = fig.add_subplot(111)
            ax.plot(x, y, 'b-', linewidth=2)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(-10, 10)
            ax.set_ylim(-10, 10)
            ax.axhline(y=0, color='k', linewidth=0.5)
            ax.axvline(x=0, color='k', linewidth=0.5)
            ax.set_title(f'Линейная функция: y = {k}x + {b}', fontsize=14, fontweight='bold')
            ax.set_xlabel('x')
            ax.set_ylabel('y')

            image = fig_to_base64(fig)
        except Exception as e:
            error = str(e)

    return render_template('linear.html', image=image, k=k, b=b, error=error, nickname=session.get('nickname'))


@app.route('/function', methods=['GET', 'POST'])
@login_required
def function_page():
    image = None
    func_str = 'sin(x)'
    error = None

    if request.method == 'POST':
        try:
            func_str = request.form.get('function', 'sin(x)')
            x = np.linspace(-10, 10, 1000)

            safe_dict = {
                'x': x,
                'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
                'atan': np.arctan, 'arcsin': np.arcsin, 'arccos': np.arccos,
                'abs': np.abs, 'sqrt': np.sqrt, 'exp': np.exp, 'log': np.log,
                'pi': np.pi
            }

            with np.errstate(divide='ignore', invalid='ignore'):
                y = eval(func_str, {"__builtins__": {}}, safe_dict)
                y = np.where(np.abs(y) > 50, np.nan, y)

            fig = Figure(figsize=(10, 6))
            ax = fig.add_subplot(111)
            ax.plot(x, y, 'r-', linewidth=2)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(-10, 10)
            ax.set_ylim(-10, 10)
            ax.axhline(y=0, color='k', linewidth=0.5)
            ax.axvline(x=0, color='k', linewidth=0.5)
            ax.set_title(f'График функции: {func_str}', fontsize=14, fontweight='bold')
            ax.set_xlabel('x')
            ax.set_ylabel('y')

            image = fig_to_base64(fig)
        except Exception as e:
            error = str(e)

    return render_template('function.html', image=image, func_str=func_str, error=error,
                           nickname=session.get('nickname'))


@app.route('/cardioid', methods=['GET', 'POST'])
@login_required
def cardioid():
    image = None
    size = power_x = power_y = None
    error = None

    if request.method == 'POST':
        try:
            size = float(request.form.get('size', 2))
            power_x = float(request.form.get('power_x', 1))
            power_y = float(request.form.get('power_y', 1))

            theta = np.linspace(0, 2 * np.pi, 1000)
            r = size * (1 - np.cos(theta))
            x = r * np.cos(theta) ** power_x
            y = r * np.sin(theta) ** power_y

            fig = Figure(figsize=(8, 8))
            ax = fig.add_subplot(111)
            ax.plot(x, y, 'purple', linewidth=2)
            ax.grid(True, alpha=0.3)
            ax.axis('equal')
            ax.axhline(y=0, color='k', linewidth=0.5)
            ax.axvline(x=0, color='k', linewidth=0.5)
            ax.set_title('Кардиоида', fontsize=14, fontweight='bold')
            ax.set_xlabel('x')
            ax.set_ylabel('y')

            image = fig_to_base64(fig)
        except Exception as e:
            error = str(e)

    return render_template('cardioid.html', image=image, size=size, power_x=power_x, power_y=power_y, error=error,
                           nickname=session.get('nickname'))


@app.route('/ellipse', methods=['GET', 'POST'])
@login_required
def ellipse():
    image = None
    a_val = None
    b_val = None
    error = None

    if request.method == 'POST':
        try:
            a_val = float(request.form.get('a', 5))
            b_val = float(request.form.get('b', 3))

            t = np.linspace(0, 2 * np.pi, 100)
            x = a_val * np.cos(t)
            y = b_val * np.sin(t)

            fig = Figure(figsize=(8, 8))
            ax = fig.add_subplot(111)
            ax.plot(x, y, 'green', linewidth=2)
            ax.grid(True, alpha=0.3)
            ax.axis('equal')
            ax.axhline(y=0, color='k', linewidth=0.5)
            ax.axvline(x=0, color='k', linewidth=0.5)
            ax.set_title(f'Эллипс (a={a_val}, b={b_val})', fontsize=14, fontweight='bold')
            ax.set_xlabel('x')
            ax.set_ylabel('y')

            image = fig_to_base64(fig)
        except Exception as e:
            error = str(e)

    return render_template('ellipse.html', image=image, a=a_val, b=b_val, error=error, nickname=session.get('nickname'))


@app.route('/3d_plot', methods=['GET', 'POST'])
@login_required
def plot_3d():
    image = None
    func_str = 'sin(sqrt(x**2 + y**2))'
    error = None

    if request.method == 'POST':
        try:
            func_str = request.form.get('function', 'sin(sqrt(x**2 + y**2))')
            x_range = request.form.get('x_range', '-5,5,0.5').split(',')
            y_range = request.form.get('y_range', '-5,5,0.5').split(',')

            x_min, x_max, x_step = float(x_range[0]), float(x_range[1]), float(x_range[2])
            y_min, y_max, y_step = float(y_range[0]), float(y_range[1]), float(y_range[2])

            x = np.arange(x_min, x_max, x_step)
            y = np.arange(y_min, y_max, y_step)
            X, Y = np.meshgrid(x, y)

            safe_dict = {
                'x': X, 'y': Y,
                'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
                'atan': np.arctan, 'arcsin': np.arcsin, 'arccos': np.arccos,
                'abs': np.abs, 'sqrt': np.sqrt, 'exp': np.exp,
                'pi': np.pi
            }

            with np.errstate(divide='ignore', invalid='ignore'):
                Z = eval(func_str, {"__builtins__": {}}, safe_dict)
                Z = np.where(np.abs(Z) > 50, np.nan, Z)

            fig = Figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            surf = ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.8)
            fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)
            ax.set_title(f'3D Поверхность: {func_str}', fontsize=12, fontweight='bold')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')

            image = fig_to_base64(fig)
        except Exception as e:
            error = str(e)

    return render_template('3d_plot.html', image=image, func_str=func_str, error=error,
                           nickname=session.get('nickname'))


@app.route('/parametric', methods=['GET', 'POST'])
@login_required
def parametric():
    image = None
    error = None
    a = b = c = 5
    x_func = 'a * sin(v) * cos(u)'
    y_func = 'b * sin(v) * sin(u)'
    z_func = 'c * cos(v)'

    if request.method == 'POST':
        try:
            a = float(request.form.get('a', 5))
            b = float(request.form.get('b', 5))
            c = float(request.form.get('c', 5))
            x_func = request.form.get('x_func', 'a * sin(v) * cos(u)')
            y_func = request.form.get('y_func', 'b * sin(v) * sin(u)')
            z_func = request.form.get('z_func', 'c * cos(v)')

            u = np.linspace(0, 2 * np.pi, 50)
            v = np.linspace(0, np.pi, 50)
            U, V = np.meshgrid(u, v)

            safe_dict = {
                'u': U, 'v': V, 'a': a, 'b': b, 'c': c,
                'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
                'pi': np.pi
            }

            X = eval(x_func, {"__builtins__": {}}, safe_dict)
            Y = eval(y_func, {"__builtins__": {}}, safe_dict)
            Z = eval(z_func, {"__builtins__": {}}, safe_dict)

            fig = Figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            ax.plot_surface(X, Y, Z, cmap='plasma', alpha=0.8)
            ax.set_title('Параметрическая 3D поверхность', fontsize=14, fontweight='bold')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')

            max_range = max(X.max() - X.min(), Y.max() - Y.min(), Z.max() - Z.min()) / 2
            mid_x = (X.max() + X.min()) / 2
            mid_y = (Y.max() + Y.min()) / 2
            mid_z = (Z.max() + Z.min()) / 2
            ax.set_xlim(mid_x - max_range, mid_x + max_range)
            ax.set_ylim(mid_y - max_range, mid_y + max_range)
            ax.set_zlim(mid_z - max_range, mid_z + max_range)

            image = fig_to_base64(fig)
        except Exception as e:
            error = str(e)

    return render_template('parametric.html', image=image, a=a, b=b, c=c,
                           x_func=x_func, y_func=y_func, z_func=z_func, error=error, nickname=session.get('nickname'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)