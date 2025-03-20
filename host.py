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
        self.model = GenerativeModel(os.environ.get("MODEL_NAME", "gemini-pro"))

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
            for t in self.all_tools:
                current_tool_name = getattr(t, "name", t.get("name") if isinstance(t, dict) else "unknown")

                if (tool_name == current_tool_name):
                    return self.mcp_clients[server_name]
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
        # Format messages for Gemini
        chat = self.model.start_chat(history=[])
        for server_name in self.mcp_clients.keys():
            client = self.mcp_clients[server_name]
            available_functions = await client.processToolsForGemini()
            print(f"Available functions: {available_functions}")
            print(f"Sending {len(available_functions)} functions to Gemini")
            # Initial Gemini API call with functions
            try:
                llm_response = await chat.send_message_async(
                    query,
                    generation_config={"temperature": 0.0},
                    tools=[{"function_declarations": available_functions}]
                )
                    # Process response and handle tool calls
                tool_results = []
                final_text = []
                #print(f"LLM response: {llm_response}")
                if hasattr(llm_response, 'candidates') and llm_response.candidates:
                    for candidate in llm_response.candidates:
                        #print(f"Candidate: {candidate}")
                        processed_response = self.process_llm_candidate(candidate)
                        if processed_response is None:
                            continue
                        print(f"Processed response: {processed_response}", "instance of:", type(processed_response))  
                        if isinstance(processed_response, dict) and processed_response['type'] == 'function_call':
                            print(f"Executing tool: {processed_response['name']} with args: {processed_response['args']}")
                            try:
                                tool_result = await client.session.call_tool(
                                    processed_response['name'], 
                                    processed_response['args']
                                )
                                tool_results.append({"call": processed_response['name'], "result": tool_result})
                                final_text.append(f"[Calling tool {processed_response['name']} with args {processed_response['args']}]")

                                # Continue conversation with tool results
                                follow_up_response = await chat.send_message_async(
                                    f"Tool result: {tool_result.content}"
                                )
                            
                                if hasattr(follow_up_response, 'text'):
                                    final_text.append(follow_up_response.text)
                                    return "\n".join(final_text)
                            except Exception as e:
                                print(f"Error executing tool: {str(e)}")
                                continue
                        else:
                            continue
                else:
                    print(f"No candidates found in response {llm_response}", "for server: {server_name}")
                
            except Exception as e:
                print(f"Gemini API error: {str(e)}")
                return f"Error calling Gemini API: {str(e)}"

            
        return "\n".join(final_text)

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
                    print(f"Successfully started {server_name}")
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

    def prepare_tools_for_gemini(self, tools):
        """Prepare tools in an ultra-simplified format that Gemini will accept."""
        sanitized_tools = []
        
        print("Preparing tools for Gemini from:", [t.name for t in tools])
        
        for tool in tools:
            # Tools are objects, not dictionaries, so use attribute access
            tool_name = tool.name
            tool_desc = tool.description
            
            # Create the simplest possible tool representation
            simple_tool = {
                "name": tool_name,
                "description": tool_desc,
                "parameters": {"type": "object", "properties": {"input": {"type": "string"}}}
            }
            sanitized_tools.append(simple_tool)
            print(f"Prepared tool: {tool_name}")
            
        return sanitized_tools

async def main():
    host = MCPHost()
    await host.run()

if __name__ == "__main__":
    asyncio.run(main())