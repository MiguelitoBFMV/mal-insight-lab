import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from mal_data.services.mal_oauth import (
    MALOAuthError,
    build_authorization_url,
    exchange_authorization_code,
    generate_code_verifier,
)


SESSION_STATE_KEY = "mal_oauth_state"
SESSION_VERIFIER_KEY = "mal_oauth_code_verifier"


@login_required
@require_GET
def mal_oauth_connect(request):
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()

    request.session[SESSION_STATE_KEY] = state
    request.session[SESSION_VERIFIER_KEY] = code_verifier

    authorization_url = build_authorization_url(
        state=state,
        code_verifier=code_verifier,
    )

    return redirect(authorization_url)


@login_required
@require_GET
def mal_oauth_callback(request):
    oauth_error = request.GET.get("error")

    if oauth_error:
        description = (
            request.GET.get("error_description")
            or oauth_error
        )

        messages.error(
            request,
            f"MyAnimeList rechazó la autorización: {description}",
        )

        return redirect("mal_insights:dashboard")

    received_state = request.GET.get("state")

    expected_state = request.session.pop(
        SESSION_STATE_KEY,
        None,
    )

    code_verifier = request.session.pop(
        SESSION_VERIFIER_KEY,
        None,
    )

    authorization_code = request.GET.get("code")

    if not expected_state or received_state != expected_state:
        messages.error(
            request,
            "La conexión con MyAnimeList falló "
            "por un state inválido.",
        )

        return redirect("mal_insights:dashboard")

    if not authorization_code or not code_verifier:
        messages.error(
            request,
            "MyAnimeList no devolvió los datos "
            "necesarios para completar OAuth.",
        )

        return redirect("mal_insights:dashboard")

    try:
        exchange_authorization_code(
            code=authorization_code,
            code_verifier=code_verifier,
        )

    except MALOAuthError as error:
        messages.error(
            request,
            f"No se pudo conectar MyAnimeList: {error}",
        )

    else:
        messages.success(
            request,
            "MyAnimeList conectado. "
            "La renovación automática quedó activa.",
        )

    return redirect("mal_insights:dashboard")

