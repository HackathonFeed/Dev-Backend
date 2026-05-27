import httpx

from app.core.config import get_settings


class GoogleAuthError(ValueError):
    pass


def _is_email_verified(value) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def _normalize_google_profile(profile: dict) -> dict:
    if not _is_email_verified(profile.get("email_verified")):
        raise GoogleAuthError("Google account email is not verified")

    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise GoogleAuthError("Google account did not return an email address")

    name = (profile.get("name") or profile.get("given_name") or email.split("@")[0]).strip()
    if len(name) < 2:
        name = email.split("@")[0][:255] or "Hacker"

    return {
        "email": email,
        "name": name[:255],
        "picture": profile.get("picture"),
        "sub": profile.get("sub"),
    }


def _validate_audience(tokeninfo: dict, client_id: str) -> None:
    audience = tokeninfo.get("aud") or tokeninfo.get("azp")
    if audience and audience != client_id:
        raise GoogleAuthError("Google sign-in token was issued for another app")


async def verify_google_id_token(token: str) -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleAuthError("Google sign-in is not configured on the server")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": token},
            )
            if response.status_code != 200:
                raise GoogleAuthError("Invalid or expired Google sign-in token")

            tokeninfo = response.json()
            _validate_audience(tokeninfo, settings.google_client_id)
            return _normalize_google_profile(tokeninfo)
    except httpx.HTTPError as exc:
        raise GoogleAuthError("Could not verify Google sign-in token") from exc


async def verify_google_access_token(token: str) -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleAuthError("Google sign-in is not configured on the server")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            tokeninfo_response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": token},
            )
            if tokeninfo_response.status_code != 200:
                raise GoogleAuthError("Invalid or expired Google sign-in token")

            tokeninfo = tokeninfo_response.json()
            _validate_audience(tokeninfo, settings.google_client_id)

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            if userinfo_response.status_code != 200:
                raise GoogleAuthError("Could not fetch Google account profile")

            return _normalize_google_profile(userinfo_response.json())
    except httpx.HTTPError as exc:
        raise GoogleAuthError("Could not verify Google sign-in token") from exc
