from openai import OpenAI, APITimeoutError, APIError
import json
from dotenv import load_dotenv
import os
import time
from perplexity_integration import CMUPerplexitySearch  # Changed from relative import
import requests
from datetime import datetime

from openai import OpenAI, APITimeoutError, APIError
import json
from dotenv import load_dotenv
import os
import time
from perplexity_integration import CMUPerplexitySearch  # Changed from relative import
import requests
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import os.path
from datetime import datetime, timedelta
from tzlocal import get_localzone  # Auto-detect user's timezone
from zoneinfo import ZoneInfo
import difflib
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import canvas_tools


#from courses import get_courses, get_course_by_id, get_fces, get_fces_by_id, get_schedules

# This scope allows for some modification to the calendar, as opposed to /calendar/readonly
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def authenticate_google_calendar():
    """Authenticate and return the Google Calendar API service."""
    credentials_location = "credentials.json"
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_location, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service



load_dotenv()

class CMUGPTAssistant:
    def __init__(self):
        # Set up OpenAI client with timeout configuration
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            timeout=60.0,  # 60 second timeout
            max_retries=3  # Allow 3 retries
        )
        self.show_eats = False
        self.show_courses = False

        self.service = authenticate_google_calendar()
        
        # Define the function definitions (tools) for the model
        self.tools = self.get_tools()
        
        # Initialize conversation messages
        self.messages = [
            {
                "role": "system",
                "content": "You are CMUGPT, an assistant knowledgeable about Carnegie Mellon University in Pittsburgh, Pennsylvania. Use the supplied tools to assist the user."
            },
            {
                "role": "system",
                "content": "If someone inquires about dining direct them to visit https://cmueats.com and always call the function to display it to the UI, while if someone asks about courses at CMU direct them to visit https://cmucourses.com and always call the function to display it to the UI, while if someone asks about directions direct them to visit https://cmumaps.com, while if someone asks about ScottyLabs direct them to visit https://ScottyLabs.org"
            },
            #{
            #    "role": "system",
            #    "content": "Write concise, relevant responses, with the skilled style of a Pultizer Prize-winning author.  Do not use course search function, all others allowed."
            #}
        ]
        
        # Keep track of functions called
        self.functions_called = []

        
        
        self.perplexity_search = CMUPerplexitySearch()
    
    def get_tools(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "general_purpose_knowledge_search",
                    "description": "Search for general knowledge about Carnegie Mellon University. Today's date is "  + datetime.now().strftime("%B %d, %Y"),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_query": {
                                "type": "string",
                                "description": "The query to search for general knowledge."
                            }
                        },
                        "required": ["search_query"],
                        "additionalProperties": False
                    },
                    "strict": True  # Enabling Structured Outputs
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "show_cmueats_website",
                    "description": "Display cmueats website to the UI frontend",
                        "required": [""],
                        "additionalProperties": False
                    },
                    "strict": True  # Enabling Structured Outputs
            },
            {
                "type": "function",
                "function": {
                    "name": "show_cmucourses_website",
                    "description": "Display cmucourses website to the UI frontend",
                        "required": [""],
                        "additionalProperties": False
                    },
                    "strict": True  # Enabling Structured Outputs
            },
            {
                "type": "function",
                "function": {
                    "name": "create_calendar_event",
                    "description": "Create/Add an event in the user's calendar when prompted",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "The name of the event to be created with default settings"
                            }, 
                            "location": {
                                "type": "string",
                                "description": "The location of the event to be created with default settings"
                            },
                            "description": {
                                "type": "string",
                                "description": "A detailed description of the event to be created with default settings"
                            },
                            "start_date": {
                                "type": "string",
                                "description": f"Start date of the event to be created, in the form of 'MM/DD/YYYY' with DEFAULT DATE AS {datetime.now()} if not specified by the user. When the user specifies a day of the week, use {datetime.now()} as reference for today's date. ALWAYS think twice and count to check that the date and the user's specified day match up"
                            },
                            "end_date": {
                                "type": "string",
                                "description": f"End date of the event to be created, in the form of 'MM/DD/YYYY' with DEFAULT DATE AS {datetime.now()} if not specified by the user. When the user specifies a day of the week, use {datetime.now()} as reference for today's date. ALWAYS think twice and count to check that the date and the user's specified day match up"
                            },
                            "start_time": {
                                "type": "string",
                                "description": f"Start time during the day of the event to be created, in the form of 'HH:MM' with default set to the time 09:00"
                            },
                            "end_time": {
                                "type": "string",
                                "description": f"End time of the event to be created, in the form of 'HH:MM' with default set to one hour after start_time"
                            }
                        },
                        "required": ["name", "start_time", "end_time"],
                        "additionalProperties": False
                    },
                    "strict": False  # Enabling Structured Outputs
                }
            }, {
                "type": "function",
                "function": {
                    "name": "delete_calendar_event",
                    "description": "Delete a calendar event that matches the given summary. First fetch events and then delete the one that matches.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "The name of the event to be deleted with default settings"
                            }
                        },
                        "required": ["name"],
                        "additionalProperties": False
                    },
                    "strict": False  # Enabling Structured Outputs
                }
            }, {
                "type": "function",
                "function": {
                    "name": "delete_all_event",
                    "description": "Delete all events in the calendar",
                    "strict": False  # Enabling Structured Outputs
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_canvas_courses",
                    "description": "Fetches the user's currently active courses from Canvas for the most recent academic term.",
                    "parameters": { # This tool takes no parameters from the LLM
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
        ]
        return tools

    def process_user_input(self, user_input):
        self.messages.append({"role": "user", "content": user_input})
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    #model='gpt-4o-mini',  # Fixed model name
                    model='gpt-4o-mini-2024-07-18',
                    messages=self.messages,
                    tools=self.tools,
                )

                assistant_message = response.choices[0].message
                
                if assistant_message.tool_calls:
                    # The model wants to call functions
                    tool_calls = assistant_message.tool_calls
                    function_results = []

                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        result = self.execute_function(function_name, arguments)

                        # Keep track of functions called
                        self.functions_called.append({
                            'function_name': function_name,
                            'arguments': arguments,
                            'result': result
                        })

                        # Prepare the function result message
                        function_result_message = {
                            "role": "tool",
                            "content": json.dumps(result),
                            "tool_call_id": tool_call.id
                        }

                        # Add the assistant's message (function call) and the function result to the conversation
                        self.messages.append({
                            "role": "assistant",
                            "tool_calls": [tool_call]
                        })
                        self.messages.append(function_result_message)

                    # After providing the function results, call the model again to get the final response
                    response = self.client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=self.messages,
                        #tools=self.tools,
                    )

                    

                    assistant_message = response.choices[0].message
                    self.messages.append(assistant_message)

                    return assistant_message.content
                else:
                    self.messages.append(assistant_message)
                    return assistant_message.content

            except APITimeoutError as e:
                if attempt == max_retries - 1:
                    return f"I apologize, but I'm having trouble connecting. Please try again in a moment. (Error: Connection timeout)"
                time.sleep(retry_delay)
                retry_delay *= 2
                
            except APIError as e:
                if attempt == max_retries - 1:
                    return f"I apologize, but there was an error processing your request. Please try again. (Error: {str(e)})"
                time.sleep(retry_delay)
                retry_delay *= 2
                
            except Exception as e:
                return f"I apologize, but an unexpected error occurred. Please try again. (Error: {str(e)})"

        return "I apologize, but I was unable to process your request after multiple attempts. Please try again later."

    # Function to execute the functions
    def execute_function(self, function_name, arguments):
        if function_name == 'general_purpose_knowledge_search':
            return self.general_purpose_knowledge_search(arguments.get('search_query'))
        #Add elif statements here
        elif function_name == 'show_cmueats_website':
            return self.show_cmu_eats()
        elif function_name == 'show_cmucourses_website':
            return self.show_cmu_courses()
        elif function_name == 'create_calendar_event':
            return self.create_calendar_event(arguments.get('summary'), arguments.get('location'), arguments.get('description'), arguments.get('start_date'), arguments.get('end_date'), arguments.get('start_time'), arguments.get('end_time'))
        elif function_name == 'delete_calendar_event':
            return self.delete_calendar_event(arguments.get('summary'))
        elif function_name == 'delete_all_event':
            return self.delete_all_event()
        elif function_name == 'get_current_canvas_courses':
            # This tool takes no arguments from the LLM
            # Call the function imported from canvas_tools.py
            return canvas_tools.fetch_current_courses()
        else:
            return {"error": "Function not found."}

    # Define the functions (simulate the functionality)
    def general_purpose_knowledge_search(self, search_query):
        # Use Perplexity API for general knowledge searches
        return self.perplexity_search.search(search_query)
    def show_cmu_eats(self):
        print("show cmu eats function called")
        self.show_eats = True
        return "Displaying CMUEATS.com website on frontend."

    def show_cmu_courses(self):
        print("show cmu courses function called")
        self.show_courses = True
        return "Displaying CMUCOURSES.com website on frontend."

    # custom function for creating calendar
    def create_calendar_event(self, summary, location, description, start_date, end_date, start_time = "06:00", end_time = "07:00"):
        #location = "Tepper"
        #description = "Eating icecream"

        #start_date = "03/20/2025"
        print(start_date)
        #end_date = "03/20/2025"
        print(end_date)
        print(start_time)
        print(end_time)

        start_object = datetime.strptime(f"{start_date} {start_time}", "%m/%d/%Y %H:%M")
        end_object = datetime.strptime(f"{end_date} {end_time}", "%m/%d/%Y %H:%M")
        user_timezone = get_localzone()
        # Localize datetime to user's timezone
        start_object = start_object.replace(tzinfo=user_timezone)
        end_object = end_object.replace(tzinfo=user_timezone)

        # Convert to ISO 8601 format
        start_iso = start_object.isoformat()
        end_iso = end_object.isoformat()

        event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_iso,
        },
        'end': {
            'dateTime': end_iso,
        },
        }

        service = self.service

        try:
            # insert the event 
            event = service.events().insert(calendarId="primary", body=event).execute()
            print(f"Event added successfully!")

        except HttpError as error:
            print(f"An error occurred: {error}")
        return "Your event was added successfully! Let me know if you need anything else"

    def fetch_events(self, delta):
        service = self.service
        if type(delta) == str:
            diff = timedelta(days=int(delta))
        else: 
            diff = timedelta(days=delta)
        event_list = []
        today = datetime.utcnow()
        start_of_week = today - diff
        end_of_week = start_of_week + diff
        timeMin = start_of_week.isoformat() + 'Z'
        timeMax = end_of_week.isoformat() + 'Z'
        print("Getting all events")
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=timeMin,
                timeMax=timeMax,
                singleEvents=True,
                orderBy="startTime"
            )
            .execute()
        )
        event_list = events_result.get("items", [])
        if len(event_list) == 0:
            print("No upcoming events found.")
        return event_list

    def get_event_id(self, name, event_list):
        for event in event_list:
            if event.get('summary') == name:
                return event.get('id')
        return None

    #it only works for the event within a week to work
    # def delete_calendar_event(self, summary):
    #     service = authenticate_google_calendar()
    #     events = self.fetch_events(100, service)
    #     best_match = None
    #     for event in events:
    #         if summary.lower() in event.get('summary', '').lower():
    #             best_match = event
    #             break
        
    #     if best_match:
    #         event_id = best_match.get('id')
    #         try:
    #             service.events().delete(calendarId="primary", eventId=event_id).execute()
    #             return f"Event '{best_match.get('summary')}' was deleted successfully!"
    #         except HttpError as error:
    #             return f"An error occurred: {error}"
    #     else:
    #         return f"No event matching '{summary}' was found in your calendar."
    def delete_calendar_event(self, summary):  # For string similarity calculation
    
        service = self.service
        events = self.fetch_events(100)
        
        if not events:
            return "No events found in your calendar to delete."
        
        # Get all event summaries and calculate similarity scores
        event_summaries = [event.get('summary', '') for event in events]
        similarity_scores = [(event, difflib.SequenceMatcher(None, summary.lower(), 
                            event.get('summary', '').lower()).ratio()) 
                            for event in events]
        
        # Sort by similarity score in descending order
        similarity_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Get the best match (highest similarity score)
        best_match = similarity_scores[0]
        best_match_event = best_match[0]
        best_match_score = best_match[1]
        
        # Threshold for considering a match "good enough" (can be adjusted)
        threshold = 0.6
        
        if best_match_score >= threshold:
            event_id = best_match_event.get('id')
            event_summary = best_match_event.get('summary')
            
            try:
                service.events().delete(calendarId="primary", eventId=event_id).execute()
                return f"Event '{event_summary}' was deleted successfully! (Match score: {best_match_score:.2f})"
            except HttpError as error:
                return f"An error occurred while trying to delete '{event_summary}': {error}"
        else:
            # Return top 3 possible matches if nothing is a great match
            top_matches = [f"'{match[0].get('summary')}' (score: {match[1]:.2f})" 
                        for match in similarity_scores[:3] if match[1] > 0.3]
            
            if top_matches:
                matches_text = "\n- ".join(top_matches)
                return f"No event closely matching '{summary}' was found. Did you mean one of these?\n- {matches_text}"
            else:
                return f"No event matching '{summary}' was found in your calendar."

    def delete_all_event(self):
        service = self.service
        events = self.fetch_events(7)
        for event in events:
            event_id = event.get('id')
            try:
                service.events().delete(calendarId="primary", eventId=event_id).execute()
                print(f"Event {event_id} deleted successfully!")

            except HttpError as error:
                print(f"An error occurred: {error}")
        return "Your event was deleted successfully! Let me know if you need anything else"
    


    def get_functions_called(self):
        return self.functions_called

    