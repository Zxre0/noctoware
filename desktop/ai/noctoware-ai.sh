# /etc/profile.d/noctoware-ai.sh
# ~/.local/bin first (per-user tools such as Claude Code's native install),
# Noctoware fallback shims last.
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac
case ":$PATH:" in *":/usr/lib/noctoware/shims:"*) ;; *) PATH="$PATH:/usr/lib/noctoware/shims" ;; esac
export PATH
