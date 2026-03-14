"""Shared supply-chain security utilities for skill manifest tooling."""
import re

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
    'wshobson',
    'wsimmonds',
})

INJECTION_PATTERNS = [
    (re.compile(r'ignore\s+(?:all\s+|any\s+|previous\s+|prior\s+|above\s+)?(?:instructions|rules|guidelines)', re.IGNORECASE), 'instruction override'),
    (re.compile(r'you\s+are\s+now\b', re.IGNORECASE), 'identity override'),
    (re.compile(r'from\s+now\s+on\b.*?\b(?:ignore|forget|disregard)', re.IGNORECASE), 'behavioral override'),
    (re.compile(r'system\s+(?:prompt|message|instruction)', re.IGNORECASE), 'system prompt reference'),
    (re.compile(r'disregard\s+(?:all\s+|any\s+|previous\s+|prior\s+)?(?:instructions|rules|guidelines|constraints)', re.IGNORECASE), 'instruction disregard'),
    (re.compile(r'<script[\s>]', re.IGNORECASE), 'script injection'),
    (re.compile(r'javascript\s*:', re.IGNORECASE), 'javascript URI'),
    (re.compile(r'data:\s*\w+/\w+;base64,', re.IGNORECASE), 'base64 data embed'),
    (re.compile(r'<\s*(?:invoke|tool_use|function_call)', re.IGNORECASE), 'tool invocation injection'),
    (re.compile(r'\bIMPORTANT\s*:\s*(?:ignore|override|disregard|forget)', re.IGNORECASE), 'priority override'),
]


def scan_content(content: str, skill_id: str) -> list[str]:
    """Scan skill content for prompt injection patterns. Returns list of warning strings."""
    warnings = []
    for pattern, description in INJECTION_PATTERNS:
        for match in pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            warnings.append(f'  {skill_id} line {line_num}: {description} — matched "{match.group()}"')
    return warnings
