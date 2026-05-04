import os

# Try to load .env file if it exists (for local dev)
# In Lambda, this will be skipped and environment variables will be used directly
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available (Lambda environment)

class Config:
    """Base configuration - works in both Flask and Lambda"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', False)
    
    # AWS
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    # S3
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'resume-screening-bucket')
    
    # DynamoDB
    DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'resume_results')
    DYNAMODB_REGION = os.getenv('DYNAMODB_REGION', 'us-east-1')
    
    # GitHub
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    
    # Bedrock
    BEDROCK_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'claude-3-sonnet-20240229')
    BEDROCK_REGION = os.getenv('BEDROCK_REGION', 'us-east-1')
    
    # File Upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max
    ALLOWED_EXTENSIONS = {'pdf'}
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'logs', 'app.log')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    DYNAMODB_TABLE_NAME = 'resume_results_test'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

# Select config based on environment
config_name = os.getenv('FLASK_ENV', 'development')
if config_name == 'testing':
    config = TestingConfig()
elif config_name == 'production':
    config = ProductionConfig()
else:
    config = DevelopmentConfig()
