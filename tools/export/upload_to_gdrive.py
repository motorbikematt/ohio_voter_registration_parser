import os
import sys
from pathlib import Path

# Add project root to path for imports if needed
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Required packages not installed. Please run:")
    print("  .venv\\Scripts\\pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    creds = None
    token_path = PROJECT_ROOT / 'token.json'
    cred_path = PROJECT_ROOT / 'credentials.json'

    # Load existing token if it exists
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not cred_path.exists():
                print("\nError: 'credentials.json' not found at the root of the project.")
                print("To upload files automatically, you must:")
                print("  1. Go to Google Cloud Console (https://console.cloud.google.com/)")
                print("  2. Create a project and enable the 'Google Drive API'")
                print("  3. Go to APIs & Services > Credentials")
                print("  4. Click + Create Credentials > OAuth client ID (set application type to Desktop app)")
                print("  5. Download the JSON, rename it to 'credentials.json', and save it at the project root:")
                print(f"     -> {cred_path}\n")
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the token
        token_path.write_text(creds.to_json())

    # Build the service
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': 'Ohio Voter Cohorts: Simple Definitions and Guide',
        'mimeType': 'application/vnd.google-apps.document'  # Converts to Google Doc format automatically
    }
    
    md_file_path = PROJECT_ROOT / 'docs' / 'cohort_definitions.md'
    if not md_file_path.exists():
        print(f"Error: Source file not found at {md_file_path}")
        sys.exit(1)
        
    media = MediaFileUpload(
        str(md_file_path),
        mimetype='text/markdown',
        resumable=True
    )
    
    print("Uploading file to Google Drive...")
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    print("\n✓ Success!")
    print(f"File ID: {uploaded_file.get('id')}")
    print(f"View/Edit Link: {uploaded_file.get('webViewLink')}")

if __name__ == '__main__':
    main()
