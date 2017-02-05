#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import os
import sys
import gdapi
import argparse
import argcomplete
from rancher.rancher import TtyHandler, ButterflyHandler, Terminal

client = gdapi.Client(url=os.environ.get('RANCHER_URL'),
                      access_key=os.environ.get('RANCHER_ACCESS_KEY'),
                      secret_key=os.environ.get('RANCHER_SECRET_KEY'))

def find_by_name(prefix, parsed_args, **kwargs):
    containers = client.list("container", state="running", system_ne="NetworkAgent", system=False, name_like=prefix+"%")
    return (container.name for container in containers.data)

def find_by_stack_name(prefix, parsed_args, **kwargs):
    stacks = client.list("stack", state="active", name_like=prefix+"%")
    return (stack.name for stack in stacks.data)

def find_by_service_name(prefix, parsed_args, **kwargs):
    services = client.list("service", state="active", name_like=prefix+"%")
    return (service.name for service in services.data)

if __name__ == "__main__":
    # Init
    parser = argparse.ArgumentParser(description="TTY - Rancher Server terminal")
    parser.add_argument("-b", "--browser", help="Start in browser", action="store_true", default=False)
    parser.add_argument("-s", "--stack", help="Limit to stack name", default=None)
    parser.add_argument("container", help="Container name").completer = find_by_name

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    containers = client.list("container", state="running", kind="container", name=args.container)
    try:
        container = containers[0]
    except IndexError:
        parser.error("container '%s' not found" % args.container)

    if args.browser:
        handler = ButterflyHandler()
        handler.connect(container.id)

    else:
        handler = TtyHandler()
        handler.connect(container.id)

    exit()
