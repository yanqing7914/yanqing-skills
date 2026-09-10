# Safety Checklist

Do not read, copy, summarize, or store secret values.

Forbidden by default:

- `.env`, `.env.*`, `.npmrc`, `.pypirc`, `.netrc`
- `*.pem`, `*.key`, `*.p12`, `*.pfx`
- private certs and SSH keys
- `~/.ssh/**`
- `~/.codex/auth.json`
- browser profiles and cookies
- cloud credentials and service account files
- kubeconfig and production database credentials
- CI secret dumps or token exports

Do not actively grep/token-hunt. If an accidental match appears, report only the path and risk.

Never allowed:

- Deploy, publish, release.
- `git push`, `git reset --hard`, force-push, destructive rebase.
- Destructive deletion or global config mutation.
- Credential sync, token export, or browser cookie access.

Blocked unless the task card names the command and who approved it:

- Dependency install.
- Migration commands.

Main Session may authorize only install or migration. Do not authorize the never-allowed list.
