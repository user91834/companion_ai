import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest


FCM_PROJECT_ID = "contextagent-cf19e"
SERVICE_ACCOUNT_FILE = "service-account.json"


def get_access_token() -> str:
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    creds.refresh(GoogleRequest())
    return creds.token


def send_push_fcm(token: str, title: str, body: str):
    access = get_access_token()
    url = f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send"
    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body
            },
            "android": {
                "priority": "HIGH"
            }
        }
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    return r