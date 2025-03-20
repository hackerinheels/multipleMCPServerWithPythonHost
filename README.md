# SSE-MCP Client

This repository contains a Server-Sent Events (SSE) Model Control Protocol (MCP) client implementation that uses Google's Gemini API.

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/hackerinheels/sse-mcp.git
   cd sse-mcp
   ```

2. Create a `.env` file in the root directory with your API keys:
   ```
   GEMINI_API_KEY=your_api_key_here
   MODEL_NAME=gemini-pro
   ```

   You can get a Gemini API key from [Google's AI Studio](https://makersuite.google.com/app/apikey).

3. Set up Google Calendar API:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Calendar API
   - Create OAuth 2.0 credentials
   - Download the credentials and save as `credentials.json` in the `googleCalendar` directory

## Running the Application

You can run either or both MCP servers:

### Eagle Feed Server (Terminal Window 1)

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
uv run eagleFeed/eagleFeed.py
```

### Google Calendar Server (Terminal Window 2)

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
uv run googleCalendar/calendarServer.py
```

### Client (Terminal Window 3)

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
# For Eagle Feed server:
uv run client.py http://0.0.0.0:8080/sse
# For Calendar server:
uv run client.py http://0.0.0.0:8081/sse
```

## Usage

Once the servers and client are running, you can interact with them by typing queries.

### Eagle Feed Commands
Type queries to interact with the Eagle Feed server.

### Google Calendar Commands
The calendar server provides the following tools:
- `list_events`: List upcoming calendar events
- `get_event_details`: Get detailed information about a specific event
- `search_events`: Search for events matching a query

Example queries:
- "Show my upcoming events"
- "Search for meetings with John"
- "Get details for event {event_id}"

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

1. **Eagle Feed Server**
   - Provides information about live bald eagle cam feeds
   - Runs on port 8001

2. **Calendar Server**
   - Handles Google Calendar interactions
   - Runs on port 8000

3. **Browser-use MCP Server**
   - Enables browser automation and interaction
   - Runs on port 8006
   - Source: [browser-use-mcp-server](https://github.com/co-browser/browser-use-mcp-server)

## Setup Instructions

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file with your API keys:
```env
GEMINI_API_KEY="your-gemini-api-key"
MODEL_NAME="gemini-1.5-flash"
```

### 3. Browser-use MCP Server Setup
1. Download the server:
   ```bash
   git clone https://github.com/co-browser/browser-use-mcp-server
   ```
2. Update config.json to include the browser-use server:
   ```json
   {
       "mcpServers": {
           "eagleFeed": {
               "command": "uv",
               "args": ["run", "eagleFeed/eagleFeed.py", "--port", "8001"]
           },
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

### 4. Browser-use Server Environment Setup
Create a `.env` file in the browser-use-mcp-server directory with the following configuration:
```env
OPENAI_API_KEY="your-openai-api-key"
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```
Note: Make sure to replace "your-openai-api-key" with your actual OpenAI API key.

## Running the Servers

1. Start the host:
   ```bash
   python host.py
   ```

2. The host will automatically start all configured servers based on config.json

## Available Functionality

### Eagle Feed Server
- Get information about live bald eagle cam feeds
- Access feed locations and descriptions

### Calendar Server
- Interact with Google Calendar
- Manage events and schedules

### Browser-use Server
- Automate browser interactions
- Control Chrome browser programmatically
- Execute browser-based tasks

## Requirements
See requirements.txt for complete list of dependencies.

## Notes
- Make sure all API keys are properly configured in .env
- Ensure Chrome is installed for browser-use server
- Each server runs on its designated port
- The host manages all server lifecycles

## Troubleshooting
- If a server fails to start, check its port availability
- Verify all environment variables are set correctly
- Ensure Chrome path is correct for your system 