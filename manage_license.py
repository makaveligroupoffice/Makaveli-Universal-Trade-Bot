import json
import os
import argparse
import secrets
import string
from typing import List, Dict, Any

def generate_license_json(revoked_ids: List[str] = None, ids_status: Dict[str, Any] = None, global_revocation: bool = False):
    """
    Generates a license JSON structure for the remote LICENSE_URL.
    """
    data = {
        "status": "REVOKED_GLOBAL" if global_revocation else "OK",
        "revoked_ids": revoked_ids or [],
        "ids": ids_status or {}
    }
    return json.dumps(data, indent=4)

def generate_activation_key(length: int = 16) -> str:
    """
    Generates a random one-time activation key.
    """
    alphabet = string.ascii_uppercase + string.digits
    return "ACT-" + "".join(secrets.choice(alphabet) for _ in range(length))

def main():
    parser = argparse.ArgumentParser(description="Manage tradebot licenses and activation keys.")
    parser.add_argument("--revoked", nargs="*", help="List of revoked client IDs")
    parser.add_argument("--status", nargs="*", help="Status of client IDs (ID:STATUS or ID:STATUS:MACHINE_ID)")
    parser.add_argument("--global-kill", action="store_true", help="Trigger global revocation")
    parser.add_argument("--generate-key", action="store_true", help="Generate a new one-time activation key")
    parser.add_argument("--output", default="license_status.json", help="Output filename")

    args = parser.parse_args()

    # Load existing license file if it exists to preserve data
    ids_status = {}
    revoked_ids = []
    if os.path.exists(args.output):
        try:
            with open(args.output, "r") as f:
                existing_data = json.load(f)
                ids_status = existing_data.get("ids", {})
                revoked_ids = existing_data.get("revoked_ids", [])
        except:
            pass

    if args.revoked:
        for rid in args.revoked:
            if rid not in revoked_ids:
                revoked_ids.append(rid)

    if args.status:
        for item in args.status:
            parts = item.split(":")
            if len(parts) >= 2:
                client_id = parts[0]
                status = parts[1].upper()
                machine_id = parts[2] if len(parts) > 2 else None
                
                if machine_id:
                    ids_status[client_id] = {"status": status, "machine_id": machine_id}
                else:
                    ids_status[client_id] = status

    if args.generate_key:
        new_key = generate_activation_key()
        # Add it to the status with PENDING state
        ids_status[new_key] = "PENDING"
        print(f"NEW ACTIVATION KEY GENERATED: {new_key}")
        print("Give this key to the user. It will be bound to their machine on first use.")

    license_json = generate_license_json(
        revoked_ids=revoked_ids,
        ids_status=ids_status,
        global_revocation=args.global_kill
    )

    with open(args.output, "w") as f:
        f.write(license_json)

    print(f"\nLicense JSON updated successfully: {args.output}")
    print("\n--- JSON Content ---")
    print(license_json)
    print("\nTo use this:")
    print("1. Upload this file to a public URL (e.g., GitHub Gist, Raw GitHub file).")
    print("2. Set the LICENSE_URL in your .env or config.py to that URL.")

if __name__ == "__main__":
    main()
