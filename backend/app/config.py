import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    supabase_inputs_bucket: str = "inputs"
    supabase_outputs_bucket: str = "outputs"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origin: str = "*"


_DEF = ""


def get_settings() -> Settings:
    url = os.getenv("SUPABASE_URL", _DEF).strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", _DEF).strip()

    if not url or not key:
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        raise RuntimeError(
            "Missing required env vars: " + ", ".join(missing)
        )

    return Settings(
        supabase_url=url,
        supabase_service_role_key=key,
        supabase_inputs_bucket=os.getenv("SUPABASE_INPUTS_BUCKET", "inputs"),
        supabase_outputs_bucket=os.getenv("SUPABASE_OUTPUTS_BUCKET", "outputs"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        cors_origin=os.getenv("CORS_ORIGIN", "*")
    )
