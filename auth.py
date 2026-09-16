import os
import re
import logging
from flask import session

logger = logging.getLogger(__name__)

SCOPES = ["User.Read"]

def get_msal_app():
    """Initializes and returns an MSAL ConfidentialClientApplication."""
    import msal

    client_id = os.environ.get("ENTRA_CLIENT_ID")
    client_secret = os.environ.get("ENTRA_CLIENT_SECRET")
    tenant_id = os.environ.get("ENTRA_TENANT_ID")

    if not all([client_id, client_secret, tenant_id]):
        logger.warning("Entra ID SSO environment variables are not fully configured.")
        return None

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

def initiate_auth_flow(redirect_uri, state=None):
    """Initiates MSAL auth code flow and returns flow dictionary."""
    msal_app = get_msal_app()
    if not msal_app:
        return None

    return msal_app.initiate_auth_code_flow(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state
    )

def acquire_token_by_flow(auth_flow, auth_response):
    """Completes auth code flow and acquires token."""
    msal_app = get_msal_app()
    if not msal_app:
        return None

    return msal_app.acquire_token_by_auth_code_flow(auth_flow, auth_response)

# Legacy alias
build_auth_url = initiate_auth_flow
acquire_token_by_auth_code = acquire_token_by_flow

def extract_user_from_claims(claims):
    """
    Parses claims from Entra ID token and determines student ID and role.
    Returns dict: { 'id': 'W0123456', 'email': '...', 'name': '...', 'role': 'student'|'instructor' }
    """
    email = claims.get("preferred_username") or claims.get("email") or claims.get("upn", "")
    name = claims.get("name") or email.split("@")[0]

    # Check admin/instructor status
    admin_emails = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
    is_admin = email.lower() in admin_emails

    # Extract W-number (e.g. W0123456 or w0123456)
    student_id = None
    match = re.search(r'(w\d{6,8})', email, re.IGNORECASE)
    if match:
        student_id = match.group(1).upper()
    else:
        # Fallback: username part of email or user object ID
        student_id = email.split("@")[0].upper() if "@" in email else claims.get("oid", "USER")

    return {
        "id": student_id,
        "email": email,
        "name": name,
        "role": "instructor" if is_admin else "student"
    }
