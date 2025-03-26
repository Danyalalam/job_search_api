from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path so we can import from api package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.linkedin_scraper import LinkedInJobScraper
from api.LLM_filtering import GeminiJobFilter

app = FastAPI(
    title="Job Finder API",
    description="API that fetches relevant job listings from LinkedIn, Indeed, and other sources",
    version="1.0.0",
)

class JobSearchRequest(BaseModel):
    position: str
    experience: str
    salary: str
    jobNature: str
    location: str
    skills: str

class JobDetail(BaseModel):
    job_title: str
    company: Optional[str] = None
    experience: Optional[str] = None
    jobNature: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    apply_link: str
    description: Optional[str] = None
    relevance_score: Optional[float] = None
    relevance_reasoning: Optional[str] = None

class JobSearchResponse(BaseModel):
    relevant_jobs: List[JobDetail]

def get_job_filter():
    """Dependency to create and return a GeminiJobFilter instance"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY environment variable not set. LLM filtering will not work properly.")
    return GeminiJobFilter(api_key=api_key)

@app.post("/search-jobs", response_model=JobSearchResponse)
async def search_jobs(request: JobSearchRequest, job_filter: GeminiJobFilter = Depends(get_job_filter)):
    try:
        # Initialize LinkedIn scraper with the job title and location from request
        linkedin_scraper = LinkedInJobScraper(
            title=request.position, 
            location=request.location
        )
        
        # Get job listings from LinkedIn (adjust max_jobs as needed)
        linkedin_jobs = linkedin_scraper.scrape_jobs(max_jobs=20)
        
        # Apply LLM filtering to get relevant jobs
        search_criteria = {
            "position": request.position,
            "experience": request.experience,
            "salary": request.salary,
            "jobNature": request.jobNature,
            "location": request.location,
            "skills": request.skills
        }
        
        try:
            # Lower the threshold to 0.3 and increase max_jobs to get more results
            filtered_jobs = job_filter.filter_relevant_jobs(
                jobs=linkedin_jobs,
                search_criteria=search_criteria,
                min_score=0.3,  # Changed from 0.6 to 0.3
                max_jobs=20     # Increased from 10 to 20
            )
        except Exception as e:
            logger.error(f"LLM filtering error: {str(e)}")
            # Fall back to unfiltered jobs if filtering fails
            filtered_jobs = linkedin_jobs
            
        # Convert to Pydantic models for validation
        job_details = []
        for job in filtered_jobs:
            job_details.append(JobDetail(**job))
        
        return JobSearchResponse(relevant_jobs=job_details)
    
    except Exception as e:
        logger.error(f"Error in search_jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching jobs: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to the Job Finder API. Use /search-jobs endpoint to search for jobs."}

if __name__ == "__main__":
    # Modified to correctly reference this file
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)