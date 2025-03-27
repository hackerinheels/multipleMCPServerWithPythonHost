Here's a step-by-step guide to set up your Google Cloud project and enable the Calendar API:
1. Create a Google Cloud Project
* Go to Google Cloud Console
* Click on the project dropdown at the top and click "New Project"
* Give your project a name (e.g., "Calendar MCP") and click "Create"
1. Enable the Google Calendar API
* In your new project, go to the API Library
* Search for "Google Calendar API"
* Click on it and click "Enable"
1. Configure OAuth Consent Screen
* Go to OAuth consent screen
* Choose "External" user type (unless you're in an organization)
* Fill in the required information:
* App name (e.g., "Calendar MCP")
* User support email (your email)
* Developer contact email (your email)
* Click "Save and Continue"
* Under "Scopes", click "Add or Remove Scopes"
* Add https://www.googleapis.com/auth/calendar.readonly
* Click "Save and Continue"
* Under "Test Users", add your Google email address
* Click "Save and Continue"
1. Create OAuth 2.0 Client ID
* Go to Credentials
* Click "Create Credentials" → "OAuth client ID"
* Choose "Desktop application" as the application type
* Give it a name (e.g., "Calendar MCP Client")
* Under "Authorized redirect URIs", add:
* http://localhost:8081
* http://localhost:8080
* Click "Create"
* You'll see a popup with your client ID and client secret
* Click "Download" to get your credentials.json file
