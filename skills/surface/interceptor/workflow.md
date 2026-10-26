# interceptor workflow (on demand)

Trigger ONLY when the operator's browser is required: login, MFA, CAPTCHA,
SPA state. Transport per the interceptor WSL notes (powershell.exe entry
points, NAT loopback + WSLENV gate).

1. Start the stack; operator performs the interaction.
2. Capture the authenticated session; export-curl into caido; identities row.
3. Stop; never leave the stack running past the need.

## N/A escapes

- `N/A: no operator-browser interaction needed this pass`
