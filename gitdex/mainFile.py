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


def get_auth_user(max_retries = 1):
    token = get_token()
    auth = Auth.Token(token)
    g = Github(auth=auth)

    try:
        user = g.get_user()
        user.login
        return g,user
    except GithubException as e:
        if max_retries > 0 and e.status in (401, 403):
            ui_console.print("[yellow]Cached token invalid or revoked - re authenticating..[/yellow]")
            if TOKEN_PATH.exists():
                TOKEN_PATH.unlink()
            return get_auth_user(max_retries-1)
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
    "android","ios","linux","windows","macos","web"
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
    ".css",".svg",".meta",".md"
}


def should_ignore(item):
    name = item.name

    if name in IGNORE_DIRS:
        return True

    if name in IGNORE_FILES:
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

def add(repo, contents, indent = 0, max_depth=2):
    lines = []
    if indent>max_depth:
        return lines
    for item in list(contents):
        if should_ignore(item):
            continue
        lines.append(" " * indent + item.name)
        if item.type == "dir" and indent < max_depth:
            try:
                sub = repo.get_contents(item.path)
                lines.extend(add(repo, sub, indent+1, max_depth))
            except Exception:
                pass

    return lines


def summary(repo_name, tree_text, desc = None):
    context = desc or tree_text[:2000]
    prompt = (
        f"Repo name: {repo_name}\n"
        f"Description/structure: {context}\n\n"
        "Write ONE short line (max 15 words) summarizing what this project does. "
        "No preamble, no quotes, just the sentence."
    )
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen2.5:0.5b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 40}
        }
    )
    return resp.json()["response"].strip()


def full(txtFile):
    with open(txtFile, "w", encoding = "utf-8") as f:
        for x in repos:
            with ui_console.status(f"[bold green]Generating Summary for {x.name}..."):
                try:
                    lines = add(x, x.get_contents(""))
                    output = "\n".join(lines)

                    # someTree = add(x)
                except Exception as e:
                    ui_console.print(f"[red]skipped {x.name}: {e}[/red]")
                    continue

            # record_console.print(someTree)
            # output = record_console.export_text(clear=True)
            summ = summary(x.name, output, x.description)
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

def user_repos(textFile):
    choices = questionary.checkbox(
        "Select which repoistories you want to add",
        choices=[x.name for x in repos]
    ).ask()
    print(choices)
    for x in repos:
        if x.name in choices:
            with open(textFile, "a", encoding = "utf-8") as f:
                with ui_console.status(f"[bold green]Generating Summary for {x.name}"):
                    try:
                        lines = add(x, x.get_contents(""))
                        output = "\n".join(lines)
                    except Exception as e:
                        ui_console.print(f"[red]skipped {x.name}: {e}[/red]")
                        continue
                
                summ = summary(x.name, output, x.description)
                f.write(f"Repo Name: {x.name}\n")
                f.write(output)
                f.write("\n")
                f.write(f"Summary: {summ}")
                f.write("\n\n")
                ui_console.print("[green]Completed[/green]")

    print("Done")

