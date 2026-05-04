import logging
import boto3
from botocore.config import Config
from datetime import datetime
from config import config
from decimal import Decimal
import os

logger = logging.getLogger(__name__)


class DynamoDBService:
    """Service for AWS DynamoDB integration for persistence"""
    
    def __init__(self):
        self.region = config.AWS_REGION
        
        # Initialize DynamoDB resource with adaptive retry strategy
        retry_config = Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'
            },
            read_timeout=60
        )
        
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=self.region,
            config=retry_config
        )
        
        # Table names - aligned with existing DynamoDB setup
        self.jobs_table_name = 'job_requirements'
        self.results_table_name = 'resume_results'  # Use existing table for candidate results
        self.batch_status_table_name = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')
        
        # Initialize or ensure tables exist
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Create tables if they don't exist"""
        try:
            # Check if jobs table exists
            try:
                self.dynamodb.meta.client.describe_table(TableName=self.jobs_table_name)
                logger.info(f'Table {self.jobs_table_name} exists')
            except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
                logger.info(f'Creating table {self.jobs_table_name}...')
                self._create_jobs_table()
            
            # Check if results table exists
            try:
                self.dynamodb.meta.client.describe_table(TableName=self.results_table_name)
                logger.info(f'Table {self.results_table_name} exists')
            except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
                logger.info(f'Creating table {self.results_table_name}...')
                self._create_results_table()
            
            # Check if batch status table exists
            try:
                self.dynamodb.meta.client.describe_table(TableName=self.batch_status_table_name)
                logger.info(f'Table {self.batch_status_table_name} exists')
            except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
                logger.info(f'Creating table {self.batch_status_table_name}...')
                self._create_batch_status_table()
        
        except Exception as e:
            logger.warning(f'Could not verify tables: {str(e)}. Continuing anyway...')
    
    def _create_jobs_table(self):
        """Create job_requirements table"""
        try:
            table = self.dynamodb.create_table(
                TableName=self.jobs_table_name,
                KeySchema=[
                    {'AttributeName': 'job_id', 'KeyType': 'HASH'},  # PK
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}  # SK
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'job_id', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'  # On-demand pricing
            )
            logger.info(f'Created table {self.jobs_table_name}')
        except Exception as e:
            logger.error(f'Failed to create {self.jobs_table_name}: {str(e)}')
    
    def _create_results_table(self):
        """Create resume_results table for storing candidate match results"""
        try:
            table = self.dynamodb.create_table(
                TableName=self.results_table_name,
                KeySchema=[
                    {'AttributeName': 'batch_id', 'KeyType': 'HASH'},  # PK
                    {'AttributeName': 'candidate_id', 'KeyType': 'RANGE'}  # SK
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'batch_id', 'AttributeType': 'S'},
                    {'AttributeName': 'candidate_id', 'AttributeType': 'S'},
                    {'AttributeName': 'job_id', 'AttributeType': 'S'},
                    {'AttributeName': 'match_percentage', 'AttributeType': 'N'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'job_id-match_percentage-index',
                        'KeySchema': [
                            {'AttributeName': 'job_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'match_percentage', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    }
                ],
                BillingMode='PROVISIONED',
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            )
            logger.info(f'Created table {self.results_table_name}')
        except Exception as e:
            logger.error(f'Failed to create {self.results_table_name}: {str(e)}')
    
    def _create_batch_status_table(self):
        """Create batch_processing_status table for tracking batch progress"""
        try:
            table = self.dynamodb.create_table(
                TableName=self.batch_status_table_name,
                KeySchema=[
                    {'AttributeName': 'batch_id', 'KeyType': 'HASH'}  # PK only (one record per batch)
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'batch_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'  # On-demand pricing
            )
            logger.info(f'Created table {self.batch_status_table_name}')
        except Exception as e:
            logger.error(f'Failed to create {self.batch_status_table_name}: {str(e)}')
    
    # ==================== JOB METHODS ====================
    
    def save_job(self, job_id, job_data):
        """
        Save job requirements to DynamoDB
        
        Args:
            job_id: Unique job identifier
            job_data: Dict containing job details
                - job_title: Job position title
                - job_description: Full job description text
                - required_skills: List of required skills
                - nice_to_have_skills: List of preferred skills
                - experience_level: Required experience level (e.g., "Senior")
                - experience_years: Years of experience required
        
        Returns:
            dict with status
        """
        try:
            table = self.dynamodb.Table(self.jobs_table_name)
            created_at = datetime.utcnow().isoformat()
            
            item = {
                'job_id': job_id,
                'created_at': created_at,
                'updated_at': created_at,
                'job_title': job_data.get('job_title'),
                'job_description': job_data.get('job_description', ''),
                'required_skills': job_data.get('required_skills', []),
                'nice_to_have_skills': job_data.get('nice_to_have_skills', []),
                'experience_level': job_data.get('experience_level'),
                'experience_years': job_data.get('experience_years', 0),
                'status': 'open'
            }
            
            # Convert skill dicts to simple strings for DynamoDB
            item['required_skills'] = [
                s['skill'] if isinstance(s, dict) else s 
                for s in item['required_skills']
            ]
            item['nice_to_have_skills'] = [
                s['skill'] if isinstance(s, dict) else s 
                for s in item['nice_to_have_skills']
            ]
            
            table.put_item(Item=item)
            logger.info(f'Saved job {job_id} - {item.get("job_title")} with {len(item["required_skills"])} required skills')
            
            return {
                'status': 'success',
                'job_id': job_id,
                'created_at': created_at
            }
        
        except Exception as e:
            error_msg = f'Failed to save job {job_id}: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg
            }
    
    def get_job(self, job_id):
        """
        Retrieve job requirements from DynamoDB
        
        Args:
            job_id: Job identifier
        
        Returns:
            dict with job data or None if not found
        """
        try:
            table = self.dynamodb.Table(self.jobs_table_name)
            
            # Query with limit to get most recent job
            response = table.query(
                KeyConditionExpression='job_id = :job_id',
                ExpressionAttributeValues={':job_id': job_id},
                ScanIndexForward=False,  # Descending order (most recent first)
                Limit=1
            )
            
            if response['Items']:
                job = response['Items'][0]
                logger.info(f'Retrieved job {job_id}')
                return job
            else:
                logger.warning(f'Job {job_id} not found')
                return None
        
        except Exception as e:
            logger.error(f'Failed to get job {job_id}: {str(e)}', exc_info=True)
            return None
    
    def get_all_jobs(self):
        """
        Retrieve all jobs from DynamoDB, most recent first
        
        Returns:
            list of all jobs
        """
        try:
            table = self.dynamodb.Table(self.jobs_table_name)
            
            # Scan all items (for small dataset) or use pagination for large ones
            all_jobs = []
            last_evaluated_key = None
            
            while True:
                if last_evaluated_key:
                    response = table.scan(ExclusiveStartKey=last_evaluated_key)
                else:
                    response = table.scan()
                
                all_jobs.extend(response.get('Items', []))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            # Sort by created_at descending (most recent first)
            all_jobs.sort(
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )
            
            logger.info(f'Retrieved {len(all_jobs)} total jobs from DynamoDB')
            return all_jobs
        
        except Exception as e:
            logger.error(f'Failed to get all jobs: {str(e)}', exc_info=True)
            return []
    
    # ==================== CANDIDATE METHODS ====================
    
    def save_candidate_match(self, batch_id, candidate_id, candidate_data):
        """
        Save candidate match results to DynamoDB resume_results table
        
        Args:
            batch_id: Unique batch identifier
            candidate_id: Unique candidate identifier within batch
            candidate_data: Dict containing:
                - job_id: Reference to job
                - filename: Resume filename
                - extracted_skills: List of skills extracted from resume
                - job_titles: List of job titles found
                - experience_level: Candidate's experience level
                - textract_confidence: Textract confidence score (0-1)
                - comprehend_confidence: Comprehend confidence score (0-1)
                - match_percentage: Skill match percentage
                - matched_skills: List of matched skills
                - missing_skills: List of missing required skills
                - bonus_skills: List of bonus skills candidate has
                - status: Match status (strong_match, partial_match, not_qualified)
        
        Returns:
            dict with status
        """
        try:
            table = self.dynamodb.Table(self.results_table_name)
            created_at = datetime.utcnow().isoformat()
            
            item = {
                'batch_id': batch_id,
                'candidate_id': candidate_id,
                'created_at': created_at,
                'updated_at': created_at,
                'job_id': candidate_data.get('job_id'),
                'filename': candidate_data.get('filename'),
                'extracted_skills': candidate_data.get('extracted_skills', []),
                'job_titles': candidate_data.get('job_titles', []),
                'experience_level': candidate_data.get('experience_level'),
                'textract_confidence': Decimal(str(candidate_data.get('textract_confidence', 0))),
                'comprehend_confidence': Decimal(str(candidate_data.get('comprehend_confidence', 0))),
                'match_percentage': Decimal(str(candidate_data.get('match_percentage', 0))),
                'matched_skills': candidate_data.get('matched_skills', []),
                'missing_skills': candidate_data.get('missing_skills', []),
                'bonus_skills': candidate_data.get('bonus_skills', []),
                'status': candidate_data.get('status', 'pending'),
                's3_url': candidate_data.get('s3_url')
            }
            
            # Convert skill dicts to strings
            for skill_key in ['extracted_skills', 'matched_skills', 'missing_skills', 'bonus_skills']:
                item[skill_key] = [
                    s['skill'] if isinstance(s, dict) else s 
                    for s in item[skill_key]
                ]
            
            # Convert job_titles dicts to strings
            item['job_titles'] = [
                t['title'] if isinstance(t, dict) else t 
                for t in item['job_titles']
            ]
            
            table.put_item(Item=item)
            logger.info(f'Saved candidate {candidate_id} to batch {batch_id} with {Decimal(str(candidate_data.get("match_percentage", 0)))}% match')
            
            return {
                'status': 'success',
                'batch_id': batch_id,
                'candidate_id': candidate_id,
                'created_at': created_at
            }
        
        except Exception as e:
            error_msg = f'Failed to save candidate {candidate_id}: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg
            }
    
    def get_batch_results(self, batch_id):
        """
        Retrieve all candidates in a batch from DynamoDB resume_results table
        
        Args:
            batch_id: Batch identifier
        
        Returns:
            list of candidate results
        """
        try:
            table = self.dynamodb.Table(self.results_table_name)
            
            response = table.query(
                KeyConditionExpression='batch_id = :batch_id',
                ExpressionAttributeValues={':batch_id': batch_id}
            )
            
            candidates = response.get('Items', [])
            logger.info(f'Retrieved {len(candidates)} candidates from batch {batch_id}')
            return candidates
        
        except Exception as e:
            logger.error(f'Failed to get batch results {batch_id}: {str(e)}', exc_info=True)
            return []
    
    def rank_candidates(self, batch_id):
        """
        Get candidates ranked by match percentage (highest first)
        
        Args:
            batch_id: Batch identifier
        
        Returns:
            list of candidates sorted by match_percentage descending
        """
        try:
            candidates = self.get_batch_results(batch_id)
            
            # Sort by match_percentage descending
            ranked = sorted(
                candidates,
                key=lambda x: float(x.get('match_percentage', 0)),
                reverse=True
            )
            
            logger.info(f'Ranked {len(ranked)} candidates from batch {batch_id}')
            return ranked
        
        except Exception as e:
            logger.error(f'Failed to rank candidates in batch {batch_id}: {str(e)}', exc_info=True)
            return []
    
    def get_candidates_for_job(self, job_id):
        """
        Get all candidates that applied for a specific job (from all batches)
        
        Args:
            job_id: Job identifier
        
        Returns:
            list of candidates
        """
        try:
            table = self.dynamodb.Table(self.results_table_name)
            
            response = table.query(
                IndexName='job_id-match_percentage-index',
                KeyConditionExpression='job_id = :job_id',
                ExpressionAttributeValues={':job_id': job_id},
                ScanIndexForward=False  # Descending by match_percentage
            )
            
            candidates = response.get('Items', [])
            logger.info(f'Retrieved {len(candidates)} candidates for job {job_id}')
            return candidates
        
        except Exception as e:
            logger.error(f'Failed to get candidates for job {job_id}: {str(e)}', exc_info=True)
            return []
    
    def update_candidate_status(self, batch_id, candidate_id, status):
        """
        Update candidate match status
        
        Args:
            batch_id: Batch identifier
            candidate_id: Candidate identifier
            status: New status (strong_match, partial_match, not_qualified, etc.)
        
        Returns:
            dict with status
        """
        try:
            table = self.dynamodb.Table(self.results_table_name)
            
            table.update_item(
                Key={
                    'batch_id': batch_id,
                    'candidate_id': candidate_id
                },
                UpdateExpression='SET #status = :status, updated_at = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': status,
                    ':updated_at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f'Updated candidate {candidate_id} status to {status}')
            return {'status': 'success'}
        
        except Exception as e:
            error_msg = f'Failed to update candidate status: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'error': error_msg}
    
    def get_candidate_result(self, batch_id, resume_id):
        """
        Get a specific candidate's result
        """
        logger.info(f"Retrieving result for resume {resume_id} in batch {batch_id}")
        
        # TODO: Implement
        return {
            'status': 'pending'
        }
    
    def update_processing_status(self, batch_id, status, progress=None):
        """
        Update batch processing status
        Args:
            batch_id: str
            status: str ('pending', 'processing', 'completed', 'failed')
            progress: int (0-100)
        """
        logger.info(f"Updating status for batch {batch_id}: {status}")
        
        # TODO: Implement
        return {
            'status': 'pending'
        }
    
    def get_all_batches(self):
        """
        Get all batches with summary info (total candidates, avg match %, job_id)
        Useful for dashboard/overview page
        
        Returns:
            list of batch summaries
        """
        try:
            table = self.dynamodb.Table(self.results_table_name)
            
            # Scan all results
            all_results = []
            last_evaluated_key = None
            
            while True:
                if last_evaluated_key:
                    response = table.scan(ExclusiveStartKey=last_evaluated_key)
                else:
                    response = table.scan()
                
                all_results.extend(response.get('Items', []))
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            # Group by batch_id to create summaries
            batches_dict = {}
            for result in all_results:
                batch_id = result.get('batch_id')
                if batch_id not in batches_dict:
                    batches_dict[batch_id] = {
                        'batch_id': batch_id,
                        'job_id': result.get('job_id'),
                        'created_at': result.get('created_at'),
                        'candidates': [],
                        'total_candidates': 0,
                        'strong_matches': 0,
                        'partial_matches': 0,
                        'not_qualified': 0,
                        'avg_match_percentage': 0
                    }
                
                # Add candidate to batch
                batches_dict[batch_id]['candidates'].append({
                    'filename': result.get('filename'),
                    'match_percentage': float(result.get('match_percentage', 0)),
                    'status': result.get('status')
                })
                
                # Update status counts
                status = result.get('status', 'unknown')
                if status == 'strong_match':
                    batches_dict[batch_id]['strong_matches'] += 1
                elif status == 'partial_match':
                    batches_dict[batch_id]['partial_matches'] += 1
                elif status == 'not_qualified':
                    batches_dict[batch_id]['not_qualified'] += 1
            
            # Calculate summary stats for each batch and fetch job details
            batches_list = []
            for batch in batches_dict.values():
                total = len(batch['candidates'])
                batch['total_candidates'] = total
                if total > 0:
                    avg_match = sum([c['match_percentage'] for c in batch['candidates']]) / total
                    batch['avg_match_percentage'] = round(avg_match, 2)
                    # Remove candidates from summary (keep only aggregates)
                    batch.pop('candidates', None)
                
                # Fetch job title from job_requirements table
                if batch.get('job_id'):
                    job_data = self.get_job(batch['job_id'])
                    if job_data:
                        batch['job_title'] = job_data.get('job_title', 'Unknown')
                    else:
                        batch['job_title'] = 'Unknown'
                else:
                    batch['job_title'] = 'Unknown'
                
                batches_list.append(batch)
            
            # Sort by creation date descending (most recent first)
            batches_list.sort(
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )
            
            logger.info(f'Retrieved {len(batches_list)} batches from DynamoDB')
            return batches_list
        
        except Exception as e:
            logger.error(f'Failed to get all batches: {str(e)}', exc_info=True)
            return []
    
    def delete_batch(self, batch_id):
        """
        Delete a batch and all its results
        """
        logger.info(f"Deleting batch {batch_id}")
        
        # TODO: Implement
        return True
    
    # ==================== BATCH STATUS TRACKING ====================
    
    def create_batch_status(self, batch_id, job_id, total_files):
        """
        Create batch processing status record when upload starts
        
        Args:
            batch_id: Unique batch identifier
            job_id: Job being applied for
            total_files: Total number of resumes in batch
        
        Returns:
            dict with status
        """
        try:
            table_name = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')
            table = self.dynamodb.Table(table_name)
            created_at = datetime.utcnow().isoformat()
            
            item = {
                'batch_id': batch_id,
                'job_id': job_id,
                'total_files': total_files,
                'processed_files': 0,
                'failed_files': 0,
                'status': 'pending',  # pending -> processing -> completed
                'created_at': created_at,
                'started_at': None,
                'completed_at': None,
                'completion_percentage': 0,
                'errors': []
            }
            
            table.put_item(Item=item)
            logger.info(f'✅ Created batch status for {batch_id}: {total_files} files for job {job_id}')
            
            return {
                'status': 'success',
                'batch_id': batch_id
            }
        
        except Exception as e:
            error_msg = f'Failed to create batch status for {batch_id}: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg
            }
    
    def get_batch_status(self, batch_id):
        """
        Get current processing status of a batch
        
        Args:
            batch_id: Batch identifier
        
        Returns:
            dict with batch status or None if not found
        """
        try:
            table_name = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')
            table = self.dynamodb.Table(table_name)
            
            response = table.get_item(Key={'batch_id': batch_id})
            
            if 'Item' in response:
                batch = response['Item']
                logger.info(f'📊 Retrieved batch {batch_id} status: {batch.get("status")}')
                return batch
            else:
                logger.warning(f'Batch {batch_id} status not found')
                return None
        
        except Exception as e:
            logger.error(f'Failed to get batch status {batch_id}: {str(e)}', exc_info=True)
            return None
    
    def update_batch_status(self, batch_id, status):
        """
        Update batch overall status
        
        Args:
            batch_id: Batch identifier
            status: 'pending' | 'processing' | 'completed' | 'failed'
        
        Returns:
            dict with status
        """
        try:
            table_name = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')
            table = self.dynamodb.Table(table_name)
            
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Set timestamps based on status
            if status == 'processing':
                update_data['started_at'] = datetime.utcnow().isoformat()
            elif status == 'completed':
                update_data['completed_at'] = datetime.utcnow().isoformat()
            
            table.update_item(
                Key={'batch_id': batch_id},
                UpdateExpression='SET #status = :status, updated_at = :updated_at, started_at = if_not_exists(started_at, :started_at), completed_at = if_not_exists(completed_at, :completed_at)',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': status,
                    ':updated_at': update_data['updated_at'],
                    ':started_at': update_data.get('started_at'),
                    ':completed_at': update_data.get('completed_at')
                }
            )
            
            logger.info(f'✅ Updated batch {batch_id} status to {status}')
            return {'status': 'success'}
        
        except Exception as e:
            error_msg = f'Failed to update batch status: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'error': error_msg}
    
    def increment_batch_processed(self, batch_id):
        """
        Increment the count of processed files in a batch
        Updates completion percentage
        
        Args:
            batch_id: Batch identifier
        
        Returns:
            dict with updated counts
        """
        try:
            table_name = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')
            table = self.dynamodb.Table(table_name)
            
            # Get current batch state
            batch = self.get_batch_status(batch_id)
            if not batch:
                return {'status': 'error', 'error': 'Batch not found'}
            
            processed = batch.get('processed_files', 0) + 1
            total = batch.get('total_files', 1)
            completion_pct = (processed / total) * 100
            
            table.update_item(
                Key={'batch_id': batch_id},
                UpdateExpression='SET processed_files = :processed, completion_percentage = :completion',
                ExpressionAttributeValues={
                    ':processed': processed,
                    ':completion': round(completion_pct, 2)
                }
            )
            
            logger.info(f'✅ Batch {batch_id}: {processed}/{total} files processed ({completion_pct:.1f}%)')
            
            return {
                'status': 'success',
                'processed_files': processed,
                'total_files': total,
                'completion_percentage': round(completion_pct, 2)
            }
        
        except Exception as e:
            error_msg = f'Failed to increment batch processed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'error': error_msg}
    
    def increment_batch_error(self, batch_id, error_message=None):
        """
        Increment the error count for a batch
        
        Args:
            batch_id: Batch identifier
            error_message: Optional error description
        
        Returns:
            dict with status
        """
        try:
            table_name = os.getenv('DYNAMODB_BATCH_STATUS_TABLE', 'batch_processing_status')
            table = self.dynamodb.Table(table_name)
            
            batch = self.get_batch_status(batch_id)
            if not batch:
                return {'status': 'error', 'error': 'Batch not found'}
            
            failed_count = batch.get('failed_files', 0) + 1
            errors = batch.get('errors', [])
            
            if error_message:
                errors.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'message': error_message
                })
            
            table.update_item(
                Key={'batch_id': batch_id},
                UpdateExpression='SET failed_files = :failed, #errors = :errors',
                ExpressionAttributeNames={'#errors': 'errors'},
                ExpressionAttributeValues={
                    ':failed': failed_count,
                    ':errors': errors
                }
            )
            
            logger.warning(f'⚠️  Batch {batch_id}: Error incremented to {failed_count}')
            
            return {'status': 'success', 'failed_files': failed_count}
        
        except Exception as e:
            error_msg = f'Failed to increment batch error: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'error': error_msg}
    
    def update_resume_status(self, batch_id, candidate_id, status, error=None):
        """
        Update individual resume processing status (for Lambda)
        
        Args:
            batch_id: Batch identifier
            candidate_id: Candidate identifier
            status: 'pending' | 'processing' | 'completed' | 'failed'
            error: Optional error message if failed
        
        Returns:
            dict with status
        """
        try:
            table = self.dynamodb.Table(self.results_table_name)
            
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if status == 'processing':
                update_data['started_at'] = datetime.utcnow().isoformat()
            elif status == 'completed':
                update_data['completed_at'] = datetime.utcnow().isoformat()
            elif status == 'failed' and error:
                update_data['error'] = error
            
            expr_names = {'#status': 'status'}
            expr_values = {':status': status, ':updated_at': update_data['updated_at']}
            update_expr = 'SET #status = :status, updated_at = :updated_at'
            
            if 'started_at' in update_data:
                expr_names['#started'] = 'started_at'
                expr_values[':started'] = update_data['started_at']
                update_expr += ', #started = if_not_exists(#started, :started)'
            
            if 'completed_at' in update_data:
                expr_names['#completed'] = 'completed_at'
                expr_values[':completed'] = update_data['completed_at']
                update_expr += ', #completed = if_not_exists(#completed, :completed)'
            
            if 'error' in update_data:
                expr_names['#error'] = 'error'
                expr_values[':error'] = update_data['error']
                update_expr += ', #error = :error'
            
            table.update_item(
                Key={
                    'batch_id': batch_id,
                    'candidate_id': candidate_id
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )
            
            logger.info(f'📝 Updated resume {candidate_id} status to {status}')
            return {'status': 'success'}
        
        except Exception as e:
            error_msg = f'Failed to update resume status: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {'status': 'error', 'error': error_msg}
