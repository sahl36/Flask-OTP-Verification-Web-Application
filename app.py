from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy.sql import func
from os import path
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp
from flask_mail import Mail, Message


def nocache(view):
    def no_cache_wrapper(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return no_cache_wrapper


DB_NAME = "database.db"

app = Flask(__name__)
app.config['SECRET_KEY'] = "HELLOWORD"
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your@gmail.com'
app.config['MAIL_PASSWORD'] = 'your app password'
mail = Mail(app)

db = SQLAlchemy(app)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())


def create_database():
    if not path.exists(DB_NAME):
        db.create_all()
        print("db created")


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.route('/')
@app.route("/login", methods=['GET', 'POST'], endpoint='login')
@nocache
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password1")

        user = User.query.filter_by(username=username).first()
        if user:
            if check_password_hash(user.password, password):
                flash("Logged in", category='success')
                login_user(user, remember=True)
                return redirect('/dashboard')
            else:
                flash('Invalid Credentials', category='error')
        else:
            flash("Invalid Credentials", category='error')

    return render_template("login.html")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")

        username_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()

        if email_exists:
            flash('Email is already in use.', category='error')
        elif username_exists:
            flash('Username is already in use.', category='error')
        elif password1 != password2:
            flash("Passwords don't match", category='error')
        else:

            totp = pyotp.TOTP('base32secret3232')
            otp = totp.now()

            msg = Message('Your OTP Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'Your OTP code is {otp}'
            mail.send(msg)

            session['otp'] = otp
            session['temp_user'] = {
                'username': username,
                'email': email,
                'password': generate_password_hash(password1, method='pbkdf2:sha256')
            }
            return redirect(url_for('verify_otp'))

    return render_template("register.html")


@app.route("/verify_otp", methods=['GET', 'POST'])
def verify_otp():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        entered_otp = request.form.get("otp")
        if entered_otp == session.get('otp'):

            user_data = session.get('temp_user')
            new_user = User(username=user_data['username'], email=user_data['email'], password=user_data['password'])
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user, remember=True)
            flash('User created and logged in successfully.', category='success')
            return redirect(url_for("dashboard"))
        else:
            flash('Invalid OTP. Please try again.', category='error')

    return render_template("verify_otp.html")


@app.route('/dashboard', methods=["GET"], endpoint='dashboard')
@login_required
@nocache
def dashboard():
    return render_template("dashboard.html", username=current_user.username)


@app.route('/logout', endpoint='logout')
@login_required
@nocache
def logout():
    logout_user()

    session.clear()

    response = redirect(url_for('login'))
    response.set_cookie('remember_token', '', expires=0)
    return response


if __name__ == "__main__":
    with app.app_context():
        create_database()
    app.run(debug=True)
