#!/usr/bin/env python3
"""
CLI tool for managing memories via the API at http://localhost:4206/.

Requirements:
    pip install requests
"""
import argparse
import sys
import requests

API_URL = "http://localhost:4206"


def print_memory(mem):
    print(f"UUID:      {mem.get('id')}")
    print(f"Component: {mem.get('metadata', {}).get('component')}")
    print(f"Mode:      {mem.get('metadata', {}).get('mode')}")
    print(f"Priority:  {mem.get('metadata', {}).get('priority')}")
    print(f"Timestamp: {mem.get('metadata', {}).get('timestamp')}")
    print(f"Memory:    {mem.get('memory')}")
    print("-" * 60)


def list_memories(component=None, mode=None):
    params = {}
    if component:
        params['component'] = component
    if mode:
        params['mode'] = mode
    try:
        resp = requests.get(f"{API_URL}/memory", params=params)
        resp.raise_for_status()
        memories = resp.json()
        if not memories:
            print("No memories found.")
            return
        # Reverse the order so oldest is printed first
        for m in reversed(memories):
            print_memory(m)
    except Exception as e:
        print(f"Error listing memories: {e}")


def list_all_memories():
    list_memories()


def add_memory(memory, priority, component, mode):
    data = {
        "memory": memory,
        "priority": float(priority),
        "component": component,
        "mode": mode
    }
    try:
        resp = requests.post(f"{API_URL}/memory", json=data)
        resp.raise_for_status()
        m = resp.json()
        print("Memory added:")
        print_memory(m)
    except Exception as e:
        print(f"Error adding memory: {e}")


def delete_memory(uuid):
    try:
        resp = requests.delete(f"{API_URL}/memory/{uuid}")
        if resp.status_code == 204 or resp.status_code == 200:
            print(f"Memory {uuid} deleted.")
        else:
            print(f"Failed to delete memory: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Error deleting memory: {e}")


def modify_priority(uuid, patch_data):
    try:
        resp = requests.patch(f"{API_URL}/memory/{uuid}", json=patch_data)
        resp.raise_for_status()
        m = resp.json()
        print("Priority updated:")
        print_memory(m)
    except Exception as e:
        print(f"Error modifying priority: {e}")


def main():
    parser = argparse.ArgumentParser(description="Manage memories via API.")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List memories by component and mode")
    list_parser.add_argument("--component", help="Component name", required=False)
    list_parser.add_argument("--mode", help="Mode", required=False)

    subparsers.add_parser("list-all", help="List all memories")

    add_parser = subparsers.add_parser("add", help="Add a memory")
    add_parser.add_argument("memory", help="Memory text")
    add_parser.add_argument("priority", type=float, help="Priority (0-1)")
    add_parser.add_argument("component", help="Component name")
    add_parser.add_argument("mode", help="Mode")

    del_parser = subparsers.add_parser("delete", help="Delete a memory by uuid")
    del_parser.add_argument("uuid", help="Memory UUID")

    mod_parser = subparsers.add_parser("modify", help="Modify a memory's priority")
    mod_parser.add_argument("uuid", help="Memory UUID")
    mod_parser.add_argument("priority", type=float, help="New priority (0-1)")
    mod_parser.add_argument("component", help="Component name")
    mod_parser.add_argument("mode", help="Mode")

    args = parser.parse_args()

    if args.command == "list":
        list_memories(args.component, args.mode)
    elif args.command == "list-all":
        list_all_memories()
    elif args.command == "add":
        add_memory(args.memory, args.priority, args.component, args.mode)
    elif args.command == "delete":
        delete_memory(args.uuid)
    elif args.command == "modify":
        patch_data = {"priority": args.priority, "component": args.component, "mode": args.mode}
        modify_priority(args.uuid, patch_data)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
