import asyncio
import json
import sys
from typing import Dict, Any, Optional, List  # Make sure these imports are present
from contextlib import AsyncExitStack
import re
import time
import subprocess

from mcp import ClientSession
from mcp.client.sse import sse_client


class MCPClient:
    def __init__(self, server_name: str, server_config: Dict[str, Any]):
         # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.running_server: Dict[str, subprocess.Popen] = {}
        self.exit_stack = AsyncExitStack()
        self.base_url: str = ""  # Empty string instead of type
        self.port: int = 0       # Default value instead of type
        self.server_name: str = server_name  # Store the actual value
        self.server_config: Dict[str, Any] = server_config  # Store the actual value
        self._streams_context = None  # Add this
        self._session_context = None  # Add this
        self.tools = []

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an MCP server running with SSE transport"""
        # Store the context managers so they stay alive
        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()
        print("Got SSE streams")

        print("Creating ClientSession")
        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()
        print("Session created successfully")

        # Initialize tools
        await self.session.initialize()

        # List available tools to verify connection
        print("Initialized SSE client...")
        print("Listing tools...")
        response = await self.session.list_tools()
        self.tools = response.tools if hasattr(response, 'tools') else []
        print("\nConnected to server with tools:", [tool.name for tool in self.tools])

    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def detect_server_port(self, process: subprocess.Popen, timeout: int = 10) -> Optional[int]:
        """Detect the port of the running server"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            output = process.stdout.readline()
            if output:
                match = re.search(r'Listening on (\d+)', output)
                if match:
                    port = int(match.group(1))
                    print(f"Detected port {port} for server '{self.server_name}'")
                    return port
            await asyncio.sleep(0.1)
        print(f"Timeout waiting for port detection after {timeout} seconds")
        return None

    async def start_server(self) -> List[Dict[str, Any]]:  
        """Start an MCP server and establish SSE connection."""
        try:
            tool_list = []

            # Extract the port from the arguments if "--port" is specified
            command = [self.server_config['command']]
            args = self.server_config.get('args', [])
            
            # Look for "--port" or "-p" in the arguments
            port = None
            for i, arg in enumerate(args):
                if arg in ['--port', '-p'] and i + 1 < len(args) and args[i + 1].isdigit():
                    port = int(args[i + 1])
                    print(f"Found port {port} in command arguments")
                    self.port = port
                    break
                # Also handle combined format like "--port=8000"
                elif arg.startswith('--port=') or arg.startswith('-p='):
                    port_str = arg.split('=')[1]
                    if port_str.isdigit():
                        port = int(port_str)
                        print(f"Found port {port} in command arguments")
                        self.port = port
                        break
            
            # If no port in args, check config
            if port is None and 'port' in self.server_config:
                port = int(self.server_config['port'])
                print(f"Using port {port} from config")
                self.port = port
            
            # Start the server process
            full_command = command + args
            print(f"Starting server '{self.server_name}' with command: {' '.join(full_command)}")
            
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.running_server[self.server_name] = process
            # Wait a bit for the server to start
            await asyncio.sleep(5)
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"Server '{self.server_name}' failed to start:")
                print(f"stdout: {stdout}")
                print(f"stderr: {stderr}")
                raise Exception(f"Server '{self.server_name}' failed to start")

            # If we still don't have the port, try to detect it
            if not hasattr(self, 'port') or not self.port:
                try:
                    self.port = await self.detect_server_port(process)
                except Exception as e:
                    print(f"Error detecting port: {e}")
                    # Don't raise - continue with default port
                
                if not self.port:
                    # Fallback to default port if detection fails
                    self.port = 8000
                    print(f"Could not detect port, using default port {self.port}")
            print("Came here 1")
            # Create SSE client and connect
            try:
                self.base_url = f"http://localhost:{self.port}/sse"
                print(f"Connecting to server '{self.server_name}' at {self.base_url}")
                
                # Add timeout for connection attempt
                await asyncio.wait_for(
                    self.connect_to_sse_server(self.base_url),
                    timeout=60  # Increase timeout to 60 seconds
                )
                
                print(f"Successfully connected to server '{self.server_name}'")
                
                # Get and format tools
                try:
                    if not self.session:
                        raise Exception("No session established")
                        
                    print("Listing tools from server...")
                    response = await self.session.list_tools()
                    print(f"Got response with {len(response.tools) if response and hasattr(response, 'tools') else 0} tools")
                    
                    for tool in response.tools:
                        # Create an extremely simplified schema
                        # Store the original tool information for reference
                        original_tool = tool
                        
                        # Create a minimal parameter structure that Gemini will accept
                        parameters = {
                            "type": "object",
                            "properties": {
                                "input": {"type": "string", "description": f"Input for {tool.name}"}
                            }
                        }
                        
                        function_info = {
                            "name": f"{self.server_name}.{tool.name}",
                            "description": tool.description,
                            "parameters": parameters,
                            "client": self,  # Include reference to this client
                            "original_tool": original_tool  # Store original tool
                        }
                        
                        tool_list.append(function_info)
                        print(f"Added tool: {function_info['name']}")
                    
                    return tool_list
                    
                except Exception as tool_error:
                    print(f"Error getting tools: {tool_error}")
                    # Try to retrieve any error output from the server
                    if hasattr(process, 'stderr') and process.stderr:
                        error_output = process.stderr.read()
                        if error_output:
                            print(f"Server error output: {error_output}")
                    raise Exception(f"Failed to get tools: {str(tool_error)}")
                
            except asyncio.TimeoutError:
                raise Exception(f"Timeout connecting to server '{self.server_name}'")
            except Exception as conn_error:
                raise Exception(f"Connection error: {str(conn_error)}")

        except Exception as e:
            import traceback
            print(f"Error with server '{self.server_name}':")
            traceback.print_exc()  # Print full traceback
            await self.stop_server()
            return []

    async def stop_server(self) -> None:
        """Stop a server and clean up its connections."""
        try:
            # First, clean up the session
            await self.cleanup()
            
            # Then terminate the process
            if self.server_name in self.running_server:
                process = self.running_server[self.server_name]
                try:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"Process didn't terminate, killing it")
                        process.kill()
                        process.wait(timeout=2)
                except Exception as e:
                    print(f"Error terminating process: {e}")
                
                del self.running_server[self.server_name]
                
            print("Stopped server", self.server_name)
            
        except Exception as e:
            print(f"Error in stop_server: {e}")


    async def processToolsForGemini(self) -> List[Dict[str, Any]]:
        """Process a query using Gemini and available tools"""
        # Format messages for Gemini
        # Convert MCP tools to Gemini function format
        print(self.session)
        print(self)
        print(self.tools)
        local_tool_list = await self.session.list_tools()
        #print(f"Got local_tool_list with {len(local_tool_list.tools) if local_tool_list and hasattr(local_tool_list, 'tools') else 0} tools")
        available_functions = []
        for tool in local_tool_list.tools:
            # Default parameters with a simple string parameter if none provided
            parameters = {
                "type": "object",
                "properties": {}  # Start with empty properties object
            }
            
            # Try to extract schema from inputSchema if available
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                try:
                    # If it's a string, parse it as JSON
                    if isinstance(tool.inputSchema, str):
                        schema = json.loads(tool.inputSchema)
                    else:
                        schema = tool.inputSchema
                    
                    # Clean up the schema to remove unsupported fields
                    cleaned_schema = self._clean_json_schema(schema)
                    
                    # Only update if we have valid properties
                    if "properties" in cleaned_schema and cleaned_schema["properties"]:
                        parameters["properties"] = cleaned_schema["properties"]
                        
                        # Add required fields only if they exist in properties
                        if "required" in cleaned_schema and isinstance(cleaned_schema["required"], list):
                            valid_required = []
                            for prop in cleaned_schema["required"]:
                                if isinstance(prop, str) and prop in parameters["properties"]:
                                    valid_required.append(prop)
                                else:
                                    print(f"Warning: Required property '{prop}' not found in properties for tool {tool.name}")
                            
                            if valid_required:
                                parameters["required"] = valid_required
                except (json.JSONDecodeError, TypeError, AttributeError) as e:
                    print(f"Error parsing schema for {tool.name}: {e}")
            
            # If no properties were added, use the default input parameter
            if not parameters["properties"]:
                parameters["properties"] = {
                    "input": {
                        "type": "string",
                        "description": "Input for the tool"
                    }
                }
                parameters["required"] = ["input"]
                      
            function = {
                "name": tool.name,
                "description": tool.description,
                "parameters": parameters
            }
            # Debug output for this function
            #print(f"\nFunction declaration for {tool.name}:")
            #print(json.dumps(function, indent=2))
            if "required" in parameters:
                for req in parameters["required"]:
                    if req not in parameters["properties"]:
                        print(f"ERROR: Required property '{req}' not in properties!")
            
            available_functions.append(function)
        return available_functions

    def _clean_json_schema(self, schema):
            """Clean JSON schema by handling or removing unsupported fields."""
            # These are fields that might cause issues with Gemini
            unsupported_fields = [
                "anyOf", "allOf", "oneOf", "not", "$ref", 
                "additionalProperties", "patternProperties", "propertyNames",
                "dependencies", "if", "then", "else", "default",
                "const", "enum", "format", "contentEncoding", "contentMediaType",
                "examples", "title", "definitions", "$schema", "$id",
                "uniqueItems", "contains", "multipleOf", "exclusiveMinimum", 
                "exclusiveMaximum", "pattern"
            ]
            
            if not isinstance(schema, dict):
                return schema
                
            cleaned = {}
            for key, value in schema.items():
                # Handle unsupported fields
                if key in unsupported_fields:
                    # For anyOf/oneOf, try to use the first schema option
                    if key in ["anyOf", "oneOf"] and isinstance(value, list) and value:
                        # Take the first option as a simplification
                        first_option = value[0]
                        if isinstance(first_option, dict):
                            for sub_key, sub_value in first_option.items():
                                # Don't overwrite existing keys
                                if sub_key not in cleaned:
                                    cleaned[sub_key] = self._clean_json_schema(sub_value)
                    # For allOf, try to merge all schemas (simplified approach)
                    elif key == "allOf" and isinstance(value, list):
                        for sub_schema in value:
                            if isinstance(sub_schema, dict):
                                for sub_key, sub_value in sub_schema.items():
                                    # Don't overwrite existing keys
                                    if sub_key not in cleaned:
                                        cleaned[sub_key] = self._clean_json_schema(sub_value)
                    # Special handling for enum values (convert to string description)
                    elif key == "enum" and isinstance(value, list):
                        if "description" not in cleaned:
                            enum_values = ", ".join([str(v) for v in value])
                            cleaned["description"] = f"Allowed values: {enum_values}"
                    # Handle title by adding it to description
                    elif key == "title" and isinstance(value, str):
                        if "description" in cleaned:
                            cleaned["description"] = f"{value}: {cleaned['description']}"
                        else:
                            cleaned["description"] = value
                    # Simply skip other unsupported fields
                    continue
                # Recursively process nested schemas
                elif isinstance(value, dict):
                    cleaned[key] = self._clean_json_schema(value)
                # Process arrays that might contain schemas
                elif isinstance(value, list):
                    cleaned_list = []
                    for item in value:
                        if isinstance(item, dict):
                            cleaned_list.append(self._clean_json_schema(item))
                        else:
                            cleaned_list.append(item)
                    cleaned[key] = cleaned_list
                # Keep other values as they are
                else:
                    cleaned[key] = value
                    
            return cleaned

    async def callTool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool with the given name and arguments"""
        result = await self.session.call_tool(tool_name, tool_args)
        print(f"Tool {tool_name} called with args {tool_args} and result {result}")
        return result
