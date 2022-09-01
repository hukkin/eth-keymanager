import argparse
import json
import os
import pathlib
import sys
from urllib.request import Request, urlopen

def request(resource: str, data: bytes | None = None):
    req = Request(f"{args.host}{resource}", data=data)
    req.add_header("authorization", f"Bearer {args.auth}")
    if data:
        req.add_header("accept", "*/*")
        req.add_header("content-type", "application/json")
    else:
        req.add_header("accept", "application/json")
    with urlopen(req) as resp:
        content_bytes = resp.read()
    content_str = content_bytes.decode()
    if data:
        return content_str
    return json.loads(content_str)

def set_fee_recipients(args: argparse.Namespace) -> int:
    # Read the JSON and normalize hex values to lower case
    fee_recipient_data = json.loads(args.file.read_bytes().decode())
    fee_recipient_data = [{"validating_pubkey": d["validating_pubkey"].lower(), "ethaddress": d["ethaddress"].lower()} for d in fee_recipient_data]

    # Show all validators managed by the node to the user
    resp_obj = request("/eth/v1/keystores")
    managed_keystores = {validator_data["validating_pubkey"].lower() for validator_data in resp_obj["data"]}
    print("The node manages the following validators:")
    for v in managed_keystores:
        print(v)

    # Exit if the JSON contains validators not managed by the node
    for d in fee_recipient_data:
        if d["validating_pubkey"] not in managed_keystores:
            sys.stderr.write(f"ERROR: Validator {d['validating_pubkey']} is not managed by the connected node.\n")
            return 1

    # Update the fee recipient according to JSON if need be
    for d in fee_recipient_data:
        print(thematic_break)
        pubkey = d["validating_pubkey"]
        new_ethaddress = d["ethaddress"]
        resp_obj = request(f"/eth/v1/validator/{pubkey}/feerecipient")
        old_ethaddress = resp_obj["data"]["ethaddress"].lower()
        print(f"Configuring {pubkey}...")
        if old_ethaddress == new_ethaddress:
            print("Fee recipient already in sync")
            continue
        req_data = json.dumps({"ethaddress": new_ethaddress}).encode()
        request(f"/eth/v1/validator/{pubkey}/feerecipient", data=req_data)
        print(f"Fee recipient updated. Previously {old_ethaddress}. Now {new_ethaddress}")

    print(thematic_break)
    print(f"Success. All fee recipients synchronized.")
    return 0


def import_keystores(args: argparse.Namespace) -> int:
    # Show all validators managed by the node to the user
    resp_obj = request("/eth/v1/keystores")
    managed_keystores = {validator_data["validating_pubkey"].lower() for validator_data in resp_obj["data"]}
    print("The node manages the following validators:")
    for v in managed_keystores:
        print(v)


    for p in args.keystores:
        print(thematic_break)
        text = p.read_bytes().decode()
        data = json.loads(text)
        pubkey = data["pubkey"]
        pubkey = pubkey if pubkey.startswith("0x") else "0x" + pubkey
        print(f"Importing {pubkey}...")
        if pubkey in managed_keystores:
            print("The node already manages this validating pubkey. Skipping this one.")
            continue
        req_data = json.dumps({"keystores": [text], "passwords": [args.keystore_passwd]}).encode()
        request(f"/eth/v1/keystores", data=req_data)
        print("Keystore imported")


    print(thematic_break)
    print(f"Success. All keystores imported.")
    return 0


thematic_break = "-" * 70

api_host_env_key = "ETH_KEYMANAGER_API_HOST"
api_auth_env_key = "ETH_KEYMANAGER_API_AUTH"

parser = argparse.ArgumentParser(description='A tool for interacting with the Ethereum keymanager API')
parser.add_argument(
    '--host',
    help=f'hostname and port of keymanager API, e.g. http://127.0.0.1:5052 (optionally read from "{api_host_env_key}" environment variable)',
    default=os.environ.get(api_host_env_key)
)
parser.add_argument(
    '--auth',
    help=f'keymanager API auth key (optionally read from "{api_auth_env_key}" environment variable)',
    default=os.environ.get(api_auth_env_key)
)
subparsers = parser.add_subparsers(dest='command', required=True)

fee_parser = subparsers.add_parser('set-fee-recipients', description='Set fee recipients from a JSON file')
fee_parser.add_argument(
    'file',
    help='JSON file with fee recipients to update. Must be an array of objects that have keys "validating_pubkey" and "ethaddress"',
    type=pathlib.Path
)
fee_parser.set_defaults(func=set_fee_recipients)

import_parser = subparsers.add_parser('import-keystores', description='Import keystore files to the validator client')
import_parser.add_argument('keystore_passwd', help='Keystore password. Reused for all keystores')
import_parser.add_argument(
    'keystores',
    nargs='+',
    help='The keystore-*.json files to be imported',
    type=pathlib.Path
)
import_parser.set_defaults(func=import_keystores)

args = parser.parse_args()

# Validate args
if not args.auth or not args.host:
    parser.error(f"Must provide keymanager API host and auth via command line options or environment variables ({api_host_env_key} and {api_auth_env_key})")

exit_code = args.func(args)
raise SystemExit(exit_code)
