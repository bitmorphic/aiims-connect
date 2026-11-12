import os
from flask import Flask
from dotenv import load_dotenv
def create_app():
    load_dotenv()
    app=Flask(__name__,template_folder='../templates',static_folder='../static')
    app.secret_key=os.getenv('FLASK_SECRET_KEY','change-this-dev-secret')
    app.config['DEBUG']=os.getenv('FLASK_DEBUG','0')=='1'
    from .routes import bp
    app.register_blueprint(bp)
    return app
