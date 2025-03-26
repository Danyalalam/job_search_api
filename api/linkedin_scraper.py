import requests
from bs4 import BeautifulSoup
import json
import re

class LinkedInJobScraper:
    def __init__(self, title, location, headers=None):
        """
        Initialize the LinkedIn Job Scraper
        
        :param title: Job title to search
        :param location: Job location to search
        :param headers: Custom headers for requests (optional)
        """
        self.title = title
        self.location = location
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
    def get_job_ids(self, start=0, max_jobs=50):
        """
        Retrieve job IDs from LinkedIn job search
        
        :param start: Starting point for pagination
        :param max_jobs: Maximum number of jobs to retrieve
        :return: List of job IDs
        """
        list_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={self.title}&location={self.location}&start={start}"
        
        try:
            response = requests.get(list_url, headers=self.headers)
            response.raise_for_status()
            
            list_soup = BeautifulSoup(response.text, "html.parser")
            page_jobs = list_soup.find_all("li")
            
            id_list = []
            for job in page_jobs[:max_jobs]:
                base_card_div = job.find("div", {"class": "base-card"})
                if base_card_div:
                    job_id = base_card_div.get("data-entity-urn", "").split(":")[-1]
                    if job_id:
                        id_list.append(job_id)
            
            return id_list
        
        except requests.RequestException as e:
            print(f"Error retrieving job IDs: {e}")
            return []
    
    def extract_job_details(self, job_id):
        """
        Extract detailed information for a specific job
        
        :param job_id: Job ID to retrieve details for
        :return: Dictionary of job details
        """
        job_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        
        try:
            job_response = requests.get(job_url, headers=self.headers)
            job_response.raise_for_status()
            
            job_soup = BeautifulSoup(job_response.text, "html.parser")
            job_post = {
                "job_title": self._safe_extract(job_soup, "h2", {"class": "top-card-layout__title"}),
                "company": self._safe_extract(job_soup, "a", {"class": "topcard__org-name-link"}),
                "location": self._safe_extract(job_soup, "span", {"class": "topcard__flavor--bullet"}),
                "experience": self._extract_experience(job_soup),
                "salary": self._extract_salary(job_soup),
                "jobNature": self._extract_job_nature(job_soup),
                "apply_link": job_url,
                "description": self._extract_description(job_soup)
            }
            
            return job_post
        
        except requests.RequestException as e:
            print(f"Error retrieving job details for job ID {job_id}: {e}")
            return None
    
    def _safe_extract(self, soup, tag, attrs):
        """
        Safely extract text from a BeautifulSoup element
        
        :param soup: BeautifulSoup object
        :param tag: HTML tag to find
        :param attrs: Attributes to match
        :return: Extracted text or None
        """
        try:
            element = soup.find(tag, attrs)
            return element.text.strip() if element else None
        except Exception:
            return None
    
    def _extract_experience(self, soup):
        """
        Extract job experience requirements
        
        :param soup: BeautifulSoup object
        :return: Experience requirement string
        """
        try:
            # Look for experience-related text in job details
            experience_text = soup.find(string=re.compile(r'\d+\s*(\+)?\s*years?'))
            return experience_text.strip() if experience_text else "Not specified"
        except Exception:
            return "Not specified"
    
    def _extract_salary(self, soup):
        """
        Extract salary information
        
        :param soup: BeautifulSoup object
        :return: Salary string
        """
        try:
            # First try to find salary in the job criteria section
            criteria_elements = soup.find_all("span", {"class": "description__job-criteria-text"})
            for element in criteria_elements:
                parent = element.find_parent("div")
                if parent and "Salary" in parent.get_text():
                    return element.get_text(strip=True)
            
            # If not found in criteria, try to extract from description
            description = soup.get_text().lower()
            
            # Common salary patterns
            import re
            salary_patterns = [
                r'salary[:\s]*[\$£₹₨]?[\d,.]+ ?[kK]?[-to]*[\$£₹₨]?[\d,.]+ ?[kK]?',
                r'[\$£₹₨][\d,.]+ ?[kK]?[-to]*[\$£₹₨]?[\d,.]+ ?[kK]? per (year|month|annum)',
                r'[\d,.]+ ?[kK]?[-to]*[\d,.]+ ?[kK]? (pkr|inr|usd|gbp)',
                r'([\d,.]+ ?[kK]?[-to]*[\d,.]+ ?[kK]?) (pkr|inr|usd|gbp)',
                r'(pkr|inr|usd|gbp) ([\d,.]+ ?[kK]?[-to]*[\d,.]+ ?[kK]?)',
            ]
            
            for pattern in salary_patterns:
                matches = re.findall(pattern, description)
                if matches:
                    return matches[0] if isinstance(matches[0], str) else ' '.join(matches[0])
            
            return "Not specified"
                
        except Exception as e:
            return "Not specified"
    
    def _extract_job_nature(self, soup):
        """
        Determine job nature (remote/onsite/hybrid)
        
        :param soup: BeautifulSoup object
        :return: Job nature string
        """
        try:
            description = soup.get_text().lower()
            if "remote" in description:
                return "remote"
            elif "onsite" in description or "on-site" in description:
                return "onsite"
            else:
                return "hybrid"
        except Exception:
            return "Not specified"
    
    def _extract_description(self, soup):
        """
        Extract job description
        
        :param soup: BeautifulSoup object
        :return: Job description text
        """
        try:
            description_div = soup.find("div", {"class": "show-more-less-html__markup"})
            return description_div.get_text(strip=True) if description_div else "No description available"
        except Exception:
            return "No description available"
    
    def scrape_jobs(self, max_jobs=10):
        """
        Scrape multiple job details
        
        :param max_jobs: Maximum number of jobs to scrape
        :return: List of job details
        """
        job_ids = self.get_job_ids(max_jobs=max_jobs)
        jobs = []
        
        for job_id in job_ids:
            job_details = self.extract_job_details(job_id)
            if job_details:
                jobs.append(job_details)
        
        return jobs

def main():
    # Example usage
    scraper = LinkedInJobScraper(title="Mern stack developer", location="pakistan")
    jobs = scraper.scrape_jobs(max_jobs=5)
    
    # Print jobs in a formatted way
    print(json.dumps({"relevant_jobs": jobs}, indent=2))

if __name__ == "__main__":
    main()