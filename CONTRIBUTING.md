# Contributing to SpaceMedic

SpaceMedic welcomes bug reports, translations, tests, documentation, cleanup-rule proposals, and code contributions.

## Development

```bat
py -3 -m unittest discover -s tests -v
py -3 -m spacemedic
```

Runtime code must remain standard-library-only unless a dependency is justified, audited, pinned, and approved.

## Safety requirements

A cleanup feature must include a read-only preview, risk classification, protected-path checks, explicit confirmation, failure handling, and automated tests. Never add generic Registry cleaning, forced driver/security removal, automatic download/execution, or name-only broad deletion.

## Cleanup rules

Rules must target regenerable data at a path relative to a known environment root. Provide an authoritative vendor reference where possible. User data, broad vendor roots, license stores, databases, VM disks, browser profiles, and cloud-synced content must not be marked SAFE.

## Translations

Core translations live in `spacemedic/i18n.py`. Keep technical commands and filesystem paths unchanged. Native-speaker review is required before marking a language complete.
