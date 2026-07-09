from github import Github
from github import Auth
from rich.tree import Tree
from rich import print
from rich.console import Console
import requests
import questionary
import time
import webbrowser
import os
import re
from collections import defaultdict
from pathlib import Path
from github import GithubException
import tiktoken

# ------- AUTH ---------

CLIENT_ID = "Ov23liBEXGn0p2seW9HG"

def device_flow_login():
    resp = requests.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={"client_id": CLIENT_ID, "scope": "repo read:user"}
    )
    data = resp.json()
    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data["verification_uri"]
    interval = data.get("interval", 5)

    print(f"\nGo to: {verification_uri}")
    print(f"Enter this code: {user_code}\n")
    webbrowser.open(verification_uri)

    while True:
        time.sleep(interval)
        token_resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            }
        )
        token_data = token_resp.json()

        if "access_token" in token_data:
            return token_data["access_token"]
        elif token_data.get("error") == "authorization_pending":
            continue
        elif token_data.get("error") == "slow_down":
            interval += 5
        else:
            raise Exception(f"Auth failed: {token_data}")

TOKEN_PATH = Path.home() / ".github_repo_summarizer" / "token"

def get_token():
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    token = device_flow_login()
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token)
    os.chmod(TOKEN_PATH, 0o600)
    return token


def get_auth_user(max_retries=1):
    token = get_token()
    auth = Auth.Token(token)
    g = Github(auth=auth)

    try:
        user = g.get_user()
        user.login
        return g, user
    except GithubException as e:
        if max_retries > 0 and e.status in (401, 403):
            ui_console.print("[yellow]Cached token invalid or revoked - re authenticating..[/yellow]")
            if TOKEN_PATH.exists():
                TOKEN_PATH.unlink()
            return get_auth_user(max_retries - 1)
        raise


global g, user, repos


record_console = Console(record=True)
ui_console = Console()


IGNORE_DIRS = {
    ".git", ".github", ".svn", ".hg",
    "node_modules", "dist", "build", ".next", ".nuxt", ".turbo",
    "coverage", ".parcel-cache", ".cache", "out",
    "__pycache__", ".venv", "venv", "env", ".pytest_cache",
    ".mypy_cache", ".tox", "*.egg-info", "site-packages",
    "x64", "x86", "Debug", "Release", "ipch", "obj", "bin",
    "cmake-build-debug", "cmake-build-release", ".vs",
    "target", ".gradle", "gradle", ".idea", "out",
    "bin", "obj", "packages", ".vs",
    "target",
    "vendor",
    ".bundle", "vendor/bundle",
    "vendor",
    ".gradle", "captures", ".externalNativeBuild", ".cxx",
    "DerivedData", "Pods", "*.xcworkspace", "*.xcodeproj",
    "Library", "Temp", "Logs", "obj", "Build", "Builds",
    ".vscode", ".idea", ".fleet", ".settings",
    ".terraform",
    ".cache", "tmp", "temp", "logs",
    "android", "ios", "linux", "windows", "macos", "web",
    "dist-info", "egg-info", "site-packages", "__MACOSX",
}

IGNORE_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    ".gitignore", ".gitattributes", ".dockerignore",
    ".DS_Store", "Thumbs.db", "desktop.ini",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "poetry.lock", "Gemfile.lock", "composer.lock",
    ".npmrc", ".yarnrc",
}

IGNORE_EXTENSIONS = {
    ".obj", ".o", ".pdb", ".exe", ".dll", ".so", ".dylib",
    ".ilk", ".exp", ".lib", ".a", ".class", ".pyc", ".pyo",
    ".log", ".tlog", ".vsidx", ".suo", ".user",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".ico",
    ".mp3", ".wav", ".mp4", ".mov", ".avi", ".mkv",
    ".ttf", ".woff", ".woff2", ".otf", ".eot",
    ".pdf", ".psd", ".ai", ".sketch",
    ".apk", ".aab", ".ipa", ".dSYM",
    ".db", ".sqlite", ".sqlite3",
    ".jar", ".war", ".ear",
    ".map", ".min.js", ".min.css",
    ".css", ".svg", ".meta", ".md",
    ".pyd", ".tcl",
}


IGNORE_DIR_SUBSTRINGS = ("dist-info", ".egg-info")

# ---------- collapsing config ----------

# Directories with more files than this get pattern-collapsed instead of
# listed one-by-one. Keeps huge asset/locale/exercise dumps (e.g. monkeytype's
# 100+ language JSON files, or czech.json/czech_10k.json/czech_1k.json...)
# from silently blowing up the token count.
COLLAPSE_THRESHOLD = 6

# If, after family-grouping, a directory still has more loose files than this
# (e.g. 100+ language files where each family only has 2-3 variants), fall
# back to a coarser extension-only collapse for whatever's left over.
DIR_COLLAPSE_THRESHOLD = 15

# Max lines emitted per repo before we truncate with a summary line.
MAX_LINES_PER_REPO = 80

DEFAULT_MODEL = "qwen2.5:3b"   # better default: fewer hallucinated summaries
FAST_MODEL = "qwen2.5:0.5b"    # opt-in via --fast for speed on huge accounts


def should_ignore(item):
    name = item.name

    if name in IGNORE_DIRS:
        return True

    if name in IGNORE_FILES:
        return True

    if any(sub in name for sub in IGNORE_DIR_SUBSTRINGS):
        return True

    for ext in IGNORE_EXTENSIONS:
        if name.endswith(ext):
            return True

    return False


def count_tokens(text, model="gpt-4"):
    enc = tiktoken.encoding_for_model(model) if "gpt" in model else tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def init_auth():
    global g, user, repos
    g, user = get_auth_user()
    repos = user.get_repos()
    return True


def _stem_pattern(filename):
    """
    Reduce a filename to a rough 'family' key so that things like
    czech.json / czech_10k.json / czech_1k.json, or p1.java...p19.java,
    or click1.wav...click4.wav, collapse into one group.
    """
    name, ext = os.path.splitext(filename)
    # strip trailing digits and common size/variant suffixes (_10k, _1k, -v2, etc.)
    stem = re.sub(r'[\d]+$', '', name)
    stem = re.sub(r'[_\-](?:\d+k|\d+|v\d+)$', '', stem, flags=re.IGNORECASE)
    stem = stem.rstrip('_- ')
    return (stem.lower() or name.lower(), ext)


def _collapse_files(file_items):
    groups = defaultdict(list)
    for item in file_items:
        key = _stem_pattern(item.name)
        groups[key].append(item.name)

    collapsed_lines = []
    leftover_names = []

    for (stem, ext), names in groups.items():
        if len(names) >= COLLAPSE_THRESHOLD:
            example = sorted(names)[0]
            collapsed_lines.append(f"{stem}*{ext} ({len(names)} files, e.g. {example})")
        else:
            leftover_names.extend(names)

    if len(leftover_names) > DIR_COLLAPSE_THRESHOLD:
        by_ext = defaultdict(list)
        for name in leftover_names:
            _, ext = os.path.splitext(name)
            by_ext[ext or "(no ext)"].append(name)

        for ext, names in by_ext.items():
            if len(names) >= COLLAPSE_THRESHOLD:
                example = sorted(names)[0]
                collapsed_lines.append(f"*{ext} ({len(names)} files, e.g. {example})")
            else:
                collapsed_lines.extend(sorted(names))
    else:
        collapsed_lines.extend(leftover_names)

    return sorted(collapsed_lines)


def add(repo, contents, indent=0, max_depth=2):
    lines = []
    if indent > max_depth:
        return lines

    items = [item for item in list(contents) if not should_ignore(item)]
    dirs = [item for item in items if item.type == "dir"]
    files = [item for item in items if item.type != "dir"]

    for item in dirs:
        lines.append(" " * indent + item.name)
        if indent < max_depth:
            try:
                sub = repo.get_contents(item.path)
                lines.extend(add(repo, sub, indent + 1, max_depth))
            except Exception:
                pass

    for line in _collapse_files(files):
        lines.append(" " * indent + line)

    if len(lines) > MAX_LINES_PER_REPO:
        shown = lines[:MAX_LINES_PER_REPO]
        remaining = len(lines) - MAX_LINES_PER_REPO
        shown.append(f"... ({remaining} more items truncated)")
        return shown

    return lines


def summary(repo_name, tree_text, desc=None, model=DEFAULT_MODEL, retries=2, timeout=30):
    context = desc or tree_text[:2000]
    prompt = (
        f"Repo name: {repo_name}\n"
        f"Description/structure: {context}\n\n"
        "Write ONE short line (max 15 words) summarizing what this project does. "
        "No preamble, no quotes, just the sentence."
    )

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 40}
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "").strip()
            if text:
                return text
            last_error = "empty response from model"
        except requests.exceptions.ConnectionError:
            last_error = "Ollama isn't running (couldn't reach localhost:11434)"
            break
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))

    ui_console.print(f"[red]summary failed for {repo_name}: {last_error}[/red]")
    return f"[summary unavailable: {last_error}]"


def full(txtFile, max_depth=2, fast=False, model=None):
    chosen_model = model or (FAST_MODEL if fast else DEFAULT_MODEL)
    with open(txtFile, "w", encoding="utf-8") as f:
        for x in repos:
            with ui_console.status(f"[bold green]Generating Summary for {x.name}..."):
                try:
                    lines = add(x, x.get_contents(""), max_depth=max_depth)
                    output = "\n".join(lines)
                except Exception as e:
                    ui_console.print(f"[red]skipped {x.name}: {e}[/red]")
                    continue

            summ = summary(x.name, output, x.description, model=chosen_model)
            f.write(f"Repo Name: {x.name}\n")
            f.write(output)
            f.write("\n")
            f.write(f"Summary: {summ}")
            f.write("\n\n")

            ui_console.print("[green]Completed[/green]")

    print("File created")

    g.close()


def token_by_repo(txt):
    enc = tiktoken.get_encoding("cl100k_base")

    with open(txt, encoding="utf-8") as f:
        content = f.read()

    chunks = content.split("Repo Name:")
    for c in chunks[1:]:
        name = c.strip().split("\n")[0]
        tokens = len(enc.encode(c))
        print(f"{name}: {tokens} tokens")


def user_repos(textFile, max_depth=2, fast=False, model=None):
    chosen_model = model or (FAST_MODEL if fast else DEFAULT_MODEL)
    choices = questionary.checkbox(
        "Select which repoistories you want to add",
        choices=[x.name for x in repos]
    ).ask()
    print(choices)
    for x in repos:
        if x.name in choices:
            with open(textFile, "a", encoding="utf-8") as f:
                with ui_console.status(f"[bold green]Generating Summary for {x.name}"):
                    try:
                        lines = add(x, x.get_contents(""), max_depth=max_depth)
                        output = "\n".join(lines)
                    except Exception as e:
                        ui_console.print(f"[red]skipped {x.name}: {e}[/red]")
                        continue

                summ = summary(x.name, output, x.description, model=chosen_model)
                f.write(f"Repo Name: {x.name}\n")
                f.write(output)
                f.write("\n")
                f.write(f"Summary: {summ}")
                f.write("\n\n")
                ui_console.print("[green]Completed[/green]")

    print("Done")