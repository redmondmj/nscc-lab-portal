#!/usr/bin/env python3
"""
Dynamic Ansible Inventory Script for NSCC Lab Portal.
Fetches real-time student VM inventory and hostvars from the portal API.

Usage:
  # Ping all active VMs in the lab:
  ansible all -i ansible/inventory.py -m win_ping

  # Run playbook against OSYS1200 student VMs:
  ansible-playbook -i ansible/inventory.py playbooks/audit_lab.yml --limit osys1200

Environment Variables (or auto-loaded from .env):
  LAB_PORTAL_URL   URL of the lab portal (default: https://labs.nscctruro.ca)
  ANSIBLE_API_KEY  API key configured in the portal server (.env)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORTAL_URL = "https://labs.nscctruro.ca"


def load_env_defaults():
    """Look for .env in current or parent directories to populate missing config."""
    config = {
        "LAB_PORTAL_URL": os.environ.get("LAB_PORTAL_URL", ""),
        "ANSIBLE_API_KEY": os.environ.get("ANSIBLE_API_KEY", "")
    }

    if config["LAB_PORTAL_URL"] and config["ANSIBLE_API_KEY"]:
        return config

    search_dirs = [Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]
    for d in search_dirs:
        env_file = d / ".env"
        if env_file.is_file():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k in config and not config[k]:
                            config[k] = v
            except Exception:
                pass

    if not config["LAB_PORTAL_URL"]:
        config["LAB_PORTAL_URL"] = DEFAULT_PORTAL_URL

    return config


def fetch_inventory():
    config = load_env_defaults()
    portal_url = config["LAB_PORTAL_URL"].rstrip("/")
    api_key = config["ANSIBLE_API_KEY"]

    endpoint = f"{portal_url}/api/admin/ansible/inventory"
    req = urllib.request.Request(endpoint)
    req.add_header("User-Agent", "Ansible-Dynamic-Inventory/1.0")
    req.add_header("Accept", "application/json")

    if api_key:
        req.add_header("X-API-Key", api_key)
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get_content_type()
            raw_data = resp.read().decode("utf-8")

            if content_type != "application/json" and not raw_data.strip().startswith(("{", "[")):
                sys.stderr.write(f"[ERROR] Received non-JSON response ({content_type}) from {endpoint}.\n")
                sys.stderr.write(
                    "[HINT] The request was likely redirected to Microsoft Entra ID SSO. Ensure ANSIBLE_API_KEY is configured on the server and client.\n"
                )
                sys.exit(1)

            return json.loads(raw_data)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[ERROR] HTTP {e.code} ({e.reason}) querying {endpoint}\n")
        if e.code in (401, 403):
            sys.stderr.write(
                "[HINT] Authentication failed. Ensure ANSIBLE_API_KEY is configured in your .env or environment.\n"
            )
        sys.exit(1)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[ERROR] Failed to parse JSON response from {endpoint}: {e}\n")
        sys.stderr.write("[HINT] Ensure ANSIBLE_API_KEY is set and that the portal is returning JSON.\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"[ERROR] Could not connect to {endpoint}: {e.reason}\n")
        sys.stderr.write("[HINT] Verify network connectivity and that Cloudflare WARP is connected.\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Unexpected error querying inventory: {e}\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="NSCC Lab Portal Dynamic Ansible Inventory")
    parser.add_argument("--list", action="store_true", default=True, help="List all active lab hosts (default)")
    parser.add_argument("--host", help="Get host variables for a specific host")
    args = parser.parse_args()

    inventory = fetch_inventory()

    if args.host:
        hostvars = inventory.get("_meta", {}).get("hostvars", {}).get(args.host, {})
        print(json.dumps(hostvars, indent=2))
    else:
        print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    main()
