import logging
import boto3
from botocore.config import Config
from config import config
import re

logger = logging.getLogger(__name__)


class ComprehendService:
    """Service for AWS Comprehend NLP integration"""
    
    def __init__(self):
        self.region = config.AWS_REGION
        
        # Initialize Comprehend client with adaptive retry strategy
        retry_config = Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'
            },
            read_timeout=60
        )
        
        self.client = boto3.client(
            'comprehend',
            region_name=self.region,
            config=retry_config,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
        )
        
        # Common tech skills for enhanced matching
        self.tech_skills = {
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Rust', 'PHP', 'Ruby',
            'AWS', 'Azure', 'GCP', 'Google Cloud', 'Kubernetes', 'Docker', 'Terraform',
            'FastAPI', 'Django', 'Flask', 'Spring', 'Node.js', 'React', 'Vue', 'Angular',
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch', 'Firebase',
            'Git', 'Jenkins', 'CI/CD', 'DevOps', 'Linux', 'Windows', 'macOS',
            'Machine Learning', 'ML', 'AI', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Scikit-learn',
            'SQL', 'NoSQL', 'REST', 'GraphQL', 'gRPC', 'SOAP',
            'Microservices', 'Agile', 'Scrum', 'Kanban', 'Waterfall'
        }
    
    def extract_skills(self, text):
        """
        Extract skills and entities from resume/candidate text
        
        Args:
            text: Resume text to analyze
            
        Returns:
            dict with:
                - status: 'success' or 'error'
                - skills: List of technical skills found
                - job_titles: List of job titles/roles
                - experience_level: Level extracted (Senior, Junior, etc.)
                - skill_count: Number of skills found
                - error: Error message if status is 'error'
        """
        logger.info(f'Extracting skills from text (length: {len(text)})')
        
        try:
            # Call Comprehend to detect entities
            response = self.client.detect_entities(
                Text=text,
                LanguageCode='en'
            )
            
            # Parse entities
            skills = []
            job_titles = []
            experience_level = None
            
            for entity in response.get('Entities', []):
                entity_text = entity['Text'].strip()
                entity_type = entity['Type']
                confidence = entity['Score']
                
                # Extract skills (match against our tech skills list)
                if self._is_tech_skill(entity_text):
                    skills.append({
                        'skill': entity_text,
                        'type': entity_type,
                        'confidence': round(confidence, 3)
                    })
                
                # Extract job titles
                if entity_type == 'TITLE':
                    job_titles.append({
                        'title': entity_text,
                        'confidence': round(confidence, 3)
                    })
                
                # Extract experience level
                if self._is_experience_level(entity_text):
                    experience_level = entity_text
            
            # Also extract skills using key phrases (catches more variations)
            key_phrase_skills = self._extract_skills_from_keyphrases(text)
            
            # Merge skills, avoid duplicates
            all_skills = {}
            for skill_dict in skills:
                skill_key = skill_dict['skill'].lower()
                all_skills[skill_key] = skill_dict
            
            for skill in key_phrase_skills:
                skill_key = skill.lower()
                if skill_key not in all_skills:
                    all_skills[skill_key] = {
                        'skill': skill,
                        'type': 'SKILL',
                        'confidence': 0.95
                    }
            
            logger.info(f'Extracted {len(all_skills)} skills, level: {experience_level}')
            
            return {
                'status': 'success',
                'skills': list(all_skills.values()),
                'job_titles': job_titles,
                'experience_level': experience_level,
                'skill_count': len(all_skills)
            }
        
        except Exception as e:
            error_msg = f'Skill extraction failed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg,
                'skills': [],
                'job_titles': [],
                'experience_level': None,
                'skill_count': 0
            }
    
    def parse_job_description(self, job_text):
        """
        Extract requirements from job description
        
        Args:
            job_text: Job description text to analyze
            
        Returns:
            dict with:
                - status: 'success' or 'error'
                - job_title: Extracted job title
                - required_skills: List of required skills
                - nice_to_have_skills: List of preferred skills
                - experience_level: Required level
                - experience_years: Years of experience required
                - error: Error message if status is 'error'
        """
        logger.info(f'Parsing job description (length: {len(job_text)})')
        
        try:
            # Extract job title first
            job_title = self._extract_job_title(job_text)
            
            # Call Comprehend to detect entities
            response = self.client.detect_entities(
                Text=job_text,
                LanguageCode='en'
            )
            
            required_skills = []
            nice_to_have_skills = []
            experience_level = None
            experience_years = None
            
            # Parse entities
            for entity in response.get('Entities', []):
                entity_text = entity['Text'].strip()
                entity_type = entity['Type']
                confidence = entity['Score']
                
                # Extract skills
                if self._is_tech_skill(entity_text):
                    # Check if it's marked as required or preferred
                    if self._is_required(job_text, entity_text):
                        required_skills.append({
                            'skill': entity_text,
                            'confidence': round(confidence, 3)
                        })
                    else:
                        nice_to_have_skills.append({
                            'skill': entity_text,
                            'confidence': round(confidence, 3)
                        })
                
                # Extract experience level
                if self._is_experience_level(entity_text):
                    experience_level = entity_text
                
                # Extract years of experience (if it's a quantity)
                if entity_type == 'QUANTITY':
                    match = re.search(r'(\d+)\+?', entity_text)
                    if match:
                        experience_years = int(match.group(1))
            
            # Also extract from key phrases
            keyphrases = self._extract_from_keyphrases(job_text)
            for skill in keyphrases:
                skill_dict = {'skill': skill, 'confidence': 0.92}
                if skill not in [s['skill'].lower() for s in required_skills]:
                    required_skills.append(skill_dict)
            
            logger.info(f'Parsed job: {len(required_skills)} required skills, title: {job_title}')
            
            return {
                'status': 'success',
                'job_title': job_title,
                'required_skills': required_skills,
                'nice_to_have_skills': nice_to_have_skills,
                'experience_level': experience_level,
                'experience_years': experience_years
            }
        
        except Exception as e:
            error_msg = f'Job parsing failed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg,
                'job_title': None,
                'required_skills': [],
                'nice_to_have_skills': [],
                'experience_level': None
            }
    
    def match_skills(self, job_required_skills, candidate_skills):
        """
        Compare job requirements with candidate skills
        
        Args:
            job_required_skills: List of required skills from job
            candidate_skills: List of candidate skills
            
        Returns:
            dict with match analysis
        """
        logger.info('Matching skills between job and candidate')
        
        try:
            # Extract skill names (lowercase for comparison)
            job_skills_list = [s if isinstance(s, str) else s.get('skill', '') for s in job_required_skills]
            candidate_skills_list = [s if isinstance(s, str) else s.get('skill', '') for s in candidate_skills]
            
            job_skills_lower = [s.lower() for s in job_skills_list]
            cand_skills_lower = [s.lower() for s in candidate_skills_list]
            
            # Calculate matches
            matched = []
            for job_skill in job_skills_lower:
                for cand_skill in cand_skills_lower:
                    if self._skill_matches(job_skill, cand_skill):
                        matched.append(job_skill)
                        break
            
            missing = [s for s in job_skills_lower if s not in matched]
            bonus = [s for s in cand_skills_lower if s not in job_skills_lower and not any(self._skill_matches(s, m) for m in job_skills_lower)]
            
            match_percentage = (len(matched) / len(job_skills_lower) * 100) if job_skills_lower else 0
            
            logger.info(f'Match: {len(matched)}/{len(job_skills_lower)} skills ({match_percentage:.1f}%)')
            
            return {
                'status': 'success',
                'matched_skills': matched,
                'missing_skills': missing,
                'bonus_skills': bonus,
                'match_percentage': round(match_percentage, 2),
                'total_required': len(job_skills_lower),
                'total_matched': len(matched)
            }
        
        except Exception as e:
            error_msg = f'Skill matching failed: {str(e)}'
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'error': error_msg,
                'matched_skills': [],
                'missing_skills': [],
                'bonus_skills': []
            }
    
    # Helper methods
    
    def _extract_job_title(self, job_text):
        """
        Extract job title from job description
        Looks for:
        1. First line (common for "Senior Python Developer" format)
        2. "Position: " or "Job Title: " patterns
        3. TITLE entities from Comprehend
        
        Args:
            job_text: Job description text
            
        Returns:
            Job title string or None
        """
        try:
            # Try to extract from first line (common format)
            first_line = job_text.split('\n')[0].strip()
            if first_line and len(first_line) < 100 and any(word in first_line.lower() for word in ['senior', 'junior', 'manager', 'engineer', 'developer', 'analyst', 'designer', 'lead', 'architect']):
                return first_line
            
            # Look for explicit patterns
            patterns = [
                r'(?:Position|Job Title|Role):\s*([^\n]+)',
                r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:-|–|—)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, job_text, re.MULTILINE | re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                    if len(title) < 100:
                        return title
            
            # Use Comprehend to detect entities (backup)
            response = self.client.detect_entities(
                Text=job_text[:500],  # Use first 500 chars for title detection
                LanguageCode='en'
            )
            
            for entity in response.get('Entities', []):
                if entity['Type'] == 'TITLE':
                    return entity['Text'].strip()
            
            # Fallback to first meaningful line
            lines = job_text.split('\n')
            for line in lines[:5]:  # Check first 5 lines
                line = line.strip()
                if line and len(line) > 3 and len(line) < 100:
                    # Avoid common non-title lines
                    if not any(word in line.lower() for word in ['please', 'read', 'click', 'apply', 'submit']):
                        return line
            
            return None
        
        except Exception as e:
            logger.warning(f'Job title extraction failed: {str(e)}')
            return None
    
    def _is_tech_skill(self, text):
        """Check if text is a technical skill"""
        if not text or len(text) < 2:
            return False
        
        text_lower = text.lower()
        
        # Check against known tech skills
        for skill in self.tech_skills:
            if skill.lower() == text_lower or skill.lower() in text_lower:
                return True
        
        # Check for common patterns
        if any(text_lower.endswith(suffix) for suffix in ['api', 'db', 'sql', 'js', 'ml', 'ai', 'orm']):
            return True
        
        # Version numbers (Python3, Node.js)
        if re.search(r'\.js|\.py|\d+\.x|\d+\.\d+', text, re.IGNORECASE):
            return True
        
        return False
    
    def _is_experience_level(self, text):
        """Check if text is an experience level"""
        levels = ['junior', 'mid-level', 'senior', 'lead', 'principal', 'staff', 'intern', 'entry-level']
        return text.lower() in levels
    
    def _is_required(self, text, skill):
        """Check if skill is marked as required in context"""
        text_lower = text.lower()
        skill_pos = text_lower.find(skill.lower())
        
        if skill_pos == -1:
            return True
        
        # Check 100 chars before skill
        context = text_lower[max(0, skill_pos - 100):skill_pos + 50]
        
        required_words = ['required', 'must', 'essential', 'mandatory']
        preferred_words = ['preferred', 'nice to have', 'optional', 'plus']
        
        has_required = any(word in context for word in required_words)
        has_preferred = any(word in context for word in preferred_words)
        
        return has_required or not has_preferred
    
    def _extract_skills_from_keyphrases(self, text):
        """Extract skills using key phrase detection"""
        try:
            response = self.client.detect_key_phrases(
                Text=text,
                LanguageCode='en'
            )
            
            skills = []
            for phrase in response.get('KeyPhrases', []):
                phrase_text = phrase['Text'].strip()
                if self._is_tech_skill(phrase_text):
                    skills.append(phrase_text)
            
            return skills
        
        except Exception as e:
            logger.warning(f'Key phrase extraction failed: {str(e)}')
            return []
    
    def _extract_from_keyphrases(self, text):
        """Extract potential skills from key phrases"""
        try:
            response = self.client.detect_key_phrases(
                Text=text,
                LanguageCode='en'
            )
            
            skills = []
            for phrase in response.get('KeyPhrases', []):
                phrase_text = phrase['Text'].strip()
                if self._is_tech_skill(phrase_text):
                    skills.append(phrase_text)
            
            return skills
        
        except Exception as e:
            logger.warning(f'Key phrase extraction failed: {str(e)}')
            return []
    
    def _skill_matches(self, skill1, skill2):
        """Check if two skills match"""
        s1 = skill1.lower().strip()
        s2 = skill2.lower().strip()
        
        # Exact match
        if s1 == s2:
            return True
        
        # Substring match
        if s1 in s2 or s2 in s1:
            return True
        
        # Known aliases
        aliases = {
            'js': 'javascript',
            'py': 'python',
            'ts': 'typescript',
            'gcp': 'google cloud',
            'k8s': 'kubernetes'
        }
        
        if s1 in aliases and aliases[s1] == s2:
            return True
        if s2 in aliases and aliases[s2] == s1:
            return True
        
        return False
