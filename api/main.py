from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import sys
import os
import logging
import random
from dotenv import load_dotenv
from api.indeed_scraper import ApifyIndeedScraper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add parent directory to path so we can import from api package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.linkedin_scraper import LinkedInJobScraper
from api.googlejob_search import SerpApiJobScraper
from api.LLM_filtering import GeminiJobFilter

app = FastAPI(
    title="Job Finder API",
    description="API that fetches relevant job listings from LinkedIn, Google Jobs, and other sources",
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
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY environment variable not set. LLM filtering will not work properly.")
    return GeminiJobFilter(api_key=api_key)

def get_serpapi_scraper():
    """Dependency to create and return a SerpApiJobScraper instance"""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        logger.warning("SERPAPI_API_KEY environment variable not set. Google Jobs search will be skipped.")
        return None
    return SerpApiJobScraper(api_key=api_key)

def get_indeed_scraper():
    """Dependency to create and return an ApifyIndeedScraper instance"""
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key:
        logger.warning("APIFY_API_KEY environment variable not set. Indeed search will be skipped.")
        return None
    return ApifyIndeedScraper(api_key=api_key)

def keyword_score_jobs(jobs: List[Dict[str, Any]], search_criteria: Dict[str, str], max_jobs: int = 20) -> List[Dict[str, Any]]:
    """
    Score jobs based on keyword matching (fallback when LLM is unavailable)
    
    Args:
        jobs: List of job dictionaries
        search_criteria: Dictionary of search criteria
        max_jobs: Maximum number of jobs to return
        
    Returns:
        List of scored jobs
    """
    filtered_jobs = []
    
    # Extract keywords from search criteria
    keywords = []
    if search_criteria.get("skills"):
        keywords.extend([k.lower().strip() for k in search_criteria["skills"].split(",") if k.strip()])
    if search_criteria.get("position"):
        keywords.extend([t.lower().strip() for t in search_criteria["position"].split() if t.strip()])
    
    # Add job nature as a keyword if specified
    if search_criteria.get("jobNature") and search_criteria["jobNature"] != "Not specified":
        keywords.append(search_criteria["jobNature"].lower())
    
    # Add location as a keyword if specified
    if search_criteria.get("location") and search_criteria["location"] != "Not specified":
        keywords.append(search_criteria["location"].lower())
    
    logger.info(f"Using keywords for fallback scoring: {keywords}")
    
    for job in jobs:
        # Simple scoring based on keyword presence
        job_text = (
            (job.get("job_title", "") + " " +
            job.get("company", "") + " " +
            job.get("location", "") + " " +
            job.get("jobNature", "") + " " +
            job.get("description", "")).lower()
        )
        
        matching_keywords = sum(1 for k in keywords if k in job_text)
        if keywords:
            score = min(1.0, matching_keywords / len(keywords))
        else:
            score = 0.5  # Default score if no keywords
        
        # Add a small random factor to avoid ties
        score = min(1.0, score + random.uniform(0, 0.05))
        
        job_copy = job.copy()
        job_copy["relevance_score"] = score
        job_copy["relevance_reasoning"] = f"Keyword matching found {matching_keywords} out of {len(keywords)} keywords"
        filtered_jobs.append(job_copy)
    
    # Sort by score
    filtered_jobs = sorted(filtered_jobs, key=lambda x: x.get("relevance_score", 0), reverse=True)
    # Limit results
    return filtered_jobs[:max_jobs]

@app.post("/search-jobs", response_model=JobSearchResponse)
async def search_jobs(
    request: JobSearchRequest, 
    job_filter: GeminiJobFilter = Depends(get_job_filter),
    serpapi_scraper: Optional[SerpApiJobScraper] = Depends(get_serpapi_scraper),
    indeed_scraper: Optional[ApifyIndeedScraper] = Depends(get_indeed_scraper)
):
    try:
        all_jobs = []
        sources_used = []
        
        # 1. Try LinkedIn scraper
        try:
            linkedin_scraper = LinkedInJobScraper(
                title=request.position, 
                location=request.location
            )
            linkedin_jobs = linkedin_scraper.scrape_jobs(max_jobs=10)
            
            if linkedin_jobs:
                all_jobs.extend(linkedin_jobs)
                sources_used.append("LinkedIn")
                logger.info(f"Found {len(linkedin_jobs)} jobs from LinkedIn")
        except Exception as e:
            logger.error(f"LinkedIn scraper error: {str(e)}")
        
        # 2. Try Google Jobs via SERPAPI
        if serpapi_scraper:
            try:
                serpapi_jobs = serpapi_scraper.scrape_jobs(
                    title=request.position,
                    location=request.location,
                    max_jobs=10
                )
                
                if serpapi_jobs:
                    all_jobs.extend(serpapi_jobs)
                    sources_used.append("Google Jobs")
                    logger.info(f"Found {len(serpapi_jobs)} jobs from Google Jobs")
            except Exception as e:
                logger.error(f"SERPAPI scraper error: {str(e)}")
        
        # 3. Use Indeed as a supplementary source if we need more jobs
        if indeed_scraper and len(all_jobs) < 8:  # Only if we have fewer than 8 jobs
            try:
                # Determine country code based on location
                country = "PK"  # Default to Pakistan
                if "united states" in request.location.lower() or "usa" in request.location.lower():
                    country = "US"
                elif "united kingdom" in request.location.lower() or "uk" in request.location.lower():
                    country = "GB"
                
                indeed_jobs = indeed_scraper.scrape_jobs(
                    title=request.position,
                    location=request.location,
                    country=country,
                    max_jobs=3  # Keep low to save API credits
                )
                
                if indeed_jobs:
                    all_jobs.extend(indeed_jobs)
                    sources_used.append("Indeed")
                    logger.info(f"Found {len(indeed_jobs)} jobs from Indeed")
            except Exception as e:
                logger.error(f"Indeed scraper error: {str(e)}")
        else:
            if indeed_scraper and len(all_jobs) >= 8:
                logger.info("Skipping Indeed since we already have enough jobs")
            
        # If no jobs found from any source
        if not all_jobs:
            logger.warning("No jobs found from any source")
            return JobSearchResponse(relevant_jobs=[])
        
        logger.info(f"Total jobs collected: {len(all_jobs)} from sources: {', '.join(sources_used)}")
        
        # Filter jobs using LLM
        search_criteria = {
            "position": request.position,
            "experience": request.experience,
            "salary": request.salary,
            "jobNature": request.jobNature,
            "location": request.location,
            "skills": request.skills
        }
        
        try:
            # If we have many jobs, limit before sending to the LLM to avoid rate limits
            jobs_for_filtering = all_jobs
            if len(all_jobs) > 15:
                logger.info(f"Limiting jobs for LLM filtering from {len(all_jobs)} to 15 to avoid rate limits")
                # Just take the first 15 jobs to avoid rate limits
                jobs_for_filtering = all_jobs[:15]
            
            # Apply LLM filtering
            filtered_jobs = job_filter.filter_relevant_jobs(
                jobs=jobs_for_filtering,
                search_criteria=search_criteria,
                min_score=0.3,
                max_jobs=20
            )
            logger.info(f"Jobs after LLM filtering: {len(filtered_jobs)}")
            
        except Exception as e:
            logger.error(f"LLM filtering error: {str(e)}")
            logger.info("Using keyword-based fallback scoring method")
            
            # Use our keyword matching fallback
            filtered_jobs = keyword_score_jobs(
                jobs=all_jobs,
                search_criteria=search_criteria,
                max_jobs=20
            )
            logger.info(f"Jobs after keyword filtering: {len(filtered_jobs)}")
        
        # Convert to response model
        job_details = [JobDetail(**job) for job in filtered_jobs]
        return JobSearchResponse(relevant_jobs=job_details)
    
    except Exception as e:
        logger.error(f"Error in search_jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching jobs: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Job Finder API", 
        "endpoints": {
            "search_jobs": "/search-jobs (POST)",
        },
        "sources": ["LinkedIn", "Google Jobs (SERPAPI)", "Indeed (Apify)"],
        "version": "1.0.0"
    }

if __name__ == "__main__":
    # Modified to correctly reference this file
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)