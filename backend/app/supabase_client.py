import inspect

import httpx

from .config import get_settings


def _patch_httpx_proxy_kw() -> None:
    if "proxy" in inspect.signature(httpx.Client).parameters:
        return

    class PatchedClient(httpx.Client):
        def __init__(self, *args, proxy=None, **kwargs):
            if proxy is not None and "proxies" not in kwargs:
                kwargs["proxies"] = proxy
            super().__init__(*args, **kwargs)

    httpx.Client = PatchedClient  # type: ignore[assignment]


_patch_httpx_proxy_kw()


from supabase import create_client, Client


def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
