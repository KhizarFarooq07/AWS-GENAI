"""
Lambda Handler - Reuses Backend Services
No code duplication, leverages existing service layer
"""

import json
import logging
import tempfile
import os
from datetime import datetime

# Import services from layer
from app.services import (
    TextractService,
    ComprehendService,
    DynamoDBService,
    MatchingService,
    S3Service
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Config
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'resume-screening-khizar-v2')
BATCH_TABLE = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')

# Services will be initialized on first use
_services = {}


def _get_services():
    """Lazy-load services on first use"""
    global _services
    if not _services:
        logger.info("Initializing services...")
        _services = {
            'textract': TextractService(),
            'comprehend': ComprehendService(),
            'dynamodb': DynamoDBService(),
            'matching': MatchingService(),
            's3': S3Service()
        }
    return _services


def lambda_handler(event, context):
    """
    Process resumes from SQS messages
    Uses existing backend services to avoid code duplication
    """
    logger.info('🚀 Lambda started - using backend services')
    
    results = {'processed': 0, 'failed': 0}
    
    for record in event.get('Records', []):
        try:
            msg = json.loads(record['body'])
            batch_id = msg['batch_id']
            candidate_id = msg['candidate_id']
            s3_key = msg['s3_key']
            filename = msg['filename']
            job_id = msg['job_id']
            
            logger.info(f"👤 Processing {candidate_id}")
            
            result = process_resume(batch_id, candidate_id, s3_key, filename, job_id)
            if result['status'] == 'success':
                results['processed'] += 1
                logger.info(f"✅ {candidate_id}: {result['match']}% match")
            else:
                results['failed'] += 1
                logger.error(f"❌ {candidate_id}: {result['error']}")
                _update_batch_error(batch_id, candidate_id, filename, result['error'])
        
        except Exception as e:
            logger.error(f"💥 Error processing record: {str(e)}", exc_info=True)
            results['failed'] += 1
    
    logger.info(f"✨ Done: {results['processed']} OK, {results['failed']} failed")
    return results


def process_resume(batch_id, candidate_id, s3_key, filename, job_id):
    """
    Full resume processing pipeline using backend services
    
    Steps:
    1. Download from S3
    2. Extract text with TextractService
    3. Extract skills with ComprehendService
    4. Match skills with MatchingService
    5. Save results to DynamoDB
    6. Update batch progress
    """
    try:
        services = _get_services()
        textract_service = services['textract']
        comprehend_service = services['comprehend']
        matching_service = services['matching']
        dynamodb_service = services['dynamodb']
        s3_service = services['s3']
        
        # Step 1: Download resume from S3
        logger.info("📥 Downloading from S3")
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
        
        s3_client = __import__('boto3').client('s3', region_name='us-east-1')
        s3_client.download_file(S3_BUCKET, s3_key, tmp_path)
        
        # Step 2: Extract text using Textract service
        logger.info("📄 Extracting text with Textract")
        text_result = textract_service.extract_text_from_pdf(tmp_path)
        if text_result['status'] != 'success':
            logger.error(f"Textract failed: {text_result['error']}")
            return {'status': 'error', 'error': f"Textract: {text_result['error']}"}
        
        text = text_result['text']
        textract_confidence = text_result.get('confidence', 0.8)
        
        # Step 3: Extract skills using Comprehend service
        logger.info("🎯 Extracting skills")
        skills_result = comprehend_service.extract_skills(text)
        if skills_result['status'] != 'success':
            logger.error(f"Comprehend failed: {skills_result['error']}")
            return {'status': 'error', 'error': f"Comprehend: {skills_result['error']}"}
        
        skills = [s['skill'] if isinstance(s, dict) else s for s in skills_result.get('skills', [])]
        job_titles = [t['title'] if isinstance(t, dict) else t for t in skills_result.get('job_titles', [])]
        exp_level = skills_result.get('experience_level', 'mid')
        comprehend_confidence = skills_result.get('average_confidence', 0.8)
        
        # Step 4: Match skills using Matching service
        logger.info("⚖️ Matching skills to job")
        match_result = matching_service.match_candidate_to_job(job_id, skills, exp_level)
        if match_result['status'] != 'success':
            logger.error(f"Matching failed: {match_result['error']}")
            return {'status': 'error', 'error': f"Matching: {match_result['error']}"}
        
        match_percentage = match_result['match_percentage']
        
        # Step 5: Save results using Matching and DynamoDB services
        logger.info("💾 Saving results")
        s3_url = f"s3://{S3_BUCKET}/{s3_key}"
        
        save_result = matching_service.save_match_result(
            batch_id=batch_id,
            candidate_id=candidate_id,
            job_id=job_id,
            filename=filename,
            candidate_skills=skills,
            job_titles=job_titles,
            experience_level=exp_level,
            textract_confidence=textract_confidence,
            comprehend_confidence=comprehend_confidence,
            match_result=match_result,
            s3_url=s3_url
        )
        
        if save_result['status'] != 'success':
            logger.error(f"Save failed: {save_result['error']}")
            return {'status': 'error', 'error': f"Save: {save_result['error']}"}
        
        # Step 6: Update batch progress
        logger.info("📊 Updating batch progress")
        _update_batch_progress(batch_id)
        
        # Cleanup
        try:
            os.remove(tmp_path)
        except:
            pass
        
        logger.info(f"🎉 {candidate_id} completed: {match_percentage}% match ({match_result.get('match_status', 'qualified')})")
        
        return {
            'status': 'success',
            'match': match_percentage,
            'status_name': match_result.get('match_status', 'qualified')
        }
    
    except Exception as e:
        logger.error(f"💥 Process error: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


def _update_batch_progress(batch_id):
    """Update batch progress counter"""
    try:
        services = _get_services()
        dynamodb_service = services['dynamodb']
        table = dynamodb_service.dynamodb.Table(BATCH_TABLE)
        
        # Get current batch status
        response = table.get_item(Key={'batch_id': batch_id})
        if 'Item' in response:
            item = response['Item']
            processed = int(item.get('processed_files', 0)) + 1
            total = int(item.get('total_files', 1))
            completion_pct = int((processed / total) * 100) if total > 0 else 0
            
            # Update batch status
            update_kwargs = {
                'Key': {'batch_id': batch_id},
                'UpdateExpression': 'SET processed_files = :pf, completion_percentage = :cp',
                'ExpressionAttributeValues': {
                    ':pf': processed,
                    ':cp': completion_pct
                }
            }
            
            # Mark as complete if all files processed
            if processed == total:
                update_kwargs['UpdateExpression'] += ', #s = :status'
                update_kwargs['ExpressionAttributeNames'] = {'#s': 'status'}
                update_kwargs['ExpressionAttributeValues'][':status'] = 'completed'
                logger.info(f"✅ Batch {batch_id} completed!")
            
            table.update_item(**update_kwargs)
            logger.info(f"📊 Batch {batch_id}: {processed}/{total} ({completion_pct}%)")
    
    except Exception as e:
        logger.error(f"Failed to update batch progress: {str(e)}", exc_info=True)


def _update_batch_error(batch_id, candidate_id, filename, error):
    """Track errors with details in batch"""
    try:
        services = _get_services()
        dynamodb_service = services['dynamodb']
        table = dynamodb_service.dynamodb.Table(BATCH_TABLE)
        
        # Append error to errors list
        error_record = {
            'candidate_id': candidate_id,
            'filename': filename,
            'error_message': error,
            'timestamp': datetime.now().isoformat()
        }
        
        # Update batch: increment failed_files and append to errors list
        table.update_item(
            Key={'batch_id': batch_id},
            UpdateExpression='SET failed_files = if_not_exists(failed_files, :zero) + :one, errors = list_append(if_not_exists(errors, :empty_list), :error)',
            ExpressionAttributeValues={
                ':zero': 0,
                ':one': 1,
                ':empty_list': [],
                ':error': [error_record]
            }
        )
        logger.info(f"⚠️ Error recorded for {candidate_id}: {error}")
    except Exception as e:
        logger.error(f"Failed to update error count: {str(e)}", exc_info=True)
