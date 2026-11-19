"""Instagram ZIP archive parser.

Handles multiple Instagram export formats:
- JSON format (preferred): followers_and_following/followers_*.json, following.json
- HTML format: detected and rejected with a helpful message
- Various folder structures in the ZIP
"""

import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from config import MAX_ZIP_SIZE_BYTES, TEMP_DIR


class ParseError(Exception):
    """Raised when ZIP cannot be parsed."""
    pass


def _extract_username(entry) -> str | None:
    """Extract username from an entry across various Instagram export formats."""
    if isinstance(entry, str):
        val = entry.strip().lstrip("@").lower()
        return val if val else None

    if not isinstance(entry, dict):
        return None

    # 1. string_list_data can have value and href
    for sld in entry.get("string_list_data", []):
        if not isinstance(sld, dict):
            continue
        # Direct value
        val = sld.get("value")
        if val and str(val).strip():
            return str(val).strip().lstrip("@").lower()

        # Extract username from href: https://www.instagram.com/_u/username or https://www.instagram.com/username/
        href = sld.get("href", "")
        if href:
            m = re.search(r"instagram\.com/(?:_u/)?([^/?#]+)", href)
            if m:
                u = m.group(1).strip().lstrip("@").lower()
                if u and u not in ("p", "explore", "reels", "stories", "accounts", "direct"):
                    return u

    # 2. Instagram 'following.json' puts username in 'title'
    title = entry.get("title")
    if title and isinstance(title, str) and title.strip():
        # Title can be just username or sometimes contains text
        clean = title.strip().lstrip("@").lower()
        if clean and not clean.startswith("http"):
            return clean

    # 3. Direct keys
    for k in ("value", "username", "name"):
        v = entry.get(k)
        if v and isinstance(v, str) and v.strip():
            return v.strip().lstrip("@").lower()

    return None


def parse_instagram_json(file_paths: list[str]) -> list[str]:
    """
    Parse Instagram JSON files and extract usernames.
    Supports all Instagram JSON export versions (title, string_list_data, href, etc.).
    """
    usernames = []

    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue

        if isinstance(data, list):
            for entry in data:
                u = _extract_username(entry)
                if u:
                    usernames.append(u)

        elif isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, list):
                    for entry in val:
                        u = _extract_username(entry)
                        if u:
                            usernames.append(u)
                elif isinstance(val, dict):
                    u = _extract_username(val)
                    if u:
                        usernames.append(u)

    # Return unique while preserving order
    return list(dict.fromkeys(usernames))


def parse_instagram_html(file_paths: list[str]) -> list[str]:
    """
    Parse Instagram HTML files and extract usernames.
    Extracts profile links from <a href="https://www.instagram.com/username">.
    """
    usernames = []
    ignored = {"p", "explore", "reels", "stories", "accounts", "direct", "about", "legal", "help"}

    pattern = re.compile(
        r'href=["\']https?://(?:www\.)?instagram\.com/(?:_u/)?([a-zA-Z0-9._]+)',
        re.IGNORECASE
    )

    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        matches = pattern.findall(content)
        for u in matches:
            clean = u.strip().lstrip("@").lower()
            if clean and clean not in ignored:
                usernames.append(clean)

    return list(dict.fromkeys(usernames))


def parse_instagram_files(file_paths: list[str]) -> list[str]:
    """Parse a mix of JSON and HTML files."""
    json_files = [fp for fp in file_paths if fp.lower().endswith(".json")]
    html_files = [fp for fp in file_paths if fp.lower().endswith(".html")]

    usernames = []
    if json_files:
        usernames.extend(parse_instagram_json(json_files))
    if html_files:
        usernames.extend(parse_instagram_html(html_files))

    return list(dict.fromkeys(usernames))


def extract_zip(zip_path: str, user_id: int) -> str:
    """Extract ZIP to a temp directory. Returns the extraction path."""
    extract_dir = os.path.join(TEMP_DIR, str(user_id))
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Security: check for path traversal
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(extract_dir, member))
                if not member_path.startswith(os.path.realpath(extract_dir)):
                    raise ParseError("❌ Архив содержит недопустимые пути файлов.")
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        raise ParseError("❌ Это не ZIP-архив или файл поврежден.")

    return extract_dir


def find_instagram_files(extract_dir: str) -> dict:
    """
    Find followers and following files (JSON or HTML) in the extracted directory.
    """
    result = {"followers": [], "following": []}

    for root, dirs, files in os.walk(extract_dir):
        for f in files:
            full_path = os.path.join(root, f)
            f_lower = f.lower()

            is_json = f_lower.endswith(".json")
            is_html = f_lower.endswith(".html")

            if not (is_json or is_html):
                continue

            # Match followers files (followers_1.json, followers.html, etc.)
            if f_lower.startswith("followers") and "following" not in f_lower:
                result["followers"].append(full_path)

            # Match following files (following.json, following.html, etc.)
            elif f_lower.startswith("following"):
                result["following"].append(full_path)

    if not result["followers"] and not result["following"]:
        raise ParseError(
            "❌ Не найдены файлы подписчиков/подписок в ZIP.\n\n"
            "Убедись, что при экспорте был выбран пункт "
            "<b>«Подписчики и подписки»</b>."
        )

    return result


def analyze(followers: list[str], following: list[str]) -> dict:
    """Compare followers and following lists, return full analysis."""
    followers_set = set(followers)
    following_set = set(following)

    mutual = followers_set & following_set
    not_following_back = following_set - followers_set  # you follow them, they don't follow you
    not_followed_back = followers_set - following_set   # they follow you, you don't follow them

    return {
        "followers": len(followers_set),
        "following": len(following_set),
        "mutual": len(mutual),
        "not_following_back": len(not_following_back),
        "not_followed_back": len(not_followed_back),
        "mutual_list": sorted(mutual),
        "not_following_back_list": sorted(not_following_back),
        "not_followed_back_list": sorted(not_followed_back),
        "followers_list": sorted(followers_set),
        "following_list": sorted(following_set),
    }


def process_zip(zip_path: str, user_id: int) -> dict:
    """Full pipeline: extract → find files → parse → analyze."""
    extract_dir = extract_zip(zip_path, user_id)
    try:
        files = find_instagram_files(extract_dir)
        followers = parse_instagram_files(files["followers"])
        following = parse_instagram_files(files["following"])

        if not followers and not following:
            raise ParseError(
                "❌ Файлы найдены, но не удалось извлечь ни одного username.\n\n"
                "Возможно, структура архива отличается от стандартной."
            )

        return analyze(followers, following)
    finally:
        # Always cleanup
        shutil.rmtree(extract_dir, ignore_errors=True)


def cleanup_user_files(user_id: int):
    """Remove any temp files for a user."""
    user_dir = os.path.join(TEMP_DIR, str(user_id))
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)
