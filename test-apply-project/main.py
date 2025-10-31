#!/usr/bin/env python3
"""Test Python project for Secuority apply command."""

import requests
from rich.console import Console

console = Console()


def main():
    """Main function."""
    response = requests.get("https://api.github.com", timeout=10)  # S113: Added timeout
    console.print(f"Status: {response.status_code}")


if __name__ == "__main__":
    main()
