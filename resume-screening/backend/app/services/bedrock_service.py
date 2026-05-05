"""
Bedrock Service for Candidate-Job Fit Analysis
Uses Claude 3.5 Haiku via Bedrock Agent to analyze candidate-job fit
"""

import json
import boto3
import logging
import re
from botocore.config import Config
from config import config

logger = logging.getLogger(__name__)


class BedrockService:
    """Service for AWS Bedrock Agent integration with Claude 3.5 Haiku"""
    
    def __init__(self):
        """Initialize Bedrock client"""
        retry_config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            read_timeout=60
        )
        
        self.client = boto3.client(
            'bedrock-agent-runtime',
            region_name=config.BEDROCK_REGION,
            config=retry_config
        )
        
        self.agent_id = config.BEDROCK_AGENT_ID
        self.agent_alias = config.BEDROCK_AGENT_ALIAS
        
        logger.info(f"Bedrock Service initialized - Agent: {self.agent_id}")
        
        if not self.agent_id or not self.agent_alias:
            logger.warning("⚠️ Bedrock Agent credentials not fully configured")
    
    def score_candidate_fit(self, candidate_data, job_data):
        """
        Score candidate fit for job using Bedrock Agent with Claude
        
        Args:
            candidate_data: {
                'candidate_id': 'cand-001',
                'name': 'John Doe',
                'resume_text': '...',
                'resume_skills': ['Python', 'AWS'],
                'resume_match_percentage': 65,
                'experience_years': 5,
                'education': 'BS Computer Science'
            }
            job_data: {
                'job_title': 'Senior Python Developer',
                'job_description': '...',
                'required_skills': ['Python', 'AWS', 'Docker'],
                'nice_to_have_skills': ['Kubernetes']
            }
        
        Returns: {
            'fit_score': 72,
            'reasoning': 'Strong Python background...',
            'strengths': ['strength 1', 'strength 2'],
            'gaps': ['gap 1', 'gap 2'],
            'recommendation': 'INTERVIEW' | 'MAYBE' | 'PASS'
        }
        """
        
        try:
            if not self.agent_id:
                logger.error("Bedrock Agent ID not configured")
                return self._default_response("Bedrock not configured")
            
            # Build prompt for the agent
            prompt = self._build_prompt(candidate_data, job_data)
            
            logger.info(f"📤 Invoking Bedrock Agent for candidate: {candidate_data.get('name', 'Unknown')}")
            
            # Invoke the agent
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias,
                sessionId=candidate_data.get('candidate_id', 'default-session'),
                inputText=prompt
            )
            
            logger.info(f"✅ Agent invoked successfully")
            
            # Parse response
            result = self._parse_response(response)
            return result
            
        except Exception as e:
            logger.error(f"❌ Bedrock error: {str(e)}")
            return self._default_response(f"Error: {str(e)}")
    
    def _build_prompt(self, candidate_data, job_data):
        """Build structured prompt for the agent"""
        prompt = f"""Analyze this candidate for the job opening:

CANDIDATE PROFILE:
- Name: {candidate_data.get('name', 'Unknown')}
- Skills: {', '.join(candidate_data.get('resume_skills', []))}
- Experience: {candidate_data.get('experience_years', 0)} years
- Resume Match Score: {candidate_data.get('resume_match_percentage', 0)}%
- Education: {candidate_data.get('education', 'Not specified')}

Resume Excerpt:
{candidate_data.get('resume_text', '')[:500]}...

JOB OPENING:
- Title: {job_data.get('job_title', 'Unknown')}
- Required Skills: {', '.join(job_data.get('required_skills', []))}
- Nice to Have: {', '.join(job_data.get('nice_to_have_skills', []))}

Job Description:
{job_data.get('job_description', '')[:500]}...

ASSESSMENT REQUIRED:
Return a JSON object with EXACTLY this structure - no additional text:
{{
    "fit_score": <0-100 integer>,
    "reasoning": "Brief explanation of the fit",
    "strengths": ["strength 1", "strength 2"],
    "gaps": ["gap 1", "gap 2"],
    "recommendation": "INTERVIEW" or "MAYBE" or "PASS"
}}"""
        
        return prompt
    
    def _parse_response(self, response):
        """Parse agent response and extract JSON"""
        try:
            result_text = ""
            
            # Extract text from event stream
            for event in response.get('completion', []):
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        result_text += chunk['bytes'].decode('utf-8')
            
            logger.info(f"📝 Agent response received ({len(result_text)} chars)")
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate required fields
                required_fields = ['fit_score', 'reasoning', 'strengths', 'gaps', 'recommendation']
                if all(field in result for field in required_fields):
                    parsed = {
                        'fit_score': min(100, max(0, int(result.get('fit_score', 50)))),
                        'reasoning': str(result.get('reasoning', 'N/A'))[:500],
                        'strengths': result.get('strengths', [])[:5],
                        'gaps': result.get('gaps', [])[:5],
                        'recommendation': result.get('recommendation', 'MAYBE')
                    }
                    logger.info(f"✅ Parsed result: score={parsed['fit_score']}, recommendation={parsed['recommendation']}")
                    return parsed
            
            logger.warning("Could not extract valid JSON from response")
            return self._default_response("Invalid response format")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            return self._default_response("JSON parsing failed")
        except Exception as e:
            logger.error(f"Parse error: {str(e)}")
            return self._default_response(f"Parse error: {str(e)}")
    
    def _default_response(self, error_msg="Analysis unavailable"):
        """Return default response on error"""
        return {
            'fit_score': 50,
            'reasoning': error_msg,
            'strengths': [],
            'gaps': [],
            'recommendation': 'MAYBE'
        }
    
    # Legacy methods for compatibility
    def score_candidate(self, candidate_data, job_requirements):
        """Legacy method - redirects to new scoring"""
        return self.score_candidate_fit(candidate_data, job_requirements)
    
    def generate_interview_prompt(self, candidate_data, job_role):
        """Generate personalized interview prompt"""
        return {'prompt': '', 'status': 'pending'}
    
    def analyze_fit(self, resume_text, job_description):
        """Comprehensive analysis of candidate-job fit"""
        return {'analysis': '', 'fit_percentage': 0, 'status': 'pending'}
