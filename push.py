import json
import os

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account

FCM_PROJECT_ID = os.environ.get("FCM_PROJECT_ID", "contextagent-cf19e")
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service-account.json")
SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")


def get_access_token() -> str:
    if SERVICE_ACCOUNT_JSON.strip():
        info = json.loads(SERVICE_ACCOUNT_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )

    creds.refresh(GoogleRequest())
    return creds.token


def send_push_fcm(token: str, title: str, body: str):
    access = get_access_token()
    url = f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send"

    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json; charset=utf-8",
    }

    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
            "android": {
                "priority": "HIGH",
            },
        }
    }

    return requests.post(url, headers=headers, json=payload, timeout=15)