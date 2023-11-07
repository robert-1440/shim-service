import base64
import json
import logging
import os
import sys
from traceback import print_exc
from typing import Dict, Any

import adjust_path
from bean import profiles, ALL_PROFILES

profiles.set_active_profiles(ALL_PROFILES)
from bean import beans, BeanName
from repos.secrets import ServiceKeys, SecretsRepo, ServiceKey
from tools.support.command_line import CommandLineProcessor
from tools.support.utils import prompt_yes
from utils import string_utils, hash_utils
from utils.date_utils import get_system_time_in_millis


def usage():
    print(f"Usage: {adjust_path.get_our_file_name()} token", file=sys.stderr)
    exit(3)


def attempt_decode(token: str, padding=None):
    try:
        return base64.b64decode(token)
    except BaseException as ex:
        if padding == "==":
            raise ex
        if padding is None:
            return attempt_decode(token + '=', '=')
        else:
            return attempt_decode(token + "=", '==')


def transform_keys(record: Dict[str, Any]) -> ServiceKeys:
    keys = []
    now = get_system_time_in_millis()
    for key_id, key in record.items():
        keys.append(ServiceKey(
            key_id,
            key,
            now
        ))
    return ServiceKeys(keys)


def deserialize(token: str) -> ServiceKeys:
    try:
        data = attempt_decode(token)
        value = string_utils.decompress(data)
        record = json.loads(value)
        expected_hash = record['hash']
        if expected_hash is not None:
            contents = record['contents']
            if contents is not None:
                encoded = json.dumps(contents, separators=(',', ':'))
                actual_hash = hash_utils.hash_sha256_to_hex(encoded)
                if actual_hash == expected_hash:
                    if contents['serviceName'] == 'shim':
                        return transform_keys(contents['keys'])
    except:
        print_exc()
        pass
    print("Invalid token.", file=sys.stderr)
    exit(2)


cli = CommandLineProcessor(usage)
token = cli.get_next_arg("token")
cli.assert_no_more()

logging.getLogger("botocore.credentials").setLevel(logging.ERROR)

profile = os.environ.get('AWS_PROFILE')
if profile is None:
    print("Need AWS_PROFILE set.", file=sys.stderr)
    exit(3)
keys = deserialize(token)
repo: SecretsRepo = beans.get_bean_instance(BeanName.SECRETS_REPO)
current = repo.find_service_keys()
if current is not None:
    print(f"Service keys are already deployed for {profile}.", file=sys.stderr)
    exit(2)

record = keys.to_record()
print(json.dumps(record, indent=True))
prompt_yes(f"Deploy to {profile}", exit_code_on_no=0)
repo.create_service_keys(keys)
print("Service keys deployed.")