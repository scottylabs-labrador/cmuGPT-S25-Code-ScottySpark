# canvas_tools.py

import os
import requests
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
# How many courses to request per API call. 50 is a reasonable balance.
# Note: This initial version doesn't handle pagination across multiple calls.
# It assumes the user's active courses fit within this limit.
PER_PAGE = 50

# --- Helper Function for Term Filtering ---

def _find_most_recent_term_id(courses: List[Dict[str, Any]]) -> Optional[int]:
    """
    Identifies the ID of the most recent term based on term end dates,
    falling back to start dates if necessary.
    """
    terms: Dict[int, Dict[str, Any]] = {}
    for course in courses:
        term_data = course.get('term')
        if term_data and isinstance(term_data, dict) and 'id' in term_data:
            term_id = term_data['id']
            if term_id not in terms:
                end_at_str = term_data.get('end_at')
                start_at_str = term_data.get('start_at')
                end_at = None
                start_at = None
                try:
                    if end_at_str: end_at = datetime.fromisoformat(end_at_str.replace('Z', '+00:00'))
                    if start_at_str: start_at = datetime.fromisoformat(start_at_str.replace('Z', '+00:00'))
                except (ValueError, TypeError) as dt_error:
                     logger.warning(f"Could not parse term dates for term {term_id}: {dt_error}")

                terms[term_id] = {
                    'id': term_id,
                    'name': term_data.get('name', 'Unknown Term'),
                    'start_at': start_at,
                    'end_at': end_at
                }

    if not terms:
        logger.warning("No valid terms found associated with the courses.")
        return None # Cannot determine the most recent term

    most_recent_term_id: Optional[int] = None
    latest_end_date: Optional[datetime] = None
    latest_start_date_for_latest_end: Optional[datetime] = None
    utc_min_date = datetime.min.replace(tzinfo=timezone.utc) # For comparison if dates are None

    for term_id, term_info in terms.items():
        current_end = term_info.get('end_at') or utc_min_date
        current_start = term_info.get('start_at') or utc_min_date

        if latest_end_date is None or current_end > latest_end_date:
            latest_end_date = current_end
            latest_start_date_for_latest_end = current_start
            most_recent_term_id = term_id
        elif current_end == latest_end_date:
             if latest_start_date_for_latest_end is None or current_start > latest_start_date_for_latest_end:
                  latest_start_date_for_latest_end = current_start
                  most_recent_term_id = term_id

    if most_recent_term_id is not None:
        logger.info(f"Identified most recent term: ID={most_recent_term_id}, Name='{terms[most_recent_term_id]['name']}'")
    else:
        logger.error("Failed to determine the most recent term ID from available terms.")

    return most_recent_term_id


# --- Main Function to Fetch Courses ---

def fetch_current_courses() -> Dict[str, Any]:
    """
    Fetches active courses for the user associated with the API token,
    filters them for the most recent term, and formats the result.

    Returns:
        A dictionary containing either a 'courses_list' string or an 'error' string.
    """
    logger.info("Attempting to fetch current Canvas courses...")

    # 1. Get Credentials from Environment
    token = os.getenv("CANVAS_API_TOKEN")
    base_url = os.getenv("CANVAS_BASE_URL")

    if not token or not base_url:
        logger.error("Canvas API token or base URL not found in environment variables.")
        return {"error": "Canvas API connection is not configured."}

    # 2. Construct API Request Details
    api_url = f"{base_url.rstrip('/')}/api/v1/courses"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "include[]": "term",
        "enrollment_state": "active",
        "per_page": PER_PAGE
    }

    # 3. Make API Call
    try:
        logger.debug(f"Making GET request to {api_url} with params: {params}")
        response = requests.get(api_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()

        all_courses = response.json()
        logger.info(f"Successfully fetched {len(all_courses)} active course enrollment(s) from Canvas.")

        if not isinstance(all_courses, list):
             logger.error(f"Unexpected API response format. Expected list, got {type(all_courses)}")
             return {"error": "Received unexpected data format from Canvas."}

        if not all_courses:
            return {"courses_list": "You do not seem to be enrolled in any active courses."}

    except requests.exceptions.Timeout:
        logger.error("Request to Canvas API timed out.")
        return {"error": "The request to Canvas timed out. Please try again later."}
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err} - Status Code: {http_err.response.status_code}")
        if http_err.response.status_code == 401:
            return {"error": "Authentication failed. Please check the Canvas API token."}
        else:
            return {"error": f"Failed to fetch courses from Canvas (HTTP {http_err.response.status_code})."}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Error during Canvas API request: {req_err}")
        return {"error": "Could not connect to Canvas to fetch courses."}
    except ValueError as json_err:
        logger.error(f"Error parsing JSON response from Canvas: {json_err}")
        return {"error": "Received invalid data format from Canvas."}
    except Exception as e:
        logger.exception("An unexpected error occurred during course fetching.")
        return {"error": "An unexpected error occurred while fetching courses."}

    # 4. Filter by Term
    most_recent_term_id = _find_most_recent_term_id(all_courses)

    if most_recent_term_id is None:
        logger.warning("Could not determine the most recent term. Cannot filter courses.")
        return {"error": "Could not determine the most recent academic term to filter courses."}

    # Calculate the term name before checking if courses exist for it
    most_recent_term_name = f"Term ID {most_recent_term_id}"  # Default value
    for course in all_courses:  # Iterate through ALL fetched courses to find the name
        if course.get('enrollment_term_id') == most_recent_term_id:
             term_info = course.get('term')
             if term_info and term_info.get('name'):
                  most_recent_term_name = term_info['name']
                  break  # Found the name, no need to check further
    logger.info(f"Using term name: '{most_recent_term_name}' for ID {most_recent_term_id}")

    current_term_courses = [
        course for course in all_courses
        if course.get('enrollment_term_id') == most_recent_term_id
    ]

    if not current_term_courses:
        return {"courses_list": f"No active courses found for the most recent term ('{most_recent_term_name}')."}

    # 5. Format Output
    output_lines = [f"Here are your current courses for {most_recent_term_name}:"]
    for course in current_term_courses:
        name = course.get('name', 'Unnamed Course')
        code = course.get('course_code', 'No Code')
        output_lines.append(f"- {name} ({code})")

    logger.info(f"Formatted {len(current_term_courses)} courses for the current term.")
    return {"courses_list": "\n".join(output_lines)}