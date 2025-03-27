import json
import subprocess
import sys
import os
import time
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from google.generativeai import GenerativeModel 
import google.generativeai as genai  
from client import MCPClient
from dotenv import load_dotenv
import traceback

load_dotenv()  # load environment variables from .env

class MCPHost:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.mcp_clients: Dict[str, SSEClient] = {}
        self.all_tools = []
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = GenerativeModel(os.environ.get("MODEL_NAME", "gemini-1.5-flash"))

    def load_server_config(self) -> Dict[str, Any]:
        """Load server configurations from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            return config.get('mcpServers', {})
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.config_path}' not found.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in configuration file '{self.config_path}'.")
            sys.exit(1)
    
    async def load_all_tools(self) -> List[Dict[str, Any]]:
        """Load all tools from all servers"""

        for server_name in self.mcp_clients.keys():
            print(f"Loading tools from {server_name}")

            client = self.mcp_clients[server_name]
            self.all_tools.extend(client.tools)
            #print(f"Loaded {self.all_tools} tools")

    def get_client_for_tool(self, tool_name: str) -> MCPClient:
        """Get the client for a given tool name"""
        for server_name in self.mcp_clients.keys():
            client = self.mcp_clients[server_name]
            for t in client.tools:
                current_tool_name = getattr(t, "name", t.get("name") if isinstance(t, dict) else "unknown")
                if tool_name == current_tool_name:
                    return client               
                    
        print(f"Warning: No client found for tool '{tool_name}'")
        return None

    def convert_part_to_json(self, part):
        """
        Convert a Protocol Buffer Part object to a JSON structure.
        """
        try:
            #print(f"Processing part: {part}")
            
            # Check if it's a function call
            if hasattr(part, 'function_call') and part.function_call.name:
                print(f"Found function call: {part.function_call.name}")
                
                # Initialize args dictionary
                args_dict = {}
                
                # Get the MapComposite object directly
                fields_map = part.function_call.args
                print(f"Fields map type: {type(fields_map)}")
                print(f"Fields map content: {fields_map}")
                
                # Iterate through the MapComposite entries
                for key in fields_map:
                    value_obj = fields_map[key]
                    print(f"Processing key: {key}, value_obj: {value_obj}, type: {type(value_obj)}")
                    
                    # Handle direct string/number values
                    if isinstance(value_obj, (str, int, float, bool)):
                        args_dict[key] = value_obj
                        print(f"Added direct value for {key}: {args_dict[key]}")
                    # Handle structured value objects
                    else:
                        if hasattr(value_obj, 'string_value'):
                            args_dict[key] = value_obj.string_value
                        elif hasattr(value_obj, 'number_value'):
                            args_dict[key] = value_obj.number_value
                        elif hasattr(value_obj, 'bool_value'):
                            args_dict[key] = value_obj.bool_value
                        print(f"Added structured value for {key}: {args_dict[key]}")
                
                print(f"Final args_dict: {args_dict}")
                
                result = {
                    'type': 'function_call',
                    'name': part.function_call.name,
                    'args': args_dict
                }
                print(f"Returning function call result: {result}")
                return result
                
        except Exception as e:
            print(f"Error in function_call processing: {str(e)}")
            traceback.print_exc()
            return None

        # Check if it's a text response
        try:
            if hasattr(part, 'text') and part.text:
                result = {
                    'type': 'text',
                    'content': part.text
                }
                #print(f"Returning text result: {result}")
                return result
        except AttributeError as e:
            print(f"AttributeError in text processing: {e}")
            pass

        print("No valid part type found, returning None")
        return None

    def process_llm_candidate(self, candidate):
        """
        Process the LLM candidate response and convert it to a manageable format.
        """
        try:
            #print("Starting to process candidate")
            if not hasattr(candidate, 'content') or not hasattr(candidate.content, 'parts'):
                print("Invalid candidate structure")
                return None

            for part in candidate.content.parts:
                #print(f"Processing part in candidate")
                json_part = self.convert_part_to_json(part)
                print(f"Converted part to JSON: {json_part}")
                
                if not json_part:
                    print("Skipping invalid part")
                    continue

                if json_part['type'] == 'text':
                    text = json_part['content'].strip()
                    if "sorry" in text.lower() or "cannot" in text.lower():
                        print("Skipping this tool")
                        continue
                    return text

                if json_part['type'] == 'function_call':
                    print(f"Found valid function call: {json_part}")
                    return json_part

            print("No valid parts found in candidate")
            return None

        except Exception as e:
            print(f"Error processing candidate: {str(e)}")
            return None

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a query using Gemini and available tools"""
        # First, collect all available tools from all clients
        all_available_functions = []
        for server_name, client in self.mcp_clients.items():
            client_functions = await client.processToolsForGemini()
            print(f"Available functions from {server_name}: {len(client_functions)}")
            all_available_functions.extend(client_functions)
        
        print(f"Total available functions: {len(all_available_functions)}")
        
        # Format messages for Gemini with planning approach
        chat = self.model.start_chat(history=[])
        
        try:
            # Create a plan using all available tools
            planning_prompt = f"""Given the following task: '{query}', please follow these steps:
1. Analyze the task and outline a plan of actions needed to accomplish it.
2. Identify the available tools that can be used to execute these actions.
3. Chain the tool calls in the order they should be executed, ensuring that the output of one tool can be used as input for the next where applicable.
4. Instead of describing the plan in text, execute it directly by calling the first tool."""

            llm_response = await chat.send_message_async(
                planning_prompt,
                generation_config={"temperature": 0.0},
                tools=[{"function_declarations": all_available_functions}]
            )
            
            # Process response and handle tool calls
            tool_results = []
            final_text = []
            print(f"LLM response: {llm_response}")
            if hasattr(llm_response, 'candidates') and llm_response.candidates:
                # Process the initial planning response
                for candidate in llm_response.candidates:
                    processed_response = self.process_llm_candidate(candidate)
                    
                    if isinstance(processed_response, str):
                        # If it's a text response, check if it contains a plan
                        final_text.append(processed_response)
                        
                        # Try to extract tool names from the plan
                        plan_tools = self._extract_tools_from_plan(processed_response, all_available_functions)
                        
                        if plan_tools:
                            # If we identified tools in the plan, ask LLM to execute the first one
                            print(f"Identified tools in plan: {plan_tools}")
                            first_tool_prompt = f"""Based on your plan:

{processed_response}

Please execute the first step by calling the appropriate tool function now."""

                            first_tool_response = await chat.send_message_async(
                                first_tool_prompt,
                                generation_config={"temperature": 0.0},
                                tools=[{"function_declarations": all_available_functions}]
                            )
                            
                            if hasattr(first_tool_response, 'candidates') and first_tool_response.candidates:
                                for tool_candidate in first_tool_response.candidates:
                                    tool_call = self.process_llm_candidate(tool_candidate)
                                    if isinstance(tool_call, dict) and tool_call['type'] == 'function_call':
                                        print(f"Extracted first tool call: {tool_call}")
                                        await self._execute_tool_chain(chat, tool_call, final_text, tool_results)
                                        break
                    
                    elif isinstance(processed_response, dict) and processed_response['type'] == 'function_call':
                        # Begin executing the plan with sequential tool calls
                        await self._execute_tool_chain(chat, processed_response, final_text, tool_results)
            else:
                print(f"No candidates found in response {llm_response}")
                return "No response generated for your query."
            
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            traceback.print_exc()
            return f"Error calling Gemini API: {str(e)}"

        return "\n".join(final_text)
        
    async def _execute_tool_chain(self, chat, initial_tool_call, final_text, tool_results):
        """Execute a chain of tool calls, passing outputs as inputs when needed"""
        current_tool_call = initial_tool_call
        
        while current_tool_call is not None:
            
            tool_name = current_tool_call['name']
            tool_args = current_tool_call['args']
            
            print(f"Executing tool: {tool_name} with args: {tool_args}")
            final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
            
            # Find the right client for this tool
            client = self.get_client_for_tool(tool_name)
            print(f"Client identified: {client}")
            if not client:
                final_text.append(f"[Error: No client found for tool {tool_name}]")
                break
                
            try:
                # Execute the tool
                print(f"EXECUTING NOW!!, tool_name: {tool_name}, tool_args: {tool_args}")
                
                tool_result = await client.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": tool_result})
                
                # Continue conversation with tool results to get next action
                follow_up_prompt = f"""Tool {tool_name} result: {tool_result.content}

Based on this result, what is the next step in your plan? 
If another tool needs to be called, use the appropriate function call.
If no further tools are needed, provide a final response."""

                follow_up_response = await chat.send_message_async(
                    follow_up_prompt,
                    generation_config={"temperature": 0.0},
                    tools=[{"function_declarations": [tool for client in self.mcp_clients.values() 
                                                    for tool in await client.processToolsForGemini()]}]
                )
                
                # Process the follow-up response
                next_response = None
                if hasattr(follow_up_response, 'candidates') and follow_up_response.candidates:
                    for candidate in follow_up_response.candidates:
                        print(f"Processing follow-up candidate: {candidate}")
                        next_response = self.process_llm_candidate(candidate)
                        print(f"Next response: {next_response}, type: {type(next_response)}")
                        
                        if next_response is not None:
                            break
                
                if next_response is None:
                    print("No valid next step found")
                    final_text.append("[No further actions determined]")
                    current_tool_call = None
                elif isinstance(next_response, str):
                    # Text response means we're done or have info to show
                    print(f"Text response received: {next_response}")
                    final_text.append(next_response)
                    current_tool_call = None  # End the chain
                elif isinstance(next_response, dict) and next_response['type'] == 'function_call':
                    # Another tool call, continue the chain
                    print(f"Function call response received: {next_response}")
                    current_tool_call = next_response
                else:
                    print(f"Unexpected response type: {type(next_response)}")
                    final_text.append(f"[Unexpected response format: {next_response}]")
                    current_tool_call = None
                    
            except Exception as e:
                print(f"Error executing tool {tool_name}: {str(e)}")
                traceback.print_exc()
                final_text.append(f"[Error executing tool {tool_name}: {str(e)}]")
                current_tool_call = None

    def _extract_tools_from_plan(self, plan_text, available_functions):
        """Extract tool names mentioned in a plan text"""
        tool_names = []
        
        # Create a mapping of lowercase tool names to actual tool names
        # This helps with case insensitive matching
        name_map = {}
        for func in available_functions:
            name = func.get('name', '')
            if name:
                name_map[name.lower()] = name
                
                # Also add versions without special characters for fuzzy matching
                simple_name = ''.join(c for c in name.lower() if c.isalnum() or c == '_')
                if simple_name and simple_name != name.lower():
                    name_map[simple_name] = name
        
        # Look for tool names in the plan text
        plan_lower = plan_text.lower()
        for simple_name, actual_name in name_map.items():
            if simple_name in plan_lower:
                if actual_name not in tool_names:
                    tool_names.append(actual_name)
                
        return tool_names

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nHost application Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                    
                final_llm_response = await self.process_query(query)
                print("\n" + final_llm_response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def run(self):
        """Main run loop for the server host."""
        servers = self.load_server_config()
        #print(f"Servers: {servers}")
        try:
            #Start all servers
            for server_name, config in servers.items():
                
                try:
                    client = MCPClient(server_name, config)
                    self.mcp_clients[server_name] = client
                    await client.start_server()
                    print(f"Successfully started {server_name}, : {client}")
                except Exception as e:
                    print(f"Failed to start server '{server_name}': {e}")
                    continue
            print("All servers started")
            print("Starting chat loop")
            await self.load_all_tools()
            await self.chat_loop()        
            
            # Keep running until interrupted
            #TODO: Keep checking if servers are running
            #while self.running_servers:
            #    for server_name, process in list(self.running_servers.items()):
            #        if process.poll() is not None:
            #            stdout, stderr = process.communicate()
            #            print(f"\nServer '{server_name}' has stopped:")
            #            print(f"stdout: {stdout}")
            #            print(f"stderr: {stderr}")
            #            await self.stop_server(server_name)
                
            #    await asyncio.sleep(1)
        

        except KeyboardInterrupt:
            print("\nShutting down servers...")
            
            for server_name in list(self.mcp_clients.keys()):
                client = self.mcp_clients[server_name]
                await client.stop_server()
                await client.close()  # Using close() instead of disconnect()
                del self.mcp_clients[server_name]
                print(f"Stopped server: {server_name}")
                print(f"mcp_clients: {self.mcp_clients}")
            print("All servers stopped")


async def main():
    host = MCPHost()
    await host.run()

if __name__ == "__main__":
    asyncio.run(main())
