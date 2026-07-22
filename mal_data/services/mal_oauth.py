from __future__ import annotations

import secrets
import string
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from mal_data.models import MALOAuthToken


AUTHORIZATION_URL = "https://myanimelist.net/v1/oauth2/authorize"
TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"

TOKEN_PK = 1
REFRESH_MARGIN = timedelta(minutes=5)


class MALOAuthError(RuntimeError):
    """Error controlado del ciclo OAuth de MyAnimeList."""


def _required_setting(name: str) -> str:
    value = getattr(settings, name, None)

    if not value:
        raise MALOAuthError(f"{name} no está configurado.")

    return value


def _client_credentials() -> dict[str, str]:
    data = {
        "client_id": _required_setting("MAL_CLIENT_ID"),
    }

    client_secret = getattr(settings, "MAL_CLIENT_SECRET", None)

    if client_secret:
        data["client_secret"] = client_secret

    return data


def generate_code_verifier() -> str:
    alphabet = string.ascii_letters + string.digits + "-._~"

    return "".join(
        secrets.choice(alphabet)
        for _ in range(128)
    )


def build_authorization_url(
    *,
    state: str,
    code_verifier: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": _required_setting("MAL_CLIENT_ID"),
        "code_challenge": code_verifier,
        "code_challenge_method": "plain",
        "state": state,
    }

    redirect_uri = getattr(settings, "MAL_REDIRECT_URI", None)

    if redirect_uri:
        params["redirect_uri"] = redirect_uri

    return f"{AUTHORIZATION_URL}?{urlencode(params)}"


def _post_token(data: dict[str, str]) -> dict:
    response = requests.post(
        TOKEN_URL,
        data=data,
        timeout=30,
    )

    if not response.ok:
        raise MALOAuthError(
            "MyAnimeList OAuth falló. "
            f"Status: {response.status_code}. "
            f"Response: {response.text}"
        )

    payload = response.json()

    if not payload.get("access_token"):
        raise MALOAuthError(
            "MyAnimeList no devolvió un access token."
        )

    return payload


def _save_token_payload(
    payload: dict,
    *,
    previous_refresh_token: str = "",
) -> MALOAuthToken:
    try:
        expires_in = int(payload.get("expires_in", 0))
    except (TypeError, ValueError) as error:
        raise MALOAuthError(
            "MyAnimeList devolvió expires_in inválido."
        ) from error

    if expires_in <= 0:
        raise MALOAuthError(
            "MyAnimeList no devolvió una expiración válida."
        )

    refresh_token = (
        payload.get("refresh_token")
        or previous_refresh_token
    )

    if not refresh_token:
        raise MALOAuthError(
            "MyAnimeList no devolvió un refresh token."
        )

    token, _ = MALOAuthToken.objects.update_or_create(
        pk=TOKEN_PK,
        defaults={
            "access_token": payload["access_token"],
            "refresh_token": refresh_token,
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": (
                timezone.now()
                + timedelta(seconds=expires_in)
            ),
        },
    )

    return token


def exchange_authorization_code(
    *,
    code: str,
    code_verifier: str,
) -> MALOAuthToken:
    data = {
        **_client_credentials(),
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
    }

    redirect_uri = getattr(
        settings,
        "MAL_REDIRECT_URI",
        None,
    )

    if redirect_uri:
        data["redirect_uri"] = redirect_uri

    payload = _post_token(data)

    return _save_token_payload(payload)


@transaction.atomic
def refresh_stored_token() -> MALOAuthToken:
    token = (
        MALOAuthToken.objects
        .select_for_update()
        .filter(pk=TOKEN_PK)
        .first()
    )

    if token is None or not token.refresh_token:
        raise MALOAuthError(
            "No existe un refresh token. "
            "Reconecta MyAnimeList desde el dashboard."
        )

    data = {
        **_client_credentials(),
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
    }

    payload = _post_token(data)

    return _save_token_payload(
        payload,
        previous_refresh_token=token.refresh_token,
    )


def get_valid_access_token(
    *,
    force_refresh: bool = False,
) -> str:
    token = MALOAuthToken.objects.filter(
        pk=TOKEN_PK,
    ).first()

    if token is not None:
        still_valid = (
            token.expires_at
            > timezone.now() + REFRESH_MARGIN
        )

        if still_valid and not force_refresh:
            return token.access_token

        return refresh_stored_token().access_token

    fallback_access_token = getattr(
        settings,
        "MAL_ACCESS_TOKEN",
        None,
    )

    if fallback_access_token and not force_refresh:
        return fallback_access_token

    raise MALOAuthError(
        "MyAnimeList no está conectado. "
        "Usa Connect / Renew MAL en el dashboard."
    )

