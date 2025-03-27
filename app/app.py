import streamlit as st
import requests
import pandas as pd
import json
import os
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Job Finder",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .job-card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        border-left: 5px solid #4CAF50;
    }
    .job-title {
        color: #1E88E5;
        font-size: 22px;
    }
    .company-name {
        color: #333;
        font-size: 18px;
        font-weight: bold;
    }
    .job-meta {
        color: #666;
        font-size: 14px;
        margin-top: 10px;
    }
    .relevance-high {
        background-color: #D5F5E3;
        border-left: 5px solid #2ECC71;
    }
    .relevance-medium {
        background-color: #FCF3CF;
        border-left: 5px solid #F1C40F;
    }
    .relevance-low {
        background-color: #FADBD8;
        border-left: 5px solid #E74C3C;
    }
    .apply-button {
        background-color: white;
        color: white;
        padding: 10px 18px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        font-weight: bold;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 4px;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# API endpoint
API_URL = "https://job-search-api-3ofh.onrender.com/search-jobs"

# App title
st.title("🔎 Job Finder")
st.markdown("Find your perfect job matching your skills and preferences")

# Create sidebar for search form
with st.sidebar:
    st.header("Search Criteria")
    
    with st.form("search_form"):
        position = st.text_input("Job Position", "Full Stack Engineer")
        location = st.text_input("Location", "Pakistan")
        experience = st.text_input("Experience", "2 years")
        
        # Job Nature with radio buttons
        job_nature = st.radio(
            "Job Nature",
            ["remote", "onsite", "hybrid"],
            index=1  # Default to onsite
        )
        
        salary = st.text_input("Salary Range", "70,000 PKR to 120,000 PKR")
        
        skills = st.text_area(
            "Skills (comma separated)",
            "full stack, MERN, Node.js, Express.js, React.js, Next.js, Firebase, TailwindCSS"
        )
        
        submitted = st.form_submit_button("Search Jobs")

# Main content area for displaying results
if submitted:
    # Show loading spinner
    with st.spinner("Searching for jobs..."):
        # Prepare search criteria
        search_criteria = {
            "position": position,
            "experience": experience,
            "salary": salary,
            "jobNature": job_nature,
            "location": location,
            "skills": skills
        }
        
        try:
            # Make API request
            response = requests.post(API_URL, json=search_criteria)
            
            # Check if request was successful
            if response.status_code == 200:
                # Parse response
                result = response.json()
                jobs = result.get("relevant_jobs", [])
                
                # Display results
                st.success(f"Found {len(jobs)} relevant jobs!")
                
                # Create tabs for different views
                tab1, tab2 = st.tabs(["Card View", "Table View"])
                
                with tab1:
                    # Card view
                    for job in jobs:
                        # Determine relevance class based on score
                        relevance_class = "relevance-high"
                        if "relevance_score" in job:
                            score = job["relevance_score"]
                            if score < 0.5:  # Changed from 0.6 to 0.5
                                relevance_class = "relevance-low"
                            elif score < 0.7:  # Changed from 0.8 to 0.7
                                relevance_class = "relevance-medium"
                        
                        # Create job card
                        st.markdown(f"""
                        <div class="job-card {relevance_class}">
                            <div class="job-title">{job.get('job_title', 'Unknown Title')}</div>
                            <div class="company-name">{job.get('company', 'Unknown Company')}</div>
                            <div class="job-meta">
                                📍 {job.get('location', 'Location not specified')} | 
                                💼 {job.get('jobNature', 'Job nature not specified')} | 
                                🕒 Experience: {job.get('experience', 'Not specified')} | 
                                💰 Salary: {job.get('salary', 'Not specified')}
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Add relevance score if available
                        if "relevance_score" in job:
                            score = job["relevance_score"]
                            st.markdown(f"""
                            <div style="margin-top:10px;">
                                <b>Relevance Score:</b> {score:.2f}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if "relevance_reasoning" in job:
                                with st.expander("View Matching Details"):
                                    st.write(job["relevance_reasoning"])
                        
                        # Job Description
                        with st.expander("View Job Description"):
                            st.write(job.get('description', 'No description available'))
                        
                        # Apply button with improved visibility
                        apply_link = job.get('apply_link', '#')
                        st.markdown(f"""
                        <div style="margin-top:10px;">
                            <a href="{apply_link}" target="_blank" class="apply-button">Apply Now</a>
                        </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with tab2:
                    # Table view
                    table_data = []
                    for job in jobs:
                        table_data.append({
                            "Title": job.get('job_title', 'Unknown'),
                            "Company": job.get('company', 'Unknown'),
                            "Location": job.get('location', 'Not specified'),
                            "Nature": job.get('jobNature', 'Not specified'),
                            "Experience": job.get('experience', 'Not specified'),
                            "Salary": job.get('salary', 'Not specified'),
                            "Relevance": job.get('relevance_score', 'N/A'),
                            "Apply": job.get('apply_link', '#')
                        })
                    
                    # Create DataFrame and display
                    if table_data:
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, 
                                    column_config={
                                        "Apply": st.column_config.LinkColumn("Apply"),
                                        "Relevance": st.column_config.ProgressColumn(
                                            "Relevance Score",
                                            help="How relevant this job is to your search criteria",
                                            min_value=0,
                                            max_value=1,
                                            format="%.2f",
                                        )
                                    })
                    else:
                        st.info("No data available for table view")
                
                # Option to save results
                if jobs:
                    st.download_button(
                        label="Download Results",
                        data=json.dumps({"relevant_jobs": jobs}, indent=2),
                        file_name=f"job_search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
            else:
                st.error(f"Error: API request failed with status code {response.status_code}")
                st.write(response.text)
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Show instructions when no search has been performed
else:
    st.info("👈 Fill out the search form in the sidebar and click 'Search Jobs' to find relevant job listings.")
    
    # Example placeholder
    st.markdown("""
    ### How it works
    
    1. Enter your job search criteria in the sidebar
    2. Click "Search Jobs" to find matches
    3. View results in either card or table format
    4. Click "Apply Now" to go to the job application page
    
    This tool searches through LinkedIn and other job platforms to find the most relevant positions matching your skills and preferences.
    """)

# Footer
st.markdown("---")
st.markdown("Job Finder API © 2025")