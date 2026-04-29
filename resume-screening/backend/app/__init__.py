from flask import Flask
from flask_cors import CORS
import logging
import os
from config import config

def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config)
    
    # Enable CORS
    CORS(app)
    
    # Setup logging
    setup_logging(app)
    
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)
    
    # Register blueprints
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'healthy', 'message': 'Resume Screening API is running'}, 200
    
    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return {'error': 'Bad request', 'message': str(e)}, 400
    
    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found', 'message': 'Endpoint does not exist'}, 404
    
    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f'Internal server error: {str(e)}')
        return {'error': 'Internal server error', 'message': 'An error occurred'}, 500
    
    return app

def setup_logging(app):
    """Configure logging"""
    log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
    
    # File handler
    file_handler = logging.FileHandler(app.config['LOG_FILE'])
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
