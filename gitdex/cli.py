import typer
from gitdex.mainFile import *
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing_extensions import Annotated

app = typer.Typer(
    help="gitdex -- scrape your Github repos, generate summaries, and manage tokens.",
    rich_markup_mode="rich"
)
console = Console()


DEPTH_OPTION = Annotated[int, typer.Option(
    "--depth", "-d",
    help="How many directory levels deep to scan per repo (default: 2)."
)]
FAST_OPTION = Annotated[bool, typer.Option(
    "--fast",
    help=f"Use the smaller/faster local model ({FAST_MODEL}) instead of the "
         f"default ({DEFAULT_MODEL}). Quicker on large accounts, lower summary quality."
)]
MODEL_OPTION = Annotated[str, typer.Option(
    "--model", "-m",
    help="Override the Ollama model used for summaries entirely (ignores --fast)."
)]


@app.command()
def complete(
    txt: str,
    depth: DEPTH_OPTION = 2,
    fast: FAST_OPTION = False,
    model: MODEL_OPTION = "",
):
    """Summarize ALL your repos into a single output file."""
    init_auth()
    full(txt, max_depth=depth, fast=fast, model=(model or None))


@app.command(name="count_token")
def countToken(txt: str):
    """Count tokens in a given text file."""
    with open(txt, encoding="utf-8") as f:
        text = f.read()
    print(f"Number of tokens this txt file has: {count_tokens(text)}")


@app.command()
def srepo(
    txt: str,
    depth: DEPTH_OPTION = 2,
    fast: FAST_OPTION = False,
    model: MODEL_OPTION = "",
):
    """Interactively select specific repos to summarize."""
    init_auth()
    user_repos(txt, max_depth=depth, fast=fast, model=(model or None))


@app.command(name="token_by_repo")
def tok_by_rep(txt: str):
    """Break down token count per repo, from an existing summary file."""
    token_by_repo(txt=txt)


@app.command()
def test():
    """Sanity check - confirms gitdex is installed and working."""
    print("Working!")


@app.command()
def help():
    """Show a full, formatted guide of every gitdex command."""
    banner = Text()
    banner.append("        gitdex", style="bold white")
    banner.append("    turn your GitHub repos into a single, compact, LLM-ready summary\n", style="dim")

    console.print(Panel(banner, box=box.ROUNDED, border_style="cyan", padding=(1, 2)))

    table = Table(
        title="Available Commands",
        box=box.SIMPLE_HEAVY,
        show_lines=True,
        header_style="bold magenta",
        title_style="bold cyan",
    )
    table.add_column("Command", style="bold green", no_wrap=True)
    table.add_column("Arguments", style="yellow")
    table.add_column("What it does", style="white")
    table.add_column("Example", style="dim italic")

    rows = [
        (
            "complete",
            "<output.txt> [--depth N] [--fast] [--model NAME]",
            "Authenticates, scrapes every repo you own, and writes a full summary + file tree to a text file.",
            "gitdex complete output.txt --depth 3",
        ),
        (
            "srepo",
            "<output.txt> [--depth N] [--fast] [--model NAME]",
            "Same as complete, but lets you [bold]pick which repos[/bold] to include via checkboxes.",
            "gitdex srepo output.txt --fast",
        ),
        (
            "count_token",
            "<file.txt>",
            "Counts how many tokens a text file contains (using tiktoken, cl100k_base/gpt-4 encoding).",
            "gitdex count_token output.txt",
        ),
        (
            "token_by_repo",
            "<summary.txt>",
            "Takes a summary file (from complete/srepo) and prints a per-repo token breakdown.",
            "gitdex token_by_repo output.txt",
        ),
        (
            "test",
            "—",
            "Quick sanity check that gitdex is installed and runnable.",
            "gitdex test",
        ),
        (
            "help",
            "—",
            "Shows this guide.",
            "gitdex help",
        ),
    ]

    for name, args, desc, example in rows:
        table.add_row(name, args, desc, example)

    console.print(table)

    console.print(
        Panel(
            "[bold]First time?[/bold] Just run any command that needs auth "
            "(e.g. [green]gitdex complete out.txt[/green]) — "
            "it'll open your browser for a one-time GitHub device login "
            "and cache the token locally.\n\n"
            "[bold]Flags:[/bold] [green]--depth[/green] controls how many folder levels are scanned per repo "
            "(higher = more detail, more tokens). [green]--fast[/green] swaps in a smaller local model for "
            "quicker but rougher summaries. [green]--model[/green] lets you point at any Ollama model you have pulled.\n\n"
            "[dim]Run [bold]gitdex <command> --help[/bold] for argument details on any single command.[/dim]",
            box=box.ROUNDED,
            border_style="dim",
            padding=(1, 2),
        )
    )


if __name__ == "__main__":
    app()