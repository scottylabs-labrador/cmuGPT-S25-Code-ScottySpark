# cmugpt_assistant.py

from openai import OpenAI, APITimeoutError, APIError
import json
from dotenv import load_dotenv
import os
import time
from perplexity_integration import CMUPerplexitySearch
import requests
import canvas_tools# <-- IMPORT the new module

# Load environment variables at the module level
load_dotenv()

class CMUGPTAssistant:
    def __init__(self):
        # Set up OpenAI client with timeout configuration
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            timeout=60.0,  # 60 second timeout
            max_retries=3  # Allow 3 retries
        )

        # Define the function definitions (tools) for the model
        self.tools = self.get_tools() # Call the method to get tools

        # Initialize conversation messages
        self.messages = [
            {
                "role": "system",
                "content": "You are CMUGPT, an assistant knowledgeable about Carnegie Mellon University in Pittsburgh, Pennsylvania. Use the supplied tools to assist the user. You can also access the user's Canvas information if they ask for it, using the appropriate tools." # Added Canvas context
            },
        ]

        # Keep track of functions called
        self.functions_called = []

        # Initialize helper classes for tools
        self.perplexity_search = CMUPerplexitySearch()
        # No specific initialization needed for canvas_tools module itself

    def get_tools(self):
        """Defines the tools (functions) available to the OpenAI model."""
        tools = [
            # --- Existing Perplexity Tool ---
            {
                "type": "function",
                "function": {
                    "name": "general_purpose_knowledge_search",
                    "description": "Search for general knowledge about Carnegie Mellon University.",
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
                    "strict": True
                }
            },
            # --- ADDED Canvas Courses Tool ---
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
            # --- Add definitions for other tools here ---
        ]
        return tools

    def process_user_input(self, user_input):
        """Handles user input, interacts with OpenAI, calls tools, and returns the final response."""
        self.messages.append({"role": "user", "content": user_input})
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                print(f"\n--- Attempt {attempt + 1}: Sending messages to OpenAI ---")
                # print(json.dumps(self.messages, indent=2)) # Uncomment for deep debugging

                response = self.client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=self.messages,
                    tools=self.tools,
                    tool_choice="auto" # Let the model decide when to call tools
                )

                assistant_message = response.choices[0].message
                print(f"--- OpenAI Response Choice 0 ---")
                # print(assistant_message) # Uncomment for deep debugging

                # Check if the model wants to call a tool
                if assistant_message.tool_calls:
                    print("--- Tool Call Requested ---")
                    # Append the assistant's turn message that contains the tool_calls request
                    self.messages.append(assistant_message)

                    # Process all tool calls requested in this turn
                    for tool_call in assistant_message.tool_calls:
                        function_name = tool_call.function.name
                        # Arguments might be empty, handle safely
                        try:
                            arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                        except json.JSONDecodeError:
                             print(f"Error decoding arguments for {function_name}: {tool_call.function.arguments}")
                             arguments = {"error": "Invalid arguments format"} # Handle error case

                        print(f"Executing tool: {function_name} with args: {arguments}")
                        # Execute the corresponding function
                        result = self.execute_function(function_name, arguments)
                        print(f"Tool result: {result}")

                        # Keep track of functions called (for sidebar display)
                        self.functions_called.append({
                            'function_name': function_name,
                            'arguments': arguments,
                            'result': result # Store the actual result dict/string
                        })

                        # Append the tool's result message back to the conversation history
                        self.messages.append({
                            "role": "tool",
                            "content": json.dumps(result), # Result should be JSON serializable
                            "tool_call_id": tool_call.id
                        })

                    # --- Call OpenAI AGAIN with the tool results included ---
                    print("--- Calling OpenAI again with tool results ---")
                    # print(json.dumps(self.messages, indent=2)) # Uncomment for deep debugging

                    response_after_tool = self.client.chat.completions.create(
                        model='gpt-4o-mini',
                        messages=self.messages,
                        # No tools needed here, we want a final text response
                    )

                    final_assistant_message = response_after_tool.choices[0].message
                    print(f"--- Final OpenAI Response ---")
                    # print(final_assistant_message) # Uncomment for deep debugging

                    self.messages.append(final_assistant_message) # Append final assistant response
                    return final_assistant_message.content # Return the content

                else:
                    # No tool call requested, just return the direct response
                    print("--- Direct Response Received ---")
                    self.messages.append(assistant_message) # Append direct assistant response
                    return assistant_message.content

            except APITimeoutError as e:
                print(f"Attempt {attempt + 1} failed: Timeout Error - {e}")
                if attempt == max_retries - 1: return f"I apologize, but I'm having trouble connecting. Please try again in a moment. (Error: Connection timeout)"
                time.sleep(retry_delay)
                retry_delay *= 2
            except APIError as e:
                print(f"Attempt {attempt + 1} failed: API Error - {e}")
                if attempt == max_retries - 1: return f"I apologize, but there was an error processing your request. Please try again. (Error: {str(e)})"
                time.sleep(retry_delay)
                retry_delay *= 2
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: Unexpected Error - {e}")
                # Log the full traceback for unexpected errors
                import traceback
                traceback.print_exc()
                return f"I apologize, but an unexpected error occurred. Please try again. (Error: {type(e).__name__})"

        return "I apologize, but I was unable to process your request after multiple attempts. Please try again later."

    def execute_function(self, function_name, arguments):
        """Dispatcher to call the correct tool implementation."""
        if function_name == 'general_purpose_knowledge_search':
            # Pass the specific argument the tool expects
            return self.general_purpose_knowledge_search(arguments.get('search_query'))
        # --- ADDED Canvas Courses Tool Call ---
        elif function_name == 'get_current_canvas_courses':
            # This tool takes no arguments from the LLM
            # Call the function imported from canvas_tools.py
            return canvas_tools.fetch_current_courses()
        # --- Add elif statements for other tools here ---
        else:
            print(f"Error: Function '{function_name}' not found.")
            return {"error": f"Function '{function_name}' not found."}

    # --- Tool Implementations (or calls to modules) ---

    def general_purpose_knowledge_search(self, search_query):
        """Calls the Perplexity search helper."""
        # Ensure search_query is provided
        if not search_query:
             return {"error": "Search query was not provided."}
        return self.perplexity_search.search(search_query)

    # Note: get_current_canvas_courses implementation is now in canvas_tools.py

    def get_functions_called(self):
        """Returns the history of functions called during the session."""
        # Return a copy to prevent external modification
        return list(self.functions_called)