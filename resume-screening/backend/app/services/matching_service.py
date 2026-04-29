import logging
from app.services.comprehend_service import ComprehendService
from app.services.dynamodb_service import DynamoDBService

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for orchestrating skill matching between jobs and candidates"""
    
    def __init__(self):
        self.comprehend_service = ComprehendService()
        self.dynamodb_service = DynamoDBService()
    
    def match_candidate_to_job(self, job_id, candidate_skills, candidate_experience_level):
        """
        Match a candidate's skills against job requirements
        
        Args:
            job_id: Job identifier
            candidate_skills: List of skills extracted from candidate's resume
            candidate_experience_level: Experience level (Senior, Junior, etc.)
        
        Returns:
            dict with:
                - matched_skills: List of matched required skills
                - missing_skills: List of required skills candidate doesn't have
                - bonus_skills: Skills candidate has that aren't required
                - match_percentage: Overall match percentage (0-100)
                - status: strong_match, partial_match, not_qualified
                - match_details: Detailed breakdown
        """
        try:
            # Get job requirements from DynamoDB
            job = self.dynamodb_service.get_job(job_id)
            
            if not job:
                logger.warning(f'Job {job_id} not found in DynamoDB')
                return {
                    'status': 'error',
                    'error': f'Job {job_id} not found'
                }
            
            required_skills = job.get('required_skills', [])
            job_experience_level = job.get('experience_level')
            job_experience_years = job.get('experience_years', 0)
            
            # Call comprehend service to match skills
            match_result = self.comprehend_service.match_skills(
                required_skills,
                candidate_skills
            )
            
            if match_result['status'] != 'success':
                return match_result
            
            # Calculate final match score and status
            match_percentage = match_result.get('match_percentage', 0)
            
            # Determine match status based on percentage
            if match_percentage >= 80:
                match_status = 'strong_match'
            elif match_percentage >= 50:
                match_status = 'partial_match'
            else:
                match_status = 'not_qualified'
            
            # Add experience level analysis
            experience_match = self._analyze_experience_level(
                candidate_experience_level,
                job_experience_level
            )
            
            logger.info(f'Job {job_id}: Candidate match {match_percentage}% ({match_status})')
            
            return {
                'status': 'success',
                'matched_skills': match_result.get('matched_skills', []),
                'missing_skills': match_result.get('missing_skills', []),
                'bonus_skills': match_result.get('bonus_skills', []),
                'match_percentage': match_result.get('match_percentage', 0),
                'total_required': match_result.get('total_required', 0),
                'total_matched': match_result.get('total_matched', 0),
                'match_status': match_status,
                'experience_match': experience_match,
                'match_details': {
                    'required_skills': required_skills,
                    'candidate_skills': [s['skill'] if isinstance(s, dict) else s for s in candidate_skills],
                    'job_experience_level': job_experience_level,
                    'job_experience_years': job_experience_years,
                    'candidate_experience_level': candidate_experience_level
                }
            }
        
        except Exception as e:
            error_msg = f'Skill matching failed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg
            }
    
    def save_match_result(self, batch_id, candidate_id, job_id, filename, 
                         candidate_skills, job_titles, experience_level,
                         textract_confidence, comprehend_confidence, match_result,
                         s3_url=None):
        """
        Save match result to DynamoDB along with all candidate data
        
        Args:
            batch_id: Batch identifier
            candidate_id: Candidate identifier
            job_id: Job identifier
            filename: Resume filename
            candidate_skills: List of extracted skills
            job_titles: List of extracted job titles
            experience_level: Extracted experience level
            textract_confidence: Textract confidence score
            comprehend_confidence: Comprehend confidence score
            match_result: Result from match_candidate_to_job()
            s3_url: S3 URL where resume is stored (optional)
        
        Returns:
            dict with save status
        """
        try:
            if match_result['status'] != 'success':
                logger.warning(f'Not saving batch {batch_id}, candidate {candidate_id}: matching failed')
                return {
                    'status': 'error',
                    'error': 'Matching failed'
                }
            
            # Prepare candidate data for storage
            candidate_data = {
                'job_id': job_id,
                'filename': filename,
                'extracted_skills': candidate_skills,
                'job_titles': job_titles,
                'experience_level': experience_level,
                'textract_confidence': textract_confidence,
                'comprehend_confidence': comprehend_confidence,
                'match_percentage': match_result['match_percentage'],
                'matched_skills': match_result['matched_skills'],
                'missing_skills': match_result['missing_skills'],
                'bonus_skills': match_result['bonus_skills'],
                'status': match_result['match_status']
            }
            
            # Add S3 URL if provided
            if s3_url:
                candidate_data['s3_url'] = s3_url
            
            # Save to DynamoDB
            save_result = self.dynamodb_service.save_candidate_match(
                batch_id,
                candidate_id,
                candidate_data
            )
            
            return save_result
        
        except Exception as e:
            error_msg = f'Failed to save match result: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg
            }
    
    def get_batch_ranked_results(self, batch_id):
        """
        Get all candidates in a batch ranked by match percentage
        
        Args:
            batch_id: Batch identifier
        
        Returns:
            list of candidates ranked from best to worst match
        """
        try:
            ranked_candidates = self.dynamodb_service.rank_candidates(batch_id)
            logger.info(f'Retrieved ranked results for batch {batch_id}: {len(ranked_candidates)} candidates')
            return ranked_candidates
        
        except Exception as e:
            logger.error(f'Failed to get ranked results: {str(e)}', exc_info=True)
            return []
    
    def get_job_candidates(self, job_id):
        """
        Get all candidates for a job across all batches, ranked by match
        
        Args:
            job_id: Job identifier
        
        Returns:
            list of candidates ranked from best to worst match
        """
        try:
            candidates = self.dynamodb_service.get_candidates_for_job(job_id)
            logger.info(f'Retrieved {len(candidates)} candidates for job {job_id}')
            return candidates
        
        except Exception as e:
            logger.error(f'Failed to get job candidates: {str(e)}', exc_info=True)
            return []
    
    def _analyze_experience_level(self, candidate_level, job_level):
        """
        Analyze if candidate's experience level meets job requirements
        
        Args:
            candidate_level: Candidate's experience level (Senior, Mid-level, Junior, etc.)
            job_level: Required experience level
        
        Returns:
            dict with analysis
        """
        try:
            level_hierarchy = {
                'intern': 1,
                'entry-level': 2,
                'junior': 2,
                'mid-level': 3,
                'mid': 3,
                'senior': 4,
                'lead': 5,
                'principal': 5,
                'staff': 5
            }
            
            candidate_score = level_hierarchy.get(candidate_level.lower() if candidate_level else None, 0)
            job_score = level_hierarchy.get(job_level.lower() if job_level else None, 0)
            
            if not job_level:
                return {
                    'meets_requirement': True,
                    'reason': 'No experience level requirement specified'
                }
            
            if candidate_score >= job_score:
                return {
                    'meets_requirement': True,
                    'reason': f'Candidate level ({candidate_level}) meets or exceeds requirement ({job_level})'
                }
            else:
                return {
                    'meets_requirement': False,
                    'reason': f'Candidate level ({candidate_level}) below requirement ({job_level})'
                }
        
        except Exception as e:
            logger.warning(f'Failed to analyze experience level: {str(e)}')
            return {
                'meets_requirement': None,
                'reason': 'Could not determine experience level match'
            }
