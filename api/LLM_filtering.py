import google.generativeai as genai
from typing import List, Dict, Any
import os
import json
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeminiJobFilter:
    def __init__(self, api_key=None):
        """
        Initialize the Gemini Job Filter
        
        Args:
            api_key: Google API key for Gemini access (defaults to environment variable)
        """
        # Try to get API key from parameter, then from environment variable
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            logger.error("No Google API key found. Make sure to set GOOGLE_API_KEY in your .env file or pass it directly.")
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY in .env file or pass it to the constructor.")
        
        # Configure the Gemini API
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Successfully initialized Gemini API")
        except Exception as e:
            logger.error(f"Error initializing Gemini API: {e}")
            raise
    
    def filter_relevant_jobs(self, jobs: List[Dict[str, Any]], search_criteria: Dict[str, str], 
                            min_score: float = 0.3, max_jobs: int = 20) -> List[Dict[str, Any]]:
        """
        Filter jobs based on relevance to search criteria using Gemini
        
        Args:
            jobs: List of job dictionaries (from LinkedIn, Indeed, etc.)
            search_criteria: Dictionary containing user search parameters
            min_score: Minimum relevance score (0-1) for inclusion
            max_jobs: Maximum number of jobs to return
            
        Returns:
            List of relevant jobs with added relevance scores
        """
        if not jobs:
            logger.warning("No jobs provided for filtering")
            return []
        
        scored_jobs = []
        
        for job in jobs:
            try:
                # Calculate relevance score for this job
                relevance_score, reasoning = self._evaluate_job_relevance(job, search_criteria)
                
                # Add relevance data to job
                job_with_score = job.copy()
                job_with_score["relevance_score"] = relevance_score
                job_with_score["relevance_reasoning"] = reasoning
                
                # Always add the job to scored_jobs, we'll filter by min_score later
                scored_jobs.append(job_with_score)
                logger.info(f"Job '{job.get('job_title')}' scored {relevance_score}")
                
            except Exception as e:
                logger.error(f"Error evaluating job: {str(e)}")
                # Include job without score rather than dropping it
                job["relevance_score"] = 0.0
                job["relevance_reasoning"] = f"Error during evaluation: {str(e)}"
                scored_jobs.append(job)
        
        # Sort all jobs by relevance score (descending)
        sorted_jobs = sorted(scored_jobs, key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Filter by min_score
        relevant_jobs = [job for job in sorted_jobs if job.get("relevance_score", 0) >= min_score]
        
        # Return up to max_jobs
        return relevant_jobs[:max_jobs]
    
    def _evaluate_job_relevance(self, job: Dict[str, Any], criteria: Dict[str, str]) -> tuple:
        """
        Use Gemini to evaluate how well a job matches the search criteria
        
        Args:
            job: Dictionary containing job details
            criteria: Dictionary containing search criteria
            
        Returns:
            Tuple of (relevance_score, reasoning)
        """
        # Create prompt for Gemini
        prompt = self._create_evaluation_prompt(job, criteria)
        
        # Generate response from Gemini
        response = self.model.generate_content(prompt)
        
        # Parse the response
        try:
            # Extract the JSON portion from the response
            response_text = response.text
            json_str = self._extract_json_from_text(response_text)
            result = json.loads(json_str)
            
            # Extract scores
            overall_score = result.get("overall_score", 0.0)
            reasoning = result.get("reasoning", "No reasoning provided")
            
            return float(overall_score), reasoning
        
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")
            return 0.0, f"Error parsing response: {str(e)}"
    
    def _extract_json_from_text(self, text: str) -> str:
        """Extract JSON string from text that might contain other content"""
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            return text[start_idx:end_idx]
        else:
            raise ValueError("No valid JSON found in response")
    
    def _create_evaluation_prompt(self, job: Dict[str, Any], criteria: Dict[str, str]) -> str:
        """
        Create a prompt for Gemini to evaluate job relevance
        
        Args:
            job: Job details
            criteria: Search criteria
            
        Returns:
            Prompt string
        """
        job_details = f"""
JOB DETAILS:
- Title: {job.get('job_title', 'Not specified')}
- Company: {job.get('company', 'Not specified')}
- Experience: {job.get('experience', 'Not specified')}
- Job Nature: {job.get('jobNature', 'Not specified')}
- Location: {job.get('location', 'Not specified')}
- Salary: {job.get('salary', 'Not specified')}
- Description: {job.get('description', 'No description available')}
        """
        
        search_criteria = f"""
SEARCH CRITERIA:
- Position: {criteria.get('position', 'Not specified')}
- Experience: {criteria.get('experience', 'Not specified')}
- Salary: {criteria.get('salary', 'Not specified')}
- Job Nature: {criteria.get('jobNature', 'Not specified')}
- Location: {criteria.get('location', 'Not specified')}
- Skills: {criteria.get('skills', 'Not specified')}
        """
        
        instructions = """
TASK: Evaluate how well this job matches the search criteria.

For each criterion, assign a score from 0.0 to 1.0:
1. Title/Position match (Is the job title similar or relevant to the position sought?)
2. Experience match (Does the required experience align with the search criteria?)
3. Location match (Is the job in the desired location?)
4. Job Nature match (Does remote/onsite/hybrid status match?)
5. Salary match (Is the salary in the desired range? If not specified, score 0.5)
6. Skills match (What percentage of required skills are mentioned in the job?)

Then calculate an overall score (average of all criteria).

IMPORTANT: Return your response in this EXACT JSON format:
{
  "title_score": <float between 0-1>,
  "experience_score": <float between 0-1>,
  "location_score": <float between 0-1>,
  "nature_score": <float between 0-1>,
  "salary_score": <float between 0-1>,
  "skills_score": <float between 0-1>,
  "overall_score": <float between 0-1>,
  "reasoning": "<brief explanation of the scores>"
}
"""
        
        return f"{job_details}\n\n{search_criteria}\n\n{instructions}"


# # Usage example
# if __name__ == "__main__":
#     # Set API key - replace with your actual key or set it as an environment variable
#     os.environ["GOOGLE_API_KEY"] = ""
    
#     # Test job
#     test_job = {
#         "job_title": "Full Stack Engineer",
#         "company": "XYZ Pvt Ltd",
#         "experience": "2+ years",
#         "jobNature": "onsite",
#         "location": "Islamabad, Pakistan",
#         "salary": "100,000 PKR",
#         "apply_link": "https://linkedin.com/job123",
#         "description": "Looking for a Full Stack Developer with experience in MERN stack. Skills needed: React, Node.js, MongoDB, Express, JavaScript, HTML/CSS."
#     }
    
#     # Test criteria
#     test_criteria = {
#         "position": "Full Stack Engineer",
#         "experience": "2 years",
#         "salary": "70,000 PKR to 120,000 PKR",
#         "jobNature": "onsite",
#         "location": "Pakistan",
#         "skills": "full stack, MERN, Node.js, Express.js, React.js, Next.js, Firebase"
#     }
    
#     try:
#         # Initialize the filter
#         job_filter = GeminiJobFilter()
        
#         # Test single job relevance
#         score, reasoning = job_filter._evaluate_job_relevance(test_job, test_criteria)
#         print(f"Relevance score: {score}")
#         print(f"Reasoning: {reasoning}")
        
#         # Test filtering multiple jobs
#         filtered_jobs = job_filter.filter_relevant_jobs([test_job, test_job], test_criteria)
#         print(f"Filtered {len(filtered_jobs)} jobs")
        
#     except Exception as e:
#         print(f"Error during testing: {str(e)}")