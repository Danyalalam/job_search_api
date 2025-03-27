import os
import json
import logging
import requests
import re
import traceback
from typing import List, Dict, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SerpApiJobScraper:
    def __init__(self, api_key=None):
        """
        Initialize the SerpApi Job Scraper using direct API access
        
        Args:
            api_key: SERPAPI API key (defaults to environment variable)
        """
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")
        
        if not self.api_key:
            logger.error("No SERPAPI API key found. Make sure to set SERPAPI_API_KEY in your .env file or pass it directly.")
            raise ValueError("SERPAPI API key is required. Set SERPAPI_API_KEY in .env file or pass it to the constructor.")
        
        logger.info("Successfully initialized SerpApi Job Scraper")
        
    def scrape_jobs(self, title: str, location: str, max_jobs: int = 10) -> List[Dict[str, Any]]:
        """
        Scrape job listings using SERPAPI
        
        Args:
            title: Job title to search for
            location: Location to search in
            max_jobs: Maximum number of jobs to return
            
        Returns:
            List of job details dictionaries
        """
        try:
            # Format query
            query = f"{title}"
            logger.info(f"Searching for: {query} in {location}")
            
            # Prepare API parameters
            params = {
                "engine": "google_jobs",
                "q": query,
                "location": location,
                "hl": "en",
                "api_key": self.api_key
            }
            
            # Make direct API call
            response = requests.get("https://serpapi.com/search", params=params)
            
            if response.status_code != 200:
                logger.error(f"API request failed with status code {response.status_code}")
                logger.error(f"Response text: {response.text}")
                return []
            
            # Parse JSON response
            results = response.json()
            
            # Debug the response structure
            if "error" in results:
                logger.error(f"API returned an error: {results['error']}")
                return []
            
            # Extract jobs data
            jobs_data = results.get("jobs_results", [])
            
            if not jobs_data:
                logger.warning("No jobs found in API response")
                logger.info(f"Response structure: {json.dumps(list(results.keys()), indent=2)}")
                return []
            
            logger.info(f"Found {len(jobs_data)} jobs in API response")
            
            # Limit to max_jobs
            jobs_data = jobs_data[:min(len(jobs_data), max_jobs)]
            
            # Format job data to match our standard structure
            formatted_jobs = []
            
            for job in jobs_data:
                # Print a sample job structure for debugging
                if len(formatted_jobs) == 0:
                    logger.info(f"Sample job structure: {json.dumps(job, indent=2)}")
                
                # Extract job description for text analysis
                description = job.get("description", "")
                
                formatted_job = {
                    "job_title": job.get("title", "Not specified"),
                    "company": job.get("company_name", "Not specified"),
                    "location": job.get("location", "Not specified"),
                    "description": description,
                    "jobNature": self._extract_job_nature(job, description),
                    "experience": self._extract_experience(job, description),
                    "salary": self._extract_salary(job, description),
                    "apply_link": self._extract_apply_link(job)
                }
                
                # Add job to results
                formatted_jobs.append(formatted_job)
            
            logger.info(f"Successfully formatted {len(formatted_jobs)} jobs")
            return formatted_jobs
            
        except Exception as e:
            logger.error(f"Error in scrape_jobs: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def _extract_job_nature(self, job: Dict, description: str) -> str:
        """Extract job nature (remote, onsite, hybrid) from job data"""
        try:
            # First check detected extensions
            if "detected_extensions" in job and "work_from_home" in job["detected_extensions"]:
                if job["detected_extensions"]["work_from_home"]:
                    return "remote"
            
            # Then check the description text
            description_lower = description.lower()
            
            # Look for hybrid indicators
            hybrid_patterns = [
                r'hybrid',
                r'remote.{1,30}onsite',
                r'onsite.{1,30}remote',
                r'(in.?office|in.?person).{1,30}remote',
                r'remote.{1,30}(in.?office|in.?person)',
                r'work (from|at) (home|office)'
            ]
            for pattern in hybrid_patterns:
                if re.search(pattern, description_lower):
                    return "hybrid"
            
            # Look for remote-only indicators
            remote_patterns = [
                r'\bremote\b',
                r'\bwork from home\b',
                r'\bwfh\b',
                r'\bvirtual\b',
                r'\btelework\b'
            ]
            # If these patterns exist and no conflicting onsite indicators
            if any(re.search(pattern, description_lower) for pattern in remote_patterns):
                # Check if there are explicit statements about remote work
                if not re.search(r'not remote|no remote|not work from home', description_lower):
                    return "remote"
            
            # Look for onsite indicators
            onsite_patterns = [
                r'\bonsite\b',
                r'\bon.?site\b',
                r'\bin.?office\b',
                r'\bin.?person\b',
                r'work location:\s*in person',
                r'must be in (the )?office'
            ]
            if any(re.search(pattern, description_lower) for pattern in onsite_patterns):
                return "onsite"
            
            # Default if no clear indicators
            return "Not specified"
            
        except Exception:
            logger.error("Error extracting job nature", exc_info=True)
            return "Not specified"
    
    def _extract_experience(self, job: Dict, description: str) -> str:
        """Extract experience requirements from job data"""
        try:
            # First check the detected extensions
            if "detected_extensions" in job and "work_experience" in job["detected_extensions"]:
                return job["detected_extensions"]["work_experience"]
                
            # Then try highlights
            if "highlights" in job and "years_of_experience" in job["highlights"]:
                return job["highlights"]["years_of_experience"]
                
            # Finally, try patterns in the description
            experience_patterns = [
                r'(\d+[\+]?\s*(-|to)\s*\d+[\+]?\s*years?(\s*of)?\s*experience)',
                r'(minimum\s*of\s*\d+[\+]?\s*years?(\s*of)?\s*experience)',
                r'(\d+[\+]?\s*years?(\s*of)?\s*experience)',
                r'(experience\s*.*\d+[\+]?\s*years?)',
                r'(at least \d+[\+]? years?)'
            ]
            
            for pattern in experience_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    return match.group(0).strip()
            
            return "Not specified"
            
        except Exception:
            logger.error("Error extracting experience", exc_info=True)
            return "Not specified"
    
    def _extract_salary(self, job: Dict, description: str) -> str:
        """Extract salary information from job data"""
        try:
            # First check if salary is directly available
            if "salary" in job:
                return job["salary"]
                
            # Then check detected extensions
            if "detected_extensions" in job and "salary" in job["detected_extensions"]:
                return job["detected_extensions"]["salary"]
                
            # Then try to find in the description
            salary_patterns = [
                r'(salary\s*:\s*[\$£₹₨]?[\d,.]+[kK]?[\s\-]*[\$£₹₨]?[\d,.]+[kK]?)',
                r'([\$£₹₨][\d,.]+[kK]?[\s\-]*[\$£₹₨]?[\d,.]+[kK]?\s*per\s*(month|year|annum))',
                r'([\d,.]+[kK]?[\s\-]*[\d,.]+[kK]?\s*(PKR|Rs|INR|USD|GBP))',
                r'((PKR|Rs|INR|USD|GBP)\s*[\d,.]+[kK]?[\s\-]*[\d,.]+[kK]?)',
                r'(salary range.*?[\d,.]+[kK]?[\s\-]*[\d,.]+[kK]?)'
            ]
            
            for pattern in salary_patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    return match.group(0).strip()
            
            return "Not specified"
            
        except Exception:
            logger.error("Error extracting salary", exc_info=True)
            return "Not specified"
    
    def _extract_apply_link(self, job: Dict) -> str:
        """Extract the apply link from job data"""
        try:
            # Check apply_options first (this contains the actual apply links)
            if "apply_options" in job and len(job["apply_options"]) > 0:
                first_option = job["apply_options"][0]
                if "link" in first_option:
                    return first_option["link"]
            
            # Fall back to other possible link fields
            return job.get("apply_link", 
                   job.get("via", 
                   job.get("share_link", "#")))
            
        except Exception:
            logger.error("Error extracting apply link", exc_info=True)
            return "#"


def main():
    """Test the SerpApiJobScraper"""
    try:
        # Make sure you have SERPAPI_API_KEY in your .env file
        load_dotenv()
        api_key = os.getenv("SERPAPI_API_KEY")
        
        if not api_key:
            print("SERPAPI_API_KEY not found in .env file")
            return
            
        print(f"Using SERPAPI key: {api_key[:5]}...{api_key[-4:]}")
        
        scraper = SerpApiJobScraper(api_key=api_key)
        jobs = scraper.scrape_jobs("Full Stack Developer", "Pakistan", max_jobs=5)
        
        # Print the results
        print(f"Found {len(jobs)} jobs")
        print(json.dumps(jobs, indent=2))
        
    except Exception as e:
        print(f"Error in main: {str(e)}")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()