from flask import Blueprint, request, jsonify, current_app
import uuid
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from app.services import TextractService, ComprehendService, DynamoDBService, MatchingService, S3Service, SQSService

api_bp = Blueprint('api', __name__)

# Initialize services
textract_service = TextractService()
comprehend_service = ComprehendService()
dynamodb_service = DynamoDBService()
matching_service = MatchingService()
s3_service = S3Service()
sqs_service = SQSService()

# Helper function to check allowed files
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@api_bp.route('/resumes/upload', methods=['POST'])
def upload_resumes():
    """
    Async upload resumes for processing via SQS queue
    Expected: multipart/form-data with files and job_id
    Returns: batch_id immediately (HTTP 202 Accepted)
    Processing happens asynchronously via Lambda
    """
    try:
        # Check if files are present
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        job_id = request.form.get('job_id')
        
        if not job_id:
            return jsonify({'error': 'job_id is required'}), 400
        
        if not files or len(files) == 0:
            return jsonify({'error': 'At least one file is required'}), 400
        
        # Validate all files before processing
        for file in files:
            if file.filename == '':
                return jsonify({'error': 'Empty filename'}), 400
            if not allowed_file(file.filename):
                return jsonify({'error': f'Invalid file type: {file.filename}. Only PDF files allowed'}), 400
        
        # Create batch ID
        batch_id = str(uuid.uuid4())
        current_app.logger.info(f'\n🚀 ASYNC UPLOAD: Batch {batch_id} initiated for job {job_id}')
        
        # Create temp folder for batch
        batch_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], batch_id)
        os.makedirs(batch_folder, exist_ok=True)
        
        # Step 1: Validate and upload all files to S3
        s3_uploads = []
        for idx, file in enumerate(files):
            filename = secure_filename(file.filename)
            filepath = os.path.join(batch_folder, filename)
            file.save(filepath)
            
            candidate_id = f"cand_{idx + 1}"
            
            current_app.logger.info(f'Batch {batch_id}: Uploading {filename} to S3...')
            s3_result = s3_service.upload_file(filepath, batch_id, filename)
            
            if s3_result['status'] == 'success':
                s3_uploads.append({
                    'filename': filename,
                    'candidate_id': candidate_id,
                    's3_key': s3_result.get('s3_key'),
                    's3_url': s3_result.get('s3_url')
                })
                current_app.logger.info(f'✅ S3 upload: {filename} → {s3_result.get("s3_url")}')
            else:
                current_app.logger.error(f'❌ S3 upload failed: {filename}')
                return jsonify({
                    'error': 'S3 upload failed',
                    'message': f'Failed to upload {filename}: {s3_result.get("error")}'
                }), 500
        
        # Step 2: Create batch status record in DynamoDB
        current_app.logger.info(f'Batch {batch_id}: Creating batch status in DynamoDB...')
        batch_status = dynamodb_service.create_batch_status(batch_id, job_id, len(files))
        
        if batch_status['status'] != 'success':
            current_app.logger.error(f'❌ Failed to create batch status: {batch_status.get("error")}')
            return jsonify({
                'error': 'Batch setup failed',
                'message': batch_status.get('error')
            }), 500
        
        current_app.logger.info(f'✅ Batch status created: {len(files)} files queued for processing')
        
        # Step 3: Send SQS messages (one per file)
        sqs_messages = []
        for upload in s3_uploads:
            candidate_id = upload['candidate_id']
            filename = upload['filename']
            s3_key = upload['s3_key']
            
            message = {
                'batch_id': batch_id,
                'job_id': job_id,
                'candidate_id': candidate_id,
                'filename': filename,
                's3_key': s3_key
            }
            
            sqs_result = sqs_service.send_message(message)
            
            if sqs_result['status'] == 'success':
                sqs_messages.append(sqs_result.get('message_id'))
                current_app.logger.info(f'📬 SQS message sent: {candidate_id} (Message ID: {sqs_result.get("message_id")})')
            else:
                current_app.logger.error(f'❌ SQS failed for {candidate_id}: {sqs_result.get("error")}')
                return jsonify({
                    'error': 'Failed to queue processing',
                    'message': f'Could not queue {candidate_id} for processing'
                }), 500
        
        current_app.logger.info(f'✅ All {len(files)} resumes queued for async processing')
        
        # Step 4: Return batch_id immediately (HTTP 202 Accepted)
        return jsonify({
            'batch_id': batch_id,
            'job_id': job_id,
            'status': 'queued',
            'files_uploaded': len(files),
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Upload accepted! {len(files)} resume(s) queued for processing.',
            'polling_url': f'/api/batches/{batch_id}/status'
        }), 202
    
    except Exception as e:
        current_app.logger.error(f'❌ Error uploading resumes: {str(e)}', exc_info=True)
        return jsonify({'error': 'Upload failed', 'message': str(e)}), 500

@api_bp.route('/jobs/parse', methods=['POST'])
def parse_job_description():
    """
    Parse job description to extract required skills using Comprehend
    Expected: JSON with job_description field
    """
    try:
        data = request.get_json()
        
        if not data or 'job_description' not in data:
            return jsonify({'error': 'job_description is required'}), 400
        
        job_description = data['job_description']
        
        if not job_description or len(job_description) < 20:
            return jsonify({'error': 'job_description must be at least 20 characters'}), 400
        
        # Generate job ID
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        # Parse job description using Comprehend
        current_app.logger.info(f'Job {job_id}: Parsing job description with Comprehend')
        comprehend_result = comprehend_service.parse_job_description(job_description)
        
        if comprehend_result['status'] == 'success':
            current_app.logger.info(f'Job {job_id}: Successfully parsed - {len(comprehend_result["required_skills"])} required skills')
            
            # ✅ NEW: Save job to DynamoDB for reference during candidate matching
            dynamodb_save = dynamodb_service.save_job(job_id, {
                'job_title': comprehend_result.get('job_title'),
                'job_description': job_description,
                'required_skills': comprehend_result['required_skills'],
                'nice_to_have_skills': comprehend_result['nice_to_have_skills'],
                'experience_level': comprehend_result['experience_level'],
                'experience_years': comprehend_result['experience_years']
            })
            
            if dynamodb_save['status'] != 'success':
                current_app.logger.warning(f'Job {job_id}: DynamoDB save failed - {dynamodb_save.get("error")}')
            
            return jsonify({
                'job_id': job_id,
                'status': 'parsed',
                'job_title': comprehend_result.get('job_title'),
                'description_length': len(job_description),
                'required_skills': comprehend_result['required_skills'],
                'nice_to_have_skills': comprehend_result['nice_to_have_skills'],
                'experience_level': comprehend_result['experience_level'],
                'experience_years': comprehend_result['experience_years'],
                'message': f'Successfully parsed job description. Found {len(comprehend_result["required_skills"])} required skills.'
            }), 200
        else:
            current_app.logger.error(f'Job {job_id}: Parse failed - {comprehend_result.get("error")}')
            return jsonify({
                'error': 'Job parsing failed',
                'message': comprehend_result.get('error')
            }), 500
    
    except Exception as e:
        current_app.logger.error(f'Error parsing job description: {str(e)}')
        return jsonify({'error': 'Parse failed', 'message': str(e)}), 500

@api_bp.route('/jobs', methods=['GET'])
def get_all_jobs():
    """
    Get all saved jobs from DynamoDB
    Returns list of all jobs with their requirements
    """
    try:
        current_app.logger.info('Fetching all jobs from DynamoDB')
        
        all_jobs = dynamodb_service.get_all_jobs()
        
        if not all_jobs:
            return jsonify({
                'status': 'success',
                'jobs': [],
                'total': 0,
                'message': 'No jobs found'
            }), 200
        
        # Convert Decimal values to float for JSON serialization
        for job in all_jobs:
            if 'created_at' in job:
                job['created_at'] = str(job['created_at'])
            if 'experience_years' in job:
                job['experience_years'] = float(job.get('experience_years', 0))
        
        current_app.logger.info(f'Retrieved {len(all_jobs)} jobs from DynamoDB')
        
        return jsonify({
            'status': 'success',
            'jobs': all_jobs,
            'total': len(all_jobs),
            'message': f'Retrieved {len(all_jobs)} jobs'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f'Error fetching jobs: {str(e)}')
        return jsonify({'error': 'Fetch failed', 'message': str(e)}), 500

@api_bp.route('/results/<batch_id>', methods=['GET'])
def get_results(batch_id):
    """
    Get processing results and ranked candidates for a batch from DynamoDB
    """
    try:
        # ✅ Query DynamoDB for batch results
        ranked_candidates = matching_service.get_batch_ranked_results(batch_id)
        
        if not ranked_candidates:
            return jsonify({
                'batch_id': batch_id,
                'status': 'not_found',
                'message': 'No results found for this batch',
                'candidates': []
            }), 404
        
        # Calculate summary statistics
        total_candidates = len(ranked_candidates)
        strong_matches = len([c for c in ranked_candidates if c.get('status') == 'strong_match'])
        partial_matches = len([c for c in ranked_candidates if c.get('status') == 'partial_match'])
        not_qualified = len([c for c in ranked_candidates if c.get('status') == 'not_qualified'])
        avg_match_percentage = (sum([float(c.get('match_percentage', 0)) for c in ranked_candidates]) / total_candidates) if ranked_candidates else 0
        
        # Convert Decimal values to float for JSON serialization
        for candidate in ranked_candidates:
            if 'match_percentage' in candidate:
                candidate['match_percentage'] = float(candidate['match_percentage'])
            if 'textract_confidence' in candidate:
                candidate['textract_confidence'] = float(candidate['textract_confidence'])
            if 'comprehend_confidence' in candidate:
                candidate['comprehend_confidence'] = float(candidate['comprehend_confidence'])
        
        current_app.logger.info(f'Retrieved {total_candidates} candidates from batch {batch_id}')
        
        return jsonify({
            'batch_id': batch_id,
            'status': 'complete',
            'summary': {
                'total_candidates': total_candidates,
                'strong_matches': strong_matches,
                'partial_matches': partial_matches,
                'not_qualified': not_qualified,
                'avg_match_percentage': round(avg_match_percentage, 2)
            },
            'candidates': ranked_candidates,
            'message': f'Found {total_candidates} candidates: {strong_matches} strong matches, {partial_matches} partial matches, {not_qualified} not qualified.'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f'Error getting results: {str(e)}')
        return jsonify({'error': 'Retrieval failed', 'message': str(e)}), 500

@api_bp.route('/batches/<batch_id>/status', methods=['GET'])
def get_batch_status_async(batch_id):
    """
    Get current processing status of a batch
    Returns progress information for frontend polling
    Used by frontend to show progress bar and completion status
    """
    try:
        current_app.logger.info(f'📊 Polling status for batch {batch_id}')
        
        # Get batch status from DynamoDB
        batch = dynamodb_service.get_batch_status(batch_id)
        
        if not batch:
            current_app.logger.warning(f'Batch {batch_id} not found')
            return jsonify({
                'error': 'Batch not found',
                'batch_id': batch_id
            }), 404
        
        # Convert Decimal values to float for JSON serialization
        response_data = {
            'batch_id': batch_id,
            'job_id': batch.get('job_id'),
            'status': batch.get('status'),
            'total_files': batch.get('total_files'),
            'processed_files': batch.get('processed_files', 0),
            'failed_files': batch.get('failed_files', 0),
            'completion_percentage': float(batch.get('completion_percentage', 0)),
            'created_at': str(batch.get('created_at')),
            'started_at': str(batch.get('started_at')) if batch.get('started_at') else None,
            'completed_at': str(batch.get('completed_at')) if batch.get('completed_at') else None
        }
        
        # Include errors if any
        if batch.get('errors'):
            response_data['errors'] = batch.get('errors')
        
        current_app.logger.info(f'✅ Batch {batch_id} status: {response_data["status"]} ({response_data["completion_percentage"]}% complete)')
        
        return jsonify(response_data), 200
    
    except Exception as e:
        current_app.logger.error(f'❌ Error getting batch status: {str(e)}', exc_info=True)
        return jsonify({'error': 'Status check failed', 'message': str(e)}), 500

@api_bp.route('/download/<batch_id>/<filename>', methods=['GET'])
def download_resume(batch_id, filename):
    """
    Generate presigned URL for downloading a resume from S3
    Allows users to access their uploaded PDFs with time-limited access (1 hour)
    """
    try:
        # Construct S3 key based on storage pattern: resumes/{batch_id}/{filename}
        s3_key = f"resumes/{batch_id}/{filename}"
        
        current_app.logger.info(f'Generating presigned URL for {s3_key}')
        
        # Get presigned URL from S3 service (expires in 1 hour)
        presigned_result = s3_service.get_presigned_url(s3_key, expiration=3600)
        
        if presigned_result['status'] == 'success':
            return jsonify({
                'status': 'success',
                'download_url': presigned_result.get('url'),
                'expires_in_seconds': 3600,
                'message': 'Presigned URL generated successfully'
            }), 200
        else:
            current_app.logger.warning(f'Failed to generate presigned URL: {presigned_result.get("error")}')
            return jsonify({
                'error': 'Failed to generate download URL',
                'message': presigned_result.get('error')
            }), 500
    
    except Exception as e:
        current_app.logger.error(f'Error generating presigned URL: {str(e)}')
        return jsonify({'error': 'Download URL generation failed', 'message': str(e)}), 500

@api_bp.route('/batches', methods=['GET'])
def get_all_batches():
    """
    Get all batches with summary statistics
    Useful for dashboard/overview page
    """
    try:
        current_app.logger.info('Fetching all batches from DynamoDB')
        
        all_batches = dynamodb_service.get_all_batches()
        
        if not all_batches:
            return jsonify({
                'status': 'success',
                'batches': [],
                'total': 0,
                'message': 'No batches found'
            }), 200
        
        current_app.logger.info(f'Retrieved {len(all_batches)} batches from DynamoDB')
        
        return jsonify({
            'status': 'success',
            'batches': all_batches,
            'total': len(all_batches),
            'message': f'Retrieved {len(all_batches)} batches'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f'Error fetching batches: {str(e)}')
        return jsonify({'error': 'Fetch failed', 'message': str(e)}), 500
