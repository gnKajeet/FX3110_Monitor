"""
Configuration loader with YAML + env var override support.

Priority (highest to lowest):
  1. Environment variables (for Docker/CI overrides)
  2. config.yaml (primary config)
  3. .env file (legacy fallback)
  4. Hardcoded defaults
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Legacy .env support
load_dotenv()

DEFAULT_CONFIG_PATHS = [
    Path("config.yaml"),
    Path("config.yml"),
    Path("/app/config.yaml"),
]


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML config with env var overrides."""
    # Find config file
    if config_path:
        paths = [Path(config_path)]
    else:
        env_path = os.getenv("CONFIG_FILE")
        paths = [Path(env_path)] if env_path else DEFAULT_CONFIG_PATHS

    config: Dict[str, Any] = {}
    for p in paths:
        if p.exists():
            try:
                import yaml
                with open(p) as f:
                    config = yaml.safe_load(f) or {}
            except ImportError:
                pass
            break

    # Apply env var overrides for backward compatibility
    config = _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: Dict) -> Dict:
    """Map legacy env vars into YAML structure."""
    # Top-level overrides
    if os.getenv("DEVICE_TYPE"):
        config["device_type"] = os.getenv("DEVICE_TYPE").strip().lower()

    # Network section
    net = config.setdefault("network", {})
    if os.getenv("BIND_INTERFACE"):
        net["bind_interface"] = os.getenv("BIND_INTERFACE")
    if os.getenv("DEST"):
        net["ping_target"] = os.getenv("DEST")
    if os.getenv("PUBLIC_IP_REFRESH_SECONDS"):
        net["public_ip_refresh"] = int(os.getenv("PUBLIC_IP_REFRESH_SECONDS"))

    # Monitor section
    mon = config.setdefault("monitor", {})
    if os.getenv("MAIN_LOOP_INTERVAL"):
        mon["interval"] = int(os.getenv("MAIN_LOOP_INTERVAL"))

    # Device sections
    devices = config.setdefault("devices", {})

    # FX3110
    if os.getenv("DEVICE_BASE"):
        fx3110 = devices.setdefault("fx3110", {})
        fx3110["base_url"] = os.getenv("DEVICE_BASE")

    # RUTM50
    rutm50_host = os.getenv("RUTM50_SSH_HOST")
    if rutm50_host:
        rutm50 = devices.setdefault("rutm50", {})
        ssh = rutm50.setdefault("ssh", {})
        ssh["host"] = rutm50_host
        if os.getenv("RUTM50_SSH_USER"):
            ssh["user"] = os.getenv("RUTM50_SSH_USER")
        if os.getenv("RUTM50_SSH_PORT"):
            ssh["port"] = int(os.getenv("RUTM50_SSH_PORT"))
        if os.getenv("RUTM50_SSH_PASSWORD"):
            ssh["password"] = os.getenv("RUTM50_SSH_PASSWORD")
        if os.getenv("RUTM50_SSH_KEY"):
            ssh["key"] = os.getenv("RUTM50_SSH_KEY")
        if os.getenv("RUTM50_SSH_STRICT"):
            ssh["strict_host_key"] = os.getenv("RUTM50_SSH_STRICT")
        if os.getenv("RUTM50_SSH_TIMEOUT"):
            ssh["timeout"] = float(os.getenv("RUTM50_SSH_TIMEOUT"))
        if os.getenv("RUTM50_CELL_IFACE"):
            rutm50["cell_interface"] = os.getenv("RUTM50_CELL_IFACE")

        script = rutm50.setdefault("collector_script", {})
        if os.getenv("RUTM50_USE_COLLECTOR_SCRIPT"):
            script["enabled"] = os.getenv("RUTM50_USE_COLLECTOR_SCRIPT", "").lower() in ("true", "1", "yes")
        if os.getenv("RUTM50_COLLECTOR_SCRIPT_PATH"):
            script["path"] = os.getenv("RUTM50_COLLECTOR_SCRIPT_PATH")

    # FX4200 (env var overrides for Docker)
    if os.getenv("FX4200_BASE_URL") or os.getenv("FX4200_PASSWORD"):
        fx4200 = devices.setdefault("fx4200", {})
        if os.getenv("FX4200_BASE_URL"):
            fx4200["base_url"] = os.getenv("FX4200_BASE_URL")
        if os.getenv("FX4200_PASSWORD"):
            fx4200["password"] = os.getenv("FX4200_PASSWORD")
        if os.getenv("FX4200_VERIFY_SSL"):
            fx4200["verify_ssl"] = os.getenv("FX4200_VERIFY_SSL", "").lower() in ("true", "1", "yes")

    return config


def get_device_config(config: Dict) -> Dict:
    """Extract the active device's config section."""
    device_type = config.get("device_type", "fx3110")
    devices = config.get("devices", {})
    return devices.get(device_type, {})
