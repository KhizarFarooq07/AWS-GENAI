import logging
import boto3
from botocore.config import Config
from config import config

logger = logging.getLogger(__name__)


class TextractService:
    """Service for AWS Textract integration"""
    
    def __init__(self):
        self.region = config.AWS_REGION
        
        # Initialize Textract client with adaptive retry strategy
        retry_config = Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'
            },
            read_timeout=60
        )
        
        self.client = boto3.client(
            'textract',
            region_name=self.region,
            config=retry_config,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
        )
    
    def extract_text_from_pdf(self, file_path):
        """
        Extract text from PDF file using AWS Textract (synchronous)
        
        Args:
            file_path: Path to PDF file on disk
            
        Returns:
            dict with keys:
                - status: 'success' or 'error'
                - text: Extracted text
                - pages: Number of pages processed
                - confidence: Average confidence score
                - error: Error message if status is 'error'
        """
        logger.info(f'Extracting text from {file_path}')
        
        try:
            # Read PDF file as bytes
            with open(file_path, 'rb') as pdf_file:
                document_bytes = pdf_file.read()
            
            logger.debug(f'File size: {len(document_bytes)} bytes')
            
            # Call Textract synchronously
            response = self.client.detect_document_text(
                Document={'Bytes': document_bytes}
            )
            
            # Parse response
            text = self._parse_textract_response(response)
            pages = response.get('DocumentMetadata', {}).get('Pages', 1)
            
            # Calculate average confidence
            confidence = self._calculate_confidence(response)
            
            logger.info(f'Successfully extracted text from {pages} page(s)')
            
            return {
                'status': 'success',
                'text': text,
                'pages': pages,
                'confidence': confidence,
                'raw_response': response
            }
        
        except FileNotFoundError:
            error_msg = f'File not found: {file_path}'
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'text': None
            }
        
        except Exception as e:
            error_msg = f'Textract extraction failed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg,
                'text': None
            }
    
    def extract_with_confidence(self, file_path):
        """
        Extract text with detailed confidence scores per block
        
        Args:
            file_path: Path to PDF file on disk
            
        Returns:
            dict with:
                - text: Full extracted text
                - blocks: List of text blocks with confidence scores
                - average_confidence: Overall confidence
                - status: 'success' or 'error'
        """
        logger.info(f'Extracting text with confidence from {file_path}')
        
        try:
            with open(file_path, 'rb') as pdf_file:
                document_bytes = pdf_file.read()
            
            response = self.client.detect_document_text(
                Document={'Bytes': document_bytes}
            )
            
            blocks = []
            full_text = []
            confidences = []
            
            # Extract confidence per block
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    text = block.get('Text', '')
                    confidence = block.get('Confidence', 0.0)
                    
                    blocks.append({
                        'text': text,
                        'confidence': confidence,
                        'block_type': 'line'
                    })
                    
                    if text.strip():
                        full_text.append(text)
                        confidences.append(confidence)
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            logger.info(f'Extracted {len(blocks)} blocks with avg confidence {avg_confidence:.2%}')
            
            return {
                'status': 'success',
                'text': '\n'.join(full_text),
                'blocks': blocks,
                'average_confidence': avg_confidence,
                'block_count': len(blocks)
            }
        
        except Exception as e:
            error_msg = f'Confidence extraction failed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg,
                'text': None,
                'blocks': []
            }
    
    def _parse_textract_response(self, response):
        """Parse Textract response and extract full text"""
        full_text = []
        
        for block in response.get('Blocks', []):
            # Extract LINE blocks (highest level text)
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '')
                if text.strip():
                    full_text.append(text)
        
        return '\n'.join(full_text)
    
    def _calculate_confidence(self, response):
        """Calculate average confidence score from Textract response (0.0 to 100.0)"""
        confidences = []
        
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                confidence = block.get('Confidence', 0.0)
                if confidence > 0:
                    confidences.append(confidence)
        
        if not confidences:
            return 0.0
        
        # Average is already in 0-100 range from AWS
        return sum(confidences) / len(confidences)
