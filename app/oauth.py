from flask import flash, redirect, url_for
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask_login import current_user, login_user
from sqlalchemy.orm.exc import NoResultFound
from .models.oauth import OAuth
from .models.user import User
from . import db

# Create a blueprint for Google OAuth
google_bp = None

def init_oauth(app):
    """Initialize OAuth providers"""
    global google_bp
    
    # Configure Google OAuth
    google_bp = make_google_blueprint(
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        scope=["profile", "email"],
        storage=SQLAlchemyStorage(OAuth, db.session, user=current_user)
    )
    
    # Define the route before registering the blueprint
    @google_bp.route("/google/authorized")
    def google_authorized():
        if not google.authorized:
            flash("Authentication failed.", "danger")
            return redirect(url_for("auth.login"))
        
        resp = google.get("/oauth2/v1/userinfo")
        if resp.ok:
            google_info = resp.json()
            google_user_id = google_info["id"]
            
            # Find this OAuth token in the database, or create it
            try:
                oauth = OAuth.query.filter_by(
                    provider="google",
                    provider_user_id=google_user_id
                ).one()
            except NoResultFound:
                oauth = OAuth(
                    provider="google",
                    provider_user_id=google_user_id,
                    token=google.token["access_token"],
                )
            
            if oauth.user:
                login_user(oauth.user)
                flash("Successfully signed in with Google.", "success")
                return redirect(url_for("main.dashboard"))
            else:
                # Create a new user
                email = google_info["email"]
                user = User.query.filter_by(email=email).first()
                
                is_new_user = False
                if not user:
                    user = User(
                        email=email,
                        name=google_info["name"],
                    )
                    db.session.add(user)
                    db.session.flush()
                    is_new_user = True
                
                # Associate the user with the OAuth token
                oauth.user = user
                db.session.add(oauth)
                db.session.commit()
                
                login_user(user)
                flash("Successfully signed in with Google.", "success")
                
                # Redirect to welcome page for first-time users
                if is_new_user:
                    return redirect(url_for("main.user_dashboard", first_login="true"))
                return redirect(url_for("main.dashboard"))
        
        flash("Failed to fetch user info from Google.", "danger")
        return redirect(url_for("auth.login"))
    
    # Register the blueprint after defining all routes
    app.register_blueprint(google_bp, url_prefix="/login") 