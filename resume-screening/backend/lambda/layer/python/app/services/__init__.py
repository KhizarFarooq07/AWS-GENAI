# Services module
# For Lambda: only import services needed for resume processing

from .textract_service import TextractService
from .comprehend_service import ComprehendService
from .dynamodb_service import DynamoDBService
from .matching_service import MatchingService
from .s3_service import S3Service

# Optional services (only imported if needed)
try:
    from .bedrock_service import BedrockService
except ImportError:
    pass

try:
    from .github_service import GitHubService
except ImportError:
    pass

try:
    from .sqs_service import SQSService
except ImportError:
    pass

__all__ = [
    'TextractService',
    'ComprehendService',
    'DynamoDBService',
    'MatchingService',
    'S3Service',
    'BedrockService'
]
