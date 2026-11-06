// Vault path safety, exercised through the real server over MCP stdio: every
// path a tool touches must resolve, symlinks followed, to a place inside the
// vault. A link planted in the vault never reaches a file outside it.
//
// Run: node --test plugins/obsidian/src/vault_paths.test.js

import { after, before, describe, test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const SERVER = path.join(path.dirname(fileURLToPath(import.meta.url)), "index.js");
const HOOK_TIMEOUT_MS = 30_000;
const SECRET = "SECRET-KEY-MATERIAL\n";
const OUTSIDE_NOTE = "outside note\n";

let tmp;
let vault;
let outside;
let client;

before(
  async () => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fermix-obsidian-vault-paths-"));
    vault = path.join(tmp, "vault");
    outside = path.join(tmp, "outside");
    fs.mkdirSync(vault);
    fs.mkdirSync(path.join(outside, "dir"), { recursive: true });
    fs.writeFileSync(path.join(outside, "secret.md"), SECRET);
    fs.writeFileSync(path.join(outside, "dir", "note.md"), OUTSIDE_NOTE);
    fs.writeFileSync(path.join(vault, "real.md"), "in-vault note\n");
    // A link from one vault note to another stays usable.
    fs.symlinkSync(path.join(vault, "real.md"), path.join(vault, "alias.md"));
    fs.symlinkSync(path.join(outside, "secret.md"), path.join(vault, "leak.md"));
    fs.symlinkSync(path.join(outside, "planted.md"), path.join(vault, "dangling.md"));
    fs.symlinkSync(path.join(outside, "dir"), path.join(vault, "linked"));

    client = new Client({ name: "vault-paths-test", version: "1.0.0" });
    await client.connect(
      new StdioClientTransport({
        command: process.execPath,
        args: [SERVER],
        env: { OBSIDIAN_VAULT_PATH: vault },
      })
    );
  },
  { timeout: HOOK_TIMEOUT_MS }
);

after(
  async () => {
    if (client !== undefined) await client.close();
    if (tmp !== undefined) fs.rmSync(tmp, { recursive: true, force: true });
  },
  { timeout: HOOK_TIMEOUT_MS }
);

async function call(name, args) {
  const result = await client.callTool({ name, arguments: args });
  const text = result.content.map((part) => part.text).join("\n");
  return { isError: result.isError === true, text };
}

async function callOk(name, args) {
  const result = await call(name, args);
  assert.equal(result.isError, false, `${name} failed: ${result.text}`);
  return result.text;
}

describe("paths inside the vault", () => {
  test("create, read, append and list a note", async () => {
    await callOk("create_note", { path: "projects/new.md", content: "first" });
    assert.equal(fs.readFileSync(path.join(vault, "projects", "new.md"), "utf8"), "first");

    assert.equal(await callOk("read_note", { path: "projects/new.md" }), "first");

    await callOk("append_note", { path: "projects/new.md", content: "second" });
    assert.equal(await callOk("read_note", { path: "projects/new.md" }), "first\nsecond");

    const folder = JSON.parse(await callOk("list_folder", { path: "projects" }));
    assert.deepEqual(folder.entries, ["new.md"]);

    const root = JSON.parse(await callOk("list_folder", {}));
    assert.ok(root.entries.includes("projects/"), root.entries.join(", "));
    assert.ok(root.entries.includes("real.md"), root.entries.join(", "));
  });

  test("a link to another note in the vault reads that note", async () => {
    assert.equal(await callOk("read_note", { path: "alias.md" }), "in-vault note\n");
  });

  test("create still refuses an existing note", async () => {
    const result = await call("create_note", { path: "real.md", content: "overwrite" });
    assert.equal(result.isError, true);
    assert.match(result.text, /already exists/);
    assert.equal(fs.readFileSync(path.join(vault, "real.md"), "utf8"), "in-vault note\n");
  });
});

describe("a note linked to a file outside the vault", () => {
  test("read is refused and the outside file is not returned", async () => {
    const result = await call("read_note", { path: "leak.md" });
    assert.equal(result.isError, true);
    assert.equal(result.text, "Error: path escapes the vault: 'leak.md'");
    assert.ok(!result.text.includes("SECRET"));
  });

  test("append is refused and the outside file is unchanged", async () => {
    const result = await call("append_note", { path: "leak.md", content: "export PWNED=1" });
    assert.equal(result.isError, true);
    assert.equal(result.text, "Error: path escapes the vault: 'leak.md'");
    assert.equal(fs.readFileSync(path.join(outside, "secret.md"), "utf8"), SECRET);
  });
});

describe("a dangling link at a create path", () => {
  test("create is refused and the outside target is not created", async () => {
    const result = await call("create_note", { path: "dangling.md", content: "planted" });
    assert.equal(result.isError, true);
    assert.match(result.text, /already exists/);
    assert.equal(fs.existsSync(path.join(outside, "planted.md")), false);
  });
});

describe("a folder linked to a directory outside the vault", () => {
  test("list is refused", async () => {
    const result = await call("list_folder", { path: "linked" });
    assert.equal(result.isError, true);
    assert.equal(result.text, "Error: path escapes the vault: 'linked'");
  });

  test("read of a note inside it is refused", async () => {
    const result = await call("read_note", { path: "linked/note.md" });
    assert.equal(result.isError, true);
    assert.equal(result.text, "Error: path escapes the vault: 'linked/note.md'");
    assert.ok(!result.text.includes("outside note"));
  });

  test("append to a note inside it is refused and the note is unchanged", async () => {
    const result = await call("append_note", { path: "linked/note.md", content: "more" });
    assert.equal(result.isError, true);
    assert.equal(result.text, "Error: path escapes the vault: 'linked/note.md'");
    assert.equal(fs.readFileSync(path.join(outside, "dir", "note.md"), "utf8"), OUTSIDE_NOTE);
  });

  test("create inside it is refused and nothing is created outside", async () => {
    const direct = await call("create_note", { path: "linked/new.md", content: "x" });
    assert.equal(direct.isError, true);
    assert.equal(direct.text, "Error: path escapes the vault: 'linked/new.md'");
    assert.equal(fs.existsSync(path.join(outside, "dir", "new.md")), false);

    const nested = await call("create_note", { path: "linked/deeper/new.md", content: "x" });
    assert.equal(nested.isError, true);
    assert.equal(nested.text, "Error: path escapes the vault: 'linked/deeper/new.md'");
    assert.equal(fs.existsSync(path.join(outside, "dir", "deeper")), false);
  });
});
