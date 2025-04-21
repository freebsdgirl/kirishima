import argparse
import requests
import sys
import json
from tabulate import tabulate

# Fill these in with your actual host and port
contacts_host = "localhost"
contacts_port = 4202

BASE_URL = f"http://{contacts_host}:{contacts_port}"

def list_contacts():
    url = f"{BASE_URL}/contacts"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    contacts = resp.json()
    # Prepare pretty table
    table = []
    for contact in contacts:
        user_id = contact.get("id", "")
        aliases = contact.get("aliases", [])
        fields = {f["key"]: f["value"] for f in contact.get("fields", [])}
        email = fields.get("email", "")
        imessage = fields.get("imessage", "")
        discord = fields.get("discord", "")
        discord_id = fields.get("discord_id", "")
        notes = contact.get("notes", "")
        # Print each alias on its own row, only show other fields on first row
        for i, alias in enumerate(aliases):
            table.append([
                user_id if i == 0 else "",
                alias,
                email if i == 0 else "",
                imessage if i == 0 else "",
                discord if i == 0 else "",
                discord_id if i == 0 else "",
                notes if i == 0 else ""
            ])
        if not aliases:
            # If no aliases, still print the contact
            table.append([user_id, "", email, imessage, notes])
    headers = ["user id", "aliases", "email", "imessage", "discord", "discord_id", "notes"]
    print("\n" + tabulate(table, headers, tablefmt="github") + "\n")

def confirm_action(message):
    response = input(f"{message} [y/N]: ").strip().lower()
    return response == 'y' or response == 'yes'

def add_contact(args):
    if not confirm_action("Are you sure you want to add this contact?"):
        print("Add cancelled.")
        sys.exit(0)
    url = f"{BASE_URL}/contact"
    fields = []
    if args.email:
        fields.append({"key": "email", "value": args.email})
    if args.imessage:
        fields.append({"key": "imessage", "value": args.imessage})
    if args.discord:
        fields.append({"key": "email", "value": args.discord})
    if args.discord_id:
        fields.append({"key": "imessage", "value": args.discord_id})
    data = {
        "aliases": args.aliases or [],
        "fields": fields,
        "notes": args.notes or ""
    }
    resp = requests.post(url, json=data)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(resp.json(), indent=2))

def fetch_contact(contact_id):
    url = f"{BASE_URL}/contacts"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Error fetching contacts: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    contacts = resp.json()
    for c in contacts:
        if c["id"] == contact_id:
            return c
    print(f"Contact with id {contact_id} not found.", file=sys.stderr)
    sys.exit(1)

def delete_contact(args):
    if not confirm_action(f"Are you sure you want to delete contact {args.id}?"):
        print("Delete cancelled.")
        sys.exit(0)
    url = f"{BASE_URL}/contact/{args.id}"
    resp = requests.delete(url)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(resp.json(), indent=2))

def patch_contact_cli(args):
    url = f"{BASE_URL}/contact/{args.id}"
    data = {}
    if args.aliases is not None:
        data["aliases"] = args.aliases
    # Only include email/imessage if provided
    fields = []
    if args.email is not None:
        fields.append({"key": "email", "value": args.email})
    if args.imessage is not None:
        fields.append({"key": "imessage", "value": args.imessage})
    if args.discord is not None:
        fields.append({"key": "discord", "value": args.discord})
    if args.discord_id is not None:
        fields.append({"key": "discord_id", "value": args.discord_id})
    if fields:
        data["fields"] = fields
    if args.notes is not None:
        data["notes"] = args.notes
    if not data:
        print("Error: At least one of --aliases, --email, --imessage, --discord, --discord_id, or --notes must be provided for patch.", file=sys.stderr)
        sys.exit(1)
    resp = requests.patch(url, json=data)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(resp.json(), indent=2))

def parse_fields(fields):
    result = []
    for f in fields:
        if '=' not in f:
            print(f"Invalid field format: {f}. Use key=value.", file=sys.stderr)
            sys.exit(1)
        k, v = f.split('=', 1)
        result.append((k, v))
    return result

def print_usage_examples():
    print("""
Examples and Syntax:
--------------------

1. List all contacts:
   python contacts.py list

2. Add a contact with multiple aliases and fields (aliases or field values with spaces must be quoted):
   python contacts.py add --aliases "Alice Smith" "Bob Jones" --email "alice@example.com" --imessage "alice@imessage.com" --notes "Test contact"

3. Add a contact with a field value containing spaces:
   python contacts.py add --email "alice@example.com" --imessage "alice@imessage.com"

4. Modify a contact (partially update only specified fields/aliases/notes, others are preserved):
   python contacts.py modify <contact_id> --aliases "Alice Smith" --email "alice@new.com" --imessage "alice@imessage.com" --notes "Updated notes"
   # NOTE: <contact_id> must come immediately after 'modify', before any --aliases or other options

5. Delete a contact:
   python contacts.py delete <contact_id>

Notes:
- When using --aliases, each argument is a separate alias. Use quotes if the value contains spaces.
- The modify command only updates the fields, aliases, or notes you specify; all other data is preserved.
- For modify, the contact_id must come directly after the 'modify' command, before any options.
""")

def main():
    parser = argparse.ArgumentParser(description="Manage contacts via the contacts microservice API.")
    parser.add_argument('--examples', action='store_true', help='Show usage examples and syntax help')
    subparsers = parser.add_subparsers(dest="command", required=False)

    # List
    subparsers.add_parser("list", help="List all contacts")

    # Add
    add_parser = subparsers.add_parser("add", help="Add a new contact")
    add_parser.add_argument("--aliases", nargs="*", help="Aliases for the contact")
    add_parser.add_argument("--email", type=str, help="Email address for the contact")
    add_parser.add_argument("--imessage", type=str, help="iMessage address for the contact")
    add_parser.add_argument("--notes", type=str, help="Notes for the contact")

    # Delete
    del_parser = subparsers.add_parser("delete", help="Delete a contact")
    del_parser.add_argument("id", help="Contact ID to delete")

    # Modify (was patch)
    modify_parser = subparsers.add_parser("modify", help="Partially update a contact (only update specified fields/aliases/notes)")
    modify_parser.add_argument("id", nargs="?", help="Contact ID to modify")
    modify_parser.add_argument("--aliases", nargs="*", help="Aliases to add (existing aliases are preserved)")
    modify_parser.add_argument("--email", type=str, help="Email address for the contact")
    modify_parser.add_argument("--imessage", type=str, help="iMessage address for the contact")
    modify_parser.add_argument("--notes", type=str, help="New notes for the contact (replaces notes if provided)")

    args = parser.parse_args()

    if getattr(args, 'examples', False):
        print_usage_examples()
        sys.exit(0)

    if not args.command:
        parser.print_help()
        print("\nFor usage examples, run: python contacts.py --examples")
        sys.exit(1)

    if args.command == "list":
        list_contacts()
    elif args.command == "add":
        add_contact(args)
    elif args.command == "delete":
        delete_contact(args)
    elif args.command == "modify":
        # If no id or no update args are provided, print example and exit
        if not args.id or not (args.aliases or args.email or args.imessage or args.notes):
            print("No contact ID or update arguments provided for modify. Example usage:")
            print()
            print("   python contacts.py modify <contact_id> --aliases 'Alice Smith' --email 'alice@new.com' --imessage 'alice@imessage.com' --notes 'Updated notes'")
            print()
            print("For more examples, run: python contacts.py --examples")
            sys.exit(1)
        patch_contact_cli(args)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
