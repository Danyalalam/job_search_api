import os
import json
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from apify_client import ApifyClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ApifyIndeedScraper:
    def __init__(self, api_key=None):
        """
        Initialize the Apify Indeed Scraper
        
        Args:
            api_key: Apify API key (defaults to environment variable)
        """
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("APIFY_API_KEY")
        
        if not self.api_key:
            logger.error("No Apify API key found. Make sure to set APIFY_API_KEY in your .env file or pass it directly.")
            raise ValueError("Apify API key is required. Set APIFY_API_KEY in .env file or pass it to the constructor.")
        
        # Initialize Apify client
        self.client = ApifyClient(self.api_key)
        logger.info("Successfully initialized Apify Indeed Scraper")
    
    def scrape_jobs(self, title: str, location: str, max_jobs: int = 5, country: str = "PK") -> List[Dict[str, Any]]:
        """
        Scrape job listings from Indeed using Apify
        
        Args:
            title: Job title to search for
            location: Location to search in
            max_jobs: Maximum number of jobs to return (keep low to save credits)
            country: Country code (default: PK for Pakistan)
            
        Returns:
            List of job details dictionaries
        """
        try:
            logger.info(f"Searching Indeed for: {title} in {location} (max: {max_jobs} jobs)")
            
            # Prepare the Actor input - keep max_items low to minimize API usage
            run_input = {
                "position": title,
                "location": location,
                "country": country,
                "maxItems": max_jobs,  # Limit to save credits
            }
            
            # Run the Actor and wait for it to finish
            logger.info("Sending request to Apify")
            run = self.client.actor("misceres/indeed-scraper").call(run_input=run_input)
            
            # Get the dataset ID
            dataset_id = run["defaultDatasetId"]
            logger.info(f"Job completed. Dataset ID: {dataset_id}")
            
            # Fetch the results
            raw_results = list(self.client.dataset(dataset_id).iterate_items())
            logger.info(f"Retrieved {len(raw_results)} jobs from Apify")
            
            # Format the results to match our standard structure
            formatted_jobs = []
            for job in raw_results:
                # Extract job nature from job type or description
                job_nature = "Not specified"
                if job.get("jobType"):
                    job_type_text = " ".join(job.get("jobType", [])).lower()
                    if "remote" in job_type_text:
                        job_nature = "remote"
                    elif "hybrid" in job_type_text:
                        job_nature = "hybrid"
                    else:
                        job_nature = "onsite"  # Default for most Indeed jobs
                
                # Format to match our standard structure
                formatted_job = {
                    "job_title": job.get("positionName", "Not specified"),
                    "company": job.get("company", "Not specified"),
                    "location": job.get("location", "Not specified"),
                    "description": job.get("description", "No description available"),
                    "apply_link": job.get("externalApplyLink", job.get("url", "#")),
                    "jobNature": job_nature,
                    "experience": self._extract_experience(job.get("description", "")),
                    "salary": job.get("salary", "Not specified")
                }
                
                formatted_jobs.append(formatted_job)
            
            logger.info(f"Successfully formatted {len(formatted_jobs)} jobs")
            return formatted_jobs
            
        except Exception as e:
            logger.error(f"Error in scrape_jobs: {str(e)}")
            return []
    
    def _extract_experience(self, description: str) -> str:
        """Extract experience requirements from job description"""
        import re
        try:
            # Common experience patterns
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


def main():
    """Test the ApifyIndeedScraper (careful with API credits)"""
    try:
        # Make sure you have APIFY_API_KEY in your .env file
        load_dotenv()
        api_key = os.getenv("APIFY_API_KEY")
        
        if not api_key:
            print("APIFY_API_KEY not found in .env file")
            return
            
        print(f"Using Apify key: {api_key[:5]}...{api_key[-4:] if len(api_key) > 8 else ''}")
        
        # Create the scraper
        scraper = ApifyIndeedScraper(api_key=api_key)
        
        # Ask for confirmation before using credits
        confirm = input("This will use Apify credits. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled. No credits used.")
            return
            
        # Run the job search with limited max_jobs to save credits
        print("Fetching jobs from Indeed...")
        jobs = scraper.scrape_jobs("Full Stack Developer", "Islamabad", max_jobs=3)
        
        # Print the results in a readable format
        print(f"\n============= Found {len(jobs)} jobs =============\n")
        
        for i, job in enumerate(jobs, 1):
            print(f"--- Job {i} ---")
            print(f"Title: {job['job_title']}")
            print(f"Company: {job['company']}")
            print(f"Location: {job['location']}")
            print(f"Job Nature: {job['jobNature']}")
            print(f"Experience: {job['experience']}")
            print(f"Salary: {job['salary']}")
            print(f"Apply Link: {job['apply_link']}")
            
            # Print a shortened description
            description = job['description']
            if len(description) > 200:
                description = description[:200] + "..."
            print(f"Description: {description}")
            print("\n")
        
        # Also save to a JSON file for reference
        with open('indeed_jobs.json', 'w') as f:
            json.dump(jobs, f, indent=2)
        print("Jobs also saved to indeed_jobs.json")
        
        print("\nREMINDER: Be careful with API usage - you have limited credits")
        
    except Exception as e:
        print(f"Error in main: {str(e)}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    main()