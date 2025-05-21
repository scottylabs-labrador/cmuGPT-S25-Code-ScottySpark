from openai import OpenAI, APITimeoutError, APIError
import json
from dotenv import load_dotenv
import os
import time
from perplexity_integration import CMUPerplexitySearch  # Changed from relative import
import requests
from datetime import datetime


#from courses import get_courses, get_course_by_id, get_fces, get_fces_by_id, get_schedules


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
                "content": "If someone inquires about dining direct them to visit https://cmueats.com and always call the function to display it to the UI, while if someone asks about courses at CMU direct them ot visit https://cmucourses.com, while if someone asks about directions direct them to visit https://cmumaps.com, while if someone asks about ScottyLabs direct them to visit https://ScottyLabs.org"
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
        ]
        return tools

    def process_user_input(self, user_input):
        self.messages.append({"role": "user", "content": user_input})
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model='gpt-4o-mini',  # Fixed model name
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

    def get_functions_called(self):
        return self.functions_called

    