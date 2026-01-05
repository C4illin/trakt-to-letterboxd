"""Trakt OAuth authentication module."""

from trakt import core
from trakt.api import TokenAuth
from trakt.auth import config_factory, device_auth

from . import console

core.AUTH_METHOD = core.DEVICE_AUTH


def create_trakt_config(account, with_tokens: bool = True):
    """Create a fresh trakt config object."""
    config = config_factory()
    config.CLIENT_ID = account.trakt_client_id
    config.CLIENT_SECRET = account.trakt_client_secret
    
    if with_tokens:
        config.OAUTH_TOKEN = account.internal.trakt_oauth.token
        config.OAUTH_REFRESH = account.internal.trakt_oauth.refresh
        config.OAUTH_EXPIRES_AT = account.internal.trakt_oauth.expires_at
    else:
        config.OAUTH_TOKEN = None
        config.OAUTH_REFRESH = None
        config.OAUTH_EXPIRES_AT = None
    
    return config


def clear_invalid_tokens(config, account):
    """Clear invalid tokens from config and save."""
    console.print("Clearing invalid OAuth tokens from config...", style="yellow")
    account.internal.trakt_oauth.token = None
    account.internal.trakt_oauth.refresh = None
    account.internal.trakt_oauth.expires_at = None
    config.save()


def save_tokens(config, account, trakt_config):
    """Save OAuth tokens from trakt_config to account and persist to file."""
    account.internal.trakt_oauth.token = trakt_config.OAUTH_TOKEN
    account.internal.trakt_oauth.refresh = trakt_config.OAUTH_REFRESH
    account.internal.trakt_oauth.expires_at = trakt_config.OAUTH_EXPIRES_AT
    config.save()


def validate_existing_tokens(config, account, trakt_config) -> bool:
    """Try to validate and refresh existing OAuth tokens."""
    console.print("Validating existing OAuth tokens...", style="blue")
    
    try:
        client = core.api()
        auth: TokenAuth = client.auth
        auth.config = trakt_config
        _, token = auth.get_token()

        if not token:
            console.print("Token validation returned None.", style="yellow")
            return False

        # Update config with potentially refreshed tokens
        save_tokens(config, account, trakt_config)
        
        # Test the token with a real API call
        # get_token() may return the old token even if refresh failed
        console.print("Testing token with API call...", style="blue")
        test_response = client.get('users/me')
        
        if test_response:
            console.print("OAuth tokens validated successfully!", style="green")
            return True
        
        console.print("API test returned empty response.", style="yellow")
        return False
        
    except Exception as e:
        console.print(f"Token validation failed: {e}", style="yellow")
        return False


def run_device_auth(config, account) -> bool:
    """Run device authentication flow.
    
    Displays a code for the user to enter at https://trakt.tv/activate.
    The library handles polling internally until user validates or timeout.
    """
    trakt_config = create_trakt_config(account, with_tokens=False)
    
    console.print(
        "\n[bold cyan]Trakt Device Authentication[/bold cyan]\n"
        "Visit [link=https://trakt.tv/activate]https://trakt.tv/activate[/link] "
        "and enter the code shown below.\n",
        style="cyan",
    )
    
    try:
        device_auth(config=trakt_config)
        save_tokens(config, account, trakt_config)
        console.print("Signed in to Trakt successfully!", style="bold green")
        return True
    except Exception as e:
        console.print(f"Authentication failed: {e}", style="bold red")
        return False


def trakt_init(config, account) -> bool:
    """Initialize Trakt authentication.
    
    Attempts to use existing tokens, refreshing if needed.
    Falls back to device authentication if tokens are invalid.
    """
    has_existing_tokens = account.internal.trakt_oauth.token is not None

    if has_existing_tokens:
        trakt_config = create_trakt_config(account, with_tokens=True)
        
        if validate_existing_tokens(config, account, trakt_config):
            return True
        
        clear_invalid_tokens(config, account)
        console.print("Tokens invalid. Starting device authentication...", style="yellow")

    return run_device_auth(config, account)
