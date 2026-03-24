import json
import os
import argparse
from typing import List, Dict

def generate_license_json(revoked_ids: List[str] = None, ids_status: Dict[str, str] = None, global_revocation: bool = False):
    """
    Generates a license JSON structure for the remote LICENSE_URL.
    """
    data = {
        "status": "REVOKED_GLOBAL" if global_revocation else "OK",
        "revoked_ids": revoked_ids or [],
        "ids": ids_status or {}
    }
    return json.dumps(data, indent=4)

def main():
    parser = argparse.ArgumentParser(description="Generate a license JSON for the tradebot.")
    parser.add_argument("--revoked", nargs="*", help="List of revoked client IDs")
    parser.add_argument("--status", nargs="*", help="Status of client IDs (ID:STATUS, e.g., user1:REVOKED)")
    parser.add_argument("--global-kill", action="store_true", help="Trigger global revocation")
    parser.add_argument("--output", default="license_status.json", help="Output filename")

    args = parser.parse_args()

    ids_status = {}
    if args.status:
        for item in args.status:
            if ":" in item:
                client_id, status = item.split(":", 1)
                ids_status[client_id] = status.upper()

    license_json = generate_license_json(
        revoked_ids=args.revoked,
        ids_status=ids_status,
        global_revocation=args.global_kill
    )

    with open(args.output, "w") as f:
        f.write(license_json)

    print(f"License JSON generated successfully: {args.output}")
    print("\n--- JSON Content ---")
    print(license_json)
    print("\nTo use this:")
    print("1. Upload this file to a public URL (e.g., GitHub Gist, Raw GitHub file, or your own server).")
    print("2. Set the LICENSE_URL in your .env or config.py to that URL.")

if __name__ == "__main__":
    main()
