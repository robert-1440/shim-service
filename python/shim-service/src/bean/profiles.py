import os
import sys
from typing import Optional

WEB_PROFILE = 0x1
PUBSUB_POLLER_PROFILE = 0x02
LIVE_AGENT_PROCESSOR_PROFILE = 0x04
PUSH_NOTIFIER_PROFILE = 0x08

ALL_PROFILES = WEB_PROFILE | PUBSUB_POLLER_PROFILE | LIVE_AGENT_PROCESSOR_PROFILE | PUSH_NOTIFIER_PROFILE

NON_WEB_PROFILES = ALL_PROFILES ^ WEB_PROFILE
NON_PUSH_PROFILES = ALL_PROFILES ^ PUSH_NOTIFIER_PROFILE

__profile_entries = {
    "web": WEB_PROFILE,
    "pubsub-poller": PUBSUB_POLLER_PROFILE,
    "live-agent-poller": LIVE_AGENT_PROCESSOR_PROFILE,
    "notification-publisher": PUSH_NOTIFIER_PROFILE
}

_active_profiles: Optional[int] = None


def is_profile_active(bit: int):
    return (get_active_profiles() & bit) != 0


def get_active_profiles() -> int:
    global _active_profiles
    if _active_profiles is None:
        profiles = os.environ.get('ACTIVE_PROFILES', "")
        # Can't use logger due to circular dependency
        print(f"Active profiles: {profiles}", file=sys.stderr)
        bits = 0
        for profile in profiles.split(','):
            b = __profile_entries.get(profile.strip().lower(), 0)
            bits |= b
        _active_profiles = bits
    return _active_profiles


def describe_profiles(bits: int):
    output = ""
    for key, value in __profile_entries.items():
        if value & bits != 0:
            if len(output) > 0:
                output += ","
            output += key
    return output
