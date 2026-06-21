---
name: agentmail-plugin
description: Use for ANY agent email task — create an inbox, send, read, reply, poll for new mail, or work with threads. Hits the AgentMail API directly via the Fermix AgentMail plugin. The inboxes belong to the agent.
---

# AgentMail

Use the `agentmail_*` tools to give the agent its own email. These call the AgentMail API directly and return clean data — no browser, no scraping.

**These are the agent's own inboxes, not the operator's personal mailbox.** Don't treat them as the user's Gmail. Mail sent from them goes out under an agent-owned address; mail arrives for the agent to act on.

## Pick the tool

- Set up: `agentmail_create_inbox` — make a new inbox · `agentmail_list_inboxes` — see existing ones and their `inbox_id`.
- Read: `agentmail_list_messages` (an inbox's recent mail) · `agentmail_get_message` (one message in full — body, headers, attachments).
- Write (confirm first): `agentmail_send_message` (new email) · `agentmail_reply` (reply in-thread).
- Threads: `agentmail_list_threads` · `agentmail_get_thread` for a whole conversation.

Most tools take an `inbox_id` — get it from `agentmail_list_inboxes` (or the create response) before reading or sending.

## Inbox lifecycle

An inbox is a durable address. Create one once with `agentmail_create_inbox` (optionally pin a `username`/`domain`); reuse its `inbox_id` afterward. Pass a stable `client_id` to make creation idempotent so a retry doesn't make a second inbox.

## Polling for inbound mail

There's no push delivery here — to notice new mail, poll `agentmail_list_messages` with `after` set to the timestamp of the last message you saw. Anything newer is unread work. Keep the window tight and `limit` modest.

## Replying keeps the thread

`agentmail_reply` threads the conversation **server-side** — pass the `inbox_id` and the original `message_id` and it sets the headers for you. Do **not** hand-craft `In-Reply-To`/`References` or reuse `send_message` for a reply; use `reply` so the thread stays intact.

## Write etiquette

`agentmail_create_inbox`, `agentmail_send_message`, and `agentmail_reply` are real actions: an inbox is provisioned, or an email lands in a real person's mailbox. Before sending or replying, show the `inbox_id`, recipients (`to`/`cc`/`bcc`), subject, and body, and get explicit confirmation. Don't alter approved content.

## Notes

- List tools page via `page_token`, auto-paging up to 5 pages; say when results may be partial.
- No deleting inboxes/messages, no label/folder management, no calendar — just create-inbox, send, read, reply, and threads. Don't claim more.
- If the `agentmail_*` tools aren't available, the plugin isn't connected — tell the user to add an AgentMail API key on the Fermix setup page. On an auth error, say to re-paste the key; don't fall back to the browser.
