#!/usr/bin/env python3
"""Test Python project for Secuority apply command."""

import requests

def main():
    """Main function."""
    response = requests.get("https://api.github.com")
    print(f"Status: {response.status_code}")

if __name__ == "__main__":
    main()