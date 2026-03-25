import os
import re
import subprocess

DEFAULT_VERSION = "1.96.0"
VERSION_ENV_VAR = "TIKBOT_VERSION"
SEMVER_TAG_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SEMVER_TAG_MATCH = "v[0-9]*.[0-9]*.[0-9]*"


def _normalize_tag_version(version):
    if not version:
        return None

    match = SEMVER_TAG_PATTERN.fullmatch(version.strip())
    if not match:
        return None

    return ".".join(match.groups())


def _run_git_command(*args):
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    output = result.stdout.strip()
    return output or None


def _get_version_from_git():
    tagged_version = _normalize_tag_version(
        _run_git_command("describe", "--tags", "--exact-match", "--match", SEMVER_TAG_MATCH)
    )
    if tagged_version:
        return tagged_version

    commit_count = _run_git_command("rev-list", "--count", "HEAD")
    if commit_count and commit_count.isdigit():
        return f"1.{int(commit_count)}.0"

    latest_tag = _normalize_tag_version(
        _run_git_command("describe", "--tags", "--abbrev=0", "--match", SEMVER_TAG_MATCH)
    )
    if latest_tag:
        return latest_tag

    return None


def get_version():
    env_version = (os.getenv(VERSION_ENV_VAR) or "").strip()
    if env_version:
        return env_version[1:] if env_version.lower().startswith("v") else env_version

    git_version = _get_version_from_git()
    if git_version:
        return git_version

    return DEFAULT_VERSION


def get_version_label():
    return f"v{get_version()}"


def get_status_text():
    return f"tik-tok channels | {get_version_label()}"
