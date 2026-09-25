# Games plugin

Play the games on [fermix.ai/games](https://fermix.ai/games/chess) with Fermix.
Installed, the agent knows where the games are and how each one is played, so
"let's play chess" or "join the chess game with code 4K7 P2Q" is enough, with
no address pasted into the chat.

The plugin is one skill and nothing else: no tools, no process, no sign-in, no
secret. Everything runs inside Fermix itself. Its skill names one address, the
site's games index at `https://fermix.ai/games/index.json`, and the rules for
playing through a page's own tools.

## How a game is played

1. The agent reads the index. Each entry carries the game's lobby, its docs
   page and a one-line `start` instruction naming the page's tools.
2. It opens the lobby in Fermix's own managed browser and lists the tools the
   page offers to agents over WebMCP (the `browser` tool's `webmcp` action).
3. It sets a game up itself, or joins with the code the person gives it, then
   reads the state and submits moves as data. No screenshots, no clicking.

The game's own page describes its tools; the skill carries none of that, so a
new game on the site needs no change here. Adding a game is adding it to the
site's index.

## Playing in a chat

A page's wait tool blocks the conversation while it waits. The skill therefore
plays move by move: the agent moves, says it is your turn, and ends its turn;
you say when you have moved. On a voice call the same rule keeps it free to
talk.

## Install

On the setup **Plugins** page or in the macOS app's **Available** list, install
Games and turn it on. There is nothing to connect.

## Local development

Symlink `plugins/games` into the directory named by `[fermix_core.plugins]
dev_local` in `config.toml`, add `"games"` to that section's `enabled` list,
and restart the daemon. The skill loads from this checkout in place.

## Validation

```sh
python3 scripts/validate_plugin.py plugins/games
python3 scripts/check_plugin_package.py plugins/games/
```
