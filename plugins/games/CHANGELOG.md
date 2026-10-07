# Changelog

## 1.1.0

- The skill plays a game through to the end when the person asks it to keep
  playing, watch the game or play to the end, instead of refusing to loop on
  waits. Move by move stays the default in a chat and on a voice call.
- It gives the real wait budgets: Fermix holds one `webmcp` call for 8 seconds
  without a `timeout_ms` and 60 at most, so it asks the page for up to 50
  seconds and passes a `timeout_ms` about 10 seconds longer. A wait that comes
  back `timedOut` is the page's limit, so it waits again.
- While playing through it hands the turn back after three waits in a row that
  bring nothing new, and by about 80 tool calls in a long game, before the
  turn's step limit.

## 1.0.0

- First release. One skill, `games-plugin`, that names the games index on
  fermix.ai and the rules for playing a game through its page's WebMCP tools
  from a chat or a voice call: find the lobby from the index, list the page's
  tools, play move by move, keep the seat link. No tools, no process, no
  sign-in.
