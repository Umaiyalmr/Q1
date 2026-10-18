
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


# --------------------------------------------------
# Assigned configuration
# --------------------------------------------------

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

CONFIG_FILE = Path("config.development.yaml")
ENV_FILE = Path(".env")

app = FastAPI(title="Effective Configuration API")


# --------------------------------------------------
# Type coercion
# --------------------------------------------------

def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    value = str(value).strip().lower()

    if value in ("true", "1", "yes", "on"):
        return True

    if value in ("false", "0", "no", "off"):
        return False

    raise ValueError(f"Invalid boolean value: {value}")


def coerce_value(key: str, value: Any) -> Any:
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        return to_bool(value)

    # log_level, api_key, and all other keys are strings.
    return str(value)


# --------------------------------------------------
# Load and merge configuration layers
# Precedence: defaults < YAML < .env < OS env
# --------------------------------------------------

def load_config() -> dict:
    config = DEFAULTS.copy()

    # Layer 2: config.development.yaml
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}

        if not isinstance(yaml_config, dict):
            raise ValueError("YAML configuration must be a mapping")

        for key, value in yaml_config.items():
            config[key] = coerce_value(key, value)

    # Layer 3: .env
    # Load without overriding existing OS environment variables.
    load_dotenv(dotenv_path=ENV_FILE, override=False)

    env_config = {}

    # Special alias: NUM_WORKERS maps to workers.
    if "NUM_WORKERS" in os.environ:
        env_config["workers"] = os.environ["NUM_WORKERS"]

    # APP_* variables map to config keys.
    for env_key, value in os.environ.items():
        if env_key.startswith("APP_"):
            key = env_key[4:].lower()
            env_config[key] = value

    # Apply .env values below OS environment values.
    # dotenv values are read separately so precedence stays correct.
    if ENV_FILE.exists():
        from dotenv import dotenv_values
        file_values = dotenv_values(ENV_FILE)

        if "NUM_WORKERS" in file_values:
            config["workers"] = coerce_value(
                "workers", file_values["NUM_WORKERS"]
            )

        for env_key, value in file_values.items():
            if env_key and env_key.startswith("APP_") and value is not None:
                key = env_key[4:].lower()
                config[key] = coerce_value(key, value)

    # Apply OS environment values at higher precedence than .env.
    for key, value in env_config.items():
        config[key] = coerce_value(key, value)

    return config


# --------------------------------------------------
# CLI/query overrides
# --------------------------------------------------

def effective_config(set_values: list[str] | None) -> dict:
    config = load_config()

    # Each set parameter is key=value; CLI overrides have highest priority.
    for item in set_values or []:
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        key = key.strip()

        if not key:
            continue

        config[key] = coerce_value(key, value)

    # Never reveal the actual API key.
    if "api_key" in config:
        config["api_key"] = "****"

    return config


@app.get("/effective-config")
def get_effective_config(
    set_values: list[str] | None = Query(default=None, alias="set"),
):
    return effective_config(set_values)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
