import typer
from gitdex.mainFile import *


app = typer.Typer()

@app.command()
def complete(txt: str):
    init_auth()
    full(txt)

@app.command(name="count_token")
def countToken(txt: str):
    with open(txt, encoding="utf-8") as f:
        text = f.read()
    print(f"Number of tokens this txt file has: {count_tokens(text)}")

@app.command()
def srepo(txt: str):
    init_auth()
    user_repos(txt)

@app.command(name="token_by_repo")
def tok_by_rep(txt: str):
    token_by_repo(txt=txt)

@app.command()
def test():
    print("Working!")

if __name__ == "__main__":
    app()