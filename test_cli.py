#!/usr/bin/env python3

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def hello(name: str = "World"):
    """Say hello."""
    console.print(f"Hello {name}!")


if __name__ == "__main__":
    app()
