# Multiple MCP SSE Servers with a Python Host
This repository contains a Server-Sent Events (SSE) Model Control Protocol (MCP) client implementation that uses Google's Gemini API.
The Host app reads the config.json file, instantiates instances of MCP Client class to launch the MCP servers and maintain connections with them, clean up on shutdown etc.

It's possible to package this host app as a dmg package and distribute which can then be used with any MCP SSE ervers. 
Todo: Add stdio server support
Todo: Add multiple model support
Todo: Add tool chaining


## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/hackerinheels/multipleMCPServerWithPythonHost.git
   cd multipleMCPServerWithPythonHost
   ```

2. Create a `.env` file in the root directory with your API keys:
   ```
   GEMINI_API_KEY=your_api_key_here
   MODEL_NAME=gemini-2.0-flash
   ```

   You can get a Gemini API key from [Google's AI Studio](https://makersuite.google.com/app/apikey).

3. Set up Google Calendar API using the instructions in the googleCalendar/README.md file

4. Update config.json to include the browser-use server:
   ```json
   {
       "mcpServers": {
           "calendar": {
               "command": "uv",
               "args": ["run", "googleCalendar/calendarServer.py", "--port", "8000"]
           },
           "browser-use": {
               "command": "uv",
               "args": ["run", "<path-to-browser-use-mcp-server>/server", "--port", "8006"]
           }
       }
   }
   ```
   Replace `<path-to-browser-use-mcp-server>` with the actual path where you cloned the repository.
5. Create a `.env` file in the browser-use-mcp-server directory with the following configuration:
```env
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

## Running the Application
```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
uv run host.py
```
This will start all the servers listed in the config.json file

## Usage

Once the servers and client are running, you can interact with them by typing queries.


### Google Calendar Commands
The calendar server provides the following tools:
- `list_events`: List upcoming calendar events
- `get_event_details`: Get detailed information about a specific event
- `search_events`: Search for events matching a query

Example queries:
- "Show my upcoming events"
- "Search for meetings with John"
- "Get details for event {event_id}"

### Browser Use For Browser Automation
This tool enable browser automation and control with the following tools:
- 'browser_use'
- 'browser_get_result'

Type `quit` to exit the client.

## Requirements

- Python 3.11+
- UV package manager
- Google Gemini API key
- Google Calendar API credentials (for calendar server)

## License

[MIT](LICENSE)

# MCP Multi-Server Configuration

This repository demonstrates how to load and run multiple MCP servers using a configuration file.

## Servers Included

### Calendar Server
- Interact with Google Calendar
- Manage events and schedules

### Browser-use Server
- Automate browser interactions
- Control Chrome browser programmatically
- Execute browser-based tasks



### 4. Browser-use Server Environment Setup
Create a `.env` file in the browser-use-mcp-server directory with the following configuration:
```env
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```
Note: Make sure to replace "your-openai-api-key" with your actual OpenAI API key.

## Notes
- Make sure all API keys are properly configured in .env
- Ensure Chrome is installed for browser-use server
- Each server runs on its designated port
- The host manages all server lifecycles

## Troubleshooting
- If a server fails to start, check its port availability
- Verify all environment variables are set correctly
- Ensure Chrome path is correct for your system 
