"""Authentication Blueprint: login, logout, and user management CLI."""
from datetime import datetime, timezone

import bcrypt
import click
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from models import db, User
from forms import LoginForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def hash_password(password: str) -> str:
    from flask import current_app
    rounds = current_app.config.get("BCRYPT_LOG_ROUNDS", 12)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index", lang=request.cookies.get("lang", "ko")))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.is_active and check_password(form.password.data, user.password_hash):
            login_user(user, remember=form.remember.data)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("index", lang=request.cookies.get("lang", "ko")))
        flash("Invalid username or password.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


def register_cli(app):
    @app.cli.command("create-user")
    @click.option("--username", prompt=True, help="Username")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--display-name", default=None)
    @click.option("--email", default=None)
    def create_user(username, password, display_name, email):
        with app.app_context():
            if User.query.filter_by(username=username).first():
                click.echo(f"Error: User '{username}' already exists.")
                return
            user = User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name or username,
                email=email,
            )
            db.session.add(user)
            db.session.commit()
            click.echo(f"User '{username}' created (id={user.id}).")

    @app.cli.command("list-users")
    def list_users():
        with app.app_context():
            users = User.query.all()
            if not users:
                click.echo("No users found.")
                return
            for u in users:
                status = "active" if u.is_active else "disabled"
                click.echo(f"  [{u.id}] {u.username} ({u.display_name}) - {status}")
