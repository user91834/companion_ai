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


def send_push_fcm_voice(
    token: str,
    title: str,
    body: str,
    audio_url: str,
    *,
    auto_play: bool = True,
    allow_background: bool = False,
    allow_lockscreen: bool = False,
):
    """
    Envia push FCM com payload de voz para o cliente poder dar play automático,
    inclusive em segundo plano ou com tela desligada, conforme as flags.
    Os valores em data devem ser strings (exigência do FCM).
    """
    access = get_access_token()
    url = f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send"

    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json; charset=utf-8",
    }

    data = {
        "type": "assistant_voice",
        "audio_url": audio_url,
        "auto_play": "true" if auto_play else "false",
        "allow_background": "true" if allow_background else "false",
        "allow_lockscreen": "true" if allow_lockscreen else "false",
    }

    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data,
            "android": {
                "priority": "HIGH",
                "notification": {
                    "sound": "default",
                    "channel_id": "assistant_voice",
                },
            },
            "apns": {
                "payload": {
                    "aps": {
                        "sound": "default",
                        "content-available": 1,
                    },
                },
                "fcm_options": {},
            },
        }
    }

    return requests.post(url, headers=headers, json=payload, timeout=15)