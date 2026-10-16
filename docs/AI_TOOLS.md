# AI development tools

Preinstalled (`noctoware-ai-tools`): git, Node.js + npm, Python + pip,
base-devel, ripgrep and the **OpenAI Codex CLI** (`openai-codex` from Arch,
Apache-2.0). Run `codex` and sign in with your ChatGPT account or API key.

**Claude Code** is proprietary and not redistributed. Install it per user:
```
noctoware-claude-setup          # explains, asks for consent, runs Anthropic's official installer
claude                          # first run: log in with your own Claude account
```
Typing `claude` before installing offers the same setup (a fallback shim in
`/usr/lib/noctoware/shims`, lowest PATH priority). The official native
install lives in `~/.local/bin/claude` and updates itself. Noctoware never
bundles API keys, tokens or credentials and never stores passwords.
