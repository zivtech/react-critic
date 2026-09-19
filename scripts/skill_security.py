"""Supply-chain trust policy plus the shared content scanner."""

from external_skill_lib import scan_content

TRUSTED_OWNERS = frozenset({
    'auth0',
    'callstack',
    'callstackincubator',
    'clerk',
    'dotneet',
    'expo',
    'getsentry',
    'github',
    'millionco',
    'mindrally',
    'react-native-community',
    'sickn33',
    'vercel-labs',
    'vercel',
    'wshobson',
    'wsimmonds',
})

__all__ = ["TRUSTED_OWNERS", "scan_content"]
