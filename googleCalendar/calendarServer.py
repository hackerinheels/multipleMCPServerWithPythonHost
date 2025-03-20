import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from starlette.applications import Starlette
from sse_starlette.sse import EventSourceResponse

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn


# If modifying these scopes, delete the file token.json.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

calendarMCP = FastMCP("Google Calendar Services")
CREDENTIALS_PATH = os.path.abspath(os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json'))
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

async def get_calendar_service():
    """Get an authorized Google Calendar service instance."""
    creds = None
    # Make sure the parent directory exists
    Path(CREDENTIALS_PATH).parent.mkdir(parents=True, exist_ok=True)
    token_path = Path(CREDENTIALS_PATH).parent / 'token.json'
    print("Came here????? !!!")
    try:
        if token_path.exists():
            print("Found existing token.json")
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            print("Loaded credentials from token.json")

        if not creds or not creds.valid:
            print("Credentials not valid, checking if refresh possible...")
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                print("Starting new OAuth flow...")
                if not Path(CREDENTIALS_PATH).exists():
                    raise FileNotFoundError(f"credentials.json not found at {CREDENTIALS_PATH}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH, SCOPES)
                print("Opening browser for OAuth consent...")
                creds = flow.run_local_server(port=0)
                print("OAuth flow completed successfully")

            # Save the credentials
            print(f"Saving credentials to {token_path}")
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        print("Building calendar service...")
        service = build('calendar', 'v3', credentials=creds)
        print("Calendar service built successfully")
        return service

    except Exception as e:
        print(f"Error in get_calendar_service: {str(e)}")
        raise

@calendarMCP.tool("list_events")
async def list_events(time_min: Optional[str] = None, 
                     time_max: Optional[str] = None, 
                     max_results: int = 10) -> Dict[str, Any]:
    """List upcoming events from the user's calendar.
    
    Args:
        time_min: Start time in ISO format (optional, defaults to now)
        time_max: End time in ISO format (optional)
        max_results: Maximum number of events to return (default: 10)
    """
    try:
        print("Received args:", args)  # Add this at the start of your function
        service = await get_calendar_service()
        
        # Ensure proper datetime format
        if not time_min:
            time_min = datetime.utcnow().isoformat() + 'Z'
        elif not time_min.endswith('Z'):
            time_min = time_min + 'Z'
            
        if time_max and not time_max.endswith('Z'):
            time_max = time_max + 'Z'
            
        # Print debug information
        print(f"Calling Google Calendar API with parameters:")
        print(f"time_min: {time_min}")
        print(f"time_max: {time_max}")
        print(f"max_results: {max_results}")
        
        # Construct the request parameters
        request_params = {
            'calendarId': 'primary',
            'timeMin': time_min,
            'maxResults': min(max_results, 100),  # Limit to 100 max
            'singleEvents': True,
            'orderBy': 'startTime'
        }
        
        if time_max:
            request_params['timeMax'] = time_max
            
        print(f"Final request parameters: {request_params}")
        
        # Make the API call
        events_result = service.events().list(**request_params).execute()
        
        events = events_result.get('items', [])
        
        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            formatted_events.append({
                'id': event['id'],  # Added id to help with get_event_details
                'summary': event.get('summary', 'No title'),
                'start': start,
                'description': event.get('description', ''),
                'location': event.get('location', '')
            })
            
        return {
            'events': formatted_events,
            'count': len(formatted_events)
        }
        
    except HttpError as error:
        print(f"Google Calendar API error: {error.content}")  # Print full error content
        return {"error": f"Calendar API error: {str(error)}"}
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@calendarMCP.tool("get_event_details")
async def get_event_details(event_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific calendar event.
    
    Args:
        event_id: The ID of the event to retrieve
    """
    try:
        service = await get_calendar_service()
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        return {
            'summary': event.get('summary', 'No title'),
            'description': event.get('description', ''),
            'start': event['start'].get('dateTime', event['start'].get('date')),
            'end': event['end'].get('dateTime', event['end'].get('date')),
            'location': event.get('location', ''),
            'attendees': [
                {'email': attendee.get('email'), 'response_status': attendee.get('responseStatus')}
                for attendee in event.get('attendees', [])
            ],
            'organizer': event.get('organizer', {}).get('email'),
            'status': event.get('status'),
            'created': event.get('created'),
            'updated': event.get('updated')
        }
        
    except HttpError as error:
        return {"error": f"Calendar API error: {str(error)}"}

@calendarMCP.tool("search_events")
async def search_events(query: str,
                       time_min: Optional[str] = None,
                       max_results: int = 10) -> Dict[str, Any]:
    """Search for calendar events matching the given query.
    
    Args:
        query: Search term to find in event summary or description
        time_min: Start time in ISO format (optional, defaults to now)
        max_results: Maximum number of events to return (default: 10)
    """
    try:
        service = await get_calendar_service()
        
        if not time_min:
            time_min = datetime.utcnow().isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime',
            q=query
        ).execute()
        
        events = events_result.get('items', [])
        
        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            formatted_events.append({
                'id': event['id'],
                'summary': event.get('summary', 'No title'),
                'start': start,
                'description': event.get('description', ''),
                'location': event.get('location', '')
            })
            
        return {
            'events': formatted_events,
            'count': len(formatted_events)
        }
        
    except HttpError as error:
        return {"error": f"Calendar API error: {str(error)}"}

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    mcp_server = calendarMCP._mcp_server  # noqa: WPS437
    import argparse
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8081, help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
