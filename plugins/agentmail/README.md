# AgentMail plugin

Declarative (http-rail) Fermix plugin for AgentMail: agent-owned email inboxes — create them, then send, read, and reply to mail via the AgentMail API (`api.agentmail.to/v0`). Pure `plugin.json` — no code, no runtime.

## Auth

API key (an **AgentMail API key**), stored in the OS keychain:

1. Create a key at <https://console.agentmail.to>.
2. Paste it into Fermix (setup page or config). It is sent as `Authorization: Bearer <key>`.

## Tools

| Tool | What it does |
|---|---|
| `agentmail_create_inbox` | Create an agent-owned inbox (write) |
| `agentmail_list_inboxes` | List inboxes |
| `agentmail_list_messages` | List messages in an inbox |
| `agentmail_get_message` | Get one message in full |
| `agentmail_send_message` | Send an email (write) |
| `agentmail_reply` | Reply to a message (write) |
| `agentmail_list_threads` | List conversation threads |
| `agentmail_get_thread` | Get one thread |

The inboxes belong to the **agent**, not the operator's personal mailbox. Sends and replies notify real recipients — confirm before calling them.
