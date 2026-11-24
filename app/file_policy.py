"""Shared, name-based credential exclusions for context and direct workspace tools.

This is a conservative filename policy, not content scanning or complete DLP.
"""
from pathlib import PurePath

SECRET_NAMES = {".env", ".env.local", ".env.production", ".env.development", "id_rsa", "id_ed25519",
                "id_ecdsa", "id_dsa", "credentials.json", "credentials.yaml", "credentials.yml",
                "credentials.toml", "secrets.json", "secrets.yaml", "secrets.yml", "secrets.toml",
                ".netrc", ".npmrc", ".pypirc", ".pgpass", ".htpasswd", "kubeconfig"}
# A key material file is a secret whatever its name; these never enter a prompt or a search result.
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdbx", ".jks", ".keystore", ".ppk"}

def sensitive_component(name: str) -> bool:
    folded = name.casefold()
    return (folded in SECRET_NAMES or folded.startswith(".env")
            or folded == "personal-codex-diagnostic.txt"
            or PurePath(folded).suffix in SECRET_SUFFIXES)
