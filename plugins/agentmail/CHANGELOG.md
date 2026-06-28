# Changelog

## 1.0.0

Initial release.

- 8 declarative http-rail tools against the AgentMail API (`api.agentmail.to/v0`): inboxes (`agentmail_create_inbox`, `agentmail_list_inboxes`), messages (`agentmail_list_messages`, `agentmail_get_message`, `agentmail_send_message`, `agentmail_reply`), threads (`agentmail_list_threads`, `agentmail_get_thread`).
- API-key auth (`Authorization: Bearer <key>`) stored in the OS keychain.
- Page-token pagination on the list tools (bounded at 5 pages).
- `agentmail-plugin` skill: inbox lifecycle, polling inbound mail via `list_messages?after=`, send/reply write etiquette, "this is the agent's own mailbox, not the operator's".
