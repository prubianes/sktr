# Security Policy

## Supported versions

Security fixes are provided for the latest published release or release
candidate. Older prereleases and development snapshots are not supported.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting for SKTR:

1. Open the repository's **Security** tab.
2. Select **Advisories**.
3. Select **Report a vulnerability**.

If that option is unavailable, open a minimal public issue asking the maintainer
for a private reporting channel. Do not include vulnerability details in it.

Include affected versions, reproduction steps, impact, and any suggested
mitigation. Remove API keys, private source code, and unrelated personal data
from the report. You should receive an acknowledgement within seven days; timing
for a fix depends on severity and reproducibility.

For non-sensitive defects and feature requests, use the public
[issue tracker](https://github.com/prubianes/sktr/issues).

## Credential handling

SKTR reads optional OpenAI credentials from `SKTR_OPENAI_API_KEY` or
`OPENAI_API_KEY`. It does not store those values in `sktr.yml`, review artifacts,
or diagnostic output. Reports should still be reviewed before sharing because
they contain repository paths, symbols, dependencies, and change metadata.
