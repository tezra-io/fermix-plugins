#!/usr/bin/env node
// Fermix Obsidian plugin — first-party MCP stdio server (MIT).
//
// Serves exactly five tools over the Obsidian vault directory given by the
// OBSIDIAN_VAULT_PATH environment variable: search_notes, read_note,
// create_note, append_note, list_folder. Fermix prefixes discovered names
// with `obsidian_`, so the agent sees obsidian_search_notes etc.
//
// The vault is reached as plain files — the Obsidian app does not need to
// be running. No network access. Every path argument must resolve inside
// the vault root; absolute paths and `..` escapes are rejected loudly.

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "node:fs";
import path from "node:path";

const MAX_SEARCH_RESULTS = 50;
const DEFAULT_SEARCH_RESULTS = 10;
const MAX_FILES_SCANNED = 10_000;

function fatal(message) {
  process.stderr.write(`fermix-obsidian-mcp: ${message}\n`);
  process.exit(1);
}

const rawVaultPath = process.env.OBSIDIAN_VAULT_PATH;
if (typeof rawVaultPath !== "string" || rawVaultPath.trim() === "") {
  fatal("OBSIDIAN_VAULT_PATH is not set — configure the plugin's vault path");
}
let vaultRoot;
try {
  vaultRoot = fs.realpathSync(rawVaultPath);
} catch {
  fatal(`OBSIDIAN_VAULT_PATH does not exist: ${rawVaultPath}`);
}
if (!fs.statSync(vaultRoot).isDirectory()) {
  fatal(`OBSIDIAN_VAULT_PATH is not a directory: ${rawVaultPath}`);
}

// Resolve a vault-relative path and assert it stays inside the vault root.
// Rejects absolute paths and any `..` segment before resolution so the
// refusal names the offending input, not a confusing resolved path.
function resolveInVault(relPath) {
  if (typeof relPath !== "string" || relPath.trim() === "") {
    throw new Error("path must be a non-empty vault-relative string like 'folder/note.md'");
  }
  if (path.isAbsolute(relPath)) {
    throw new Error(`path must be vault-relative, not absolute: '${relPath}'`);
  }
  if (relPath.split(/[\\/]+/).includes("..")) {
    throw new Error(`path escapes the vault ('..' is not allowed): '${relPath}'`);
  }
  const resolved = path.resolve(vaultRoot, relPath);
  if (resolved !== vaultRoot && !resolved.startsWith(vaultRoot + path.sep)) {
    throw new Error(`path escapes the vault: '${relPath}'`);
  }
  return resolved;
}

function requireNotePath(relPath) {
  const resolved = resolveInVault(relPath);
  if (!resolved.endsWith(".md")) {
    throw new Error(`notes are markdown files — path must end with .md: '${relPath}'`);
  }
  return resolved;
}

function requireString(args, key) {
  const value = args?.[key];
  if (typeof value !== "string") {
    throw new Error(`'${key}' must be a string`);
  }
  return value;
}

// Markdown files under the vault, depth-first, dot-entries (.obsidian,
// .trash) skipped, total scan bounded by MAX_FILES_SCANNED.
function* walkNotes(dir, state) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    if (state.scanned >= MAX_FILES_SCANNED) return;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkNotes(full, state);
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      state.scanned += 1;
      yield full;
    }
  }
}

function searchNotes(args) {
  const query = requireString(args, "query").toLowerCase();
  if (query.trim() === "") throw new Error("'query' must be a non-empty string");
  const rawLimit = args?.limit ?? DEFAULT_SEARCH_RESULTS;
  if (typeof rawLimit !== "number" || !Number.isFinite(rawLimit)) {
    throw new Error("'limit' must be a number");
  }
  const limit = Math.min(Math.max(Math.trunc(rawLimit), 1), MAX_SEARCH_RESULTS);

  const results = [];
  const state = { scanned: 0 };
  for (const file of walkNotes(vaultRoot, state)) {
    if (results.length >= limit) break;
    const relPath = path.relative(vaultRoot, file);
    const content = fs.readFileSync(file, "utf8");
    if (relPath.toLowerCase().includes(query)) {
      results.push({ path: relPath, match: "filename" });
      continue;
    }
    const line = content
      .split("\n")
      .find((candidate) => candidate.toLowerCase().includes(query));
    if (line !== undefined) {
      results.push({ path: relPath, match: "content", snippet: line.trim().slice(0, 200) });
    }
  }
  return jsonText({ query: args.query, results, truncated: results.length >= limit });
}

function readNote(args) {
  const resolved = requireNotePath(requireString(args, "path"));
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
    throw new Error(`note not found: '${args.path}'`);
  }
  return text(fs.readFileSync(resolved, "utf8"));
}

function createNote(args) {
  const relPath = requireString(args, "path");
  const content = requireString(args, "content");
  const resolved = requireNotePath(relPath);
  if (fs.existsSync(resolved)) {
    throw new Error(`note already exists: '${relPath}' — use append_note to add to it`);
  }
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  fs.writeFileSync(resolved, content, "utf8");
  return text(`Created '${relPath}' (${Buffer.byteLength(content)} bytes)`);
}

function appendNote(args) {
  const relPath = requireString(args, "path");
  const content = requireString(args, "content");
  const resolved = requireNotePath(relPath);
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
    throw new Error(`note not found: '${relPath}' — use create_note to create it`);
  }
  const existing = fs.readFileSync(resolved, "utf8");
  const separator = existing === "" || existing.endsWith("\n") ? "" : "\n";
  fs.appendFileSync(resolved, separator + content, "utf8");
  return text(`Appended ${Buffer.byteLength(content)} bytes to '${relPath}'`);
}

function listFolder(args) {
  const relPath = args?.path ?? "";
  const resolved = relPath === "" ? vaultRoot : resolveInVault(relPath);
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isDirectory()) {
    throw new Error(`folder not found: '${relPath || "/"}'`);
  }
  const entries = fs
    .readdirSync(resolved, { withFileTypes: true })
    .filter((entry) => !entry.name.startsWith("."))
    .map((entry) => (entry.isDirectory() ? `${entry.name}/` : entry.name))
    .sort();
  return jsonText({ path: relPath || "", entries });
}

function text(value) {
  return { content: [{ type: "text", text: value }] };
}

function jsonText(value) {
  return text(JSON.stringify(value, null, 2));
}

const TOOLS = [
  {
    name: "search_notes",
    description: "Full-text search across the vault's markdown notes (filenames and contents).",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Case-insensitive text to find in note names or contents." },
        limit: { type: "number", description: "Maximum results (default 10, max 50)." },
      },
      required: ["query"],
    },
    handler: searchNotes,
  },
  {
    name: "read_note",
    description: "Read one note's markdown by vault-relative path, e.g. 'folder/note.md'.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Vault-relative note path ending in .md." },
      },
      required: ["path"],
    },
    handler: readNote,
  },
  {
    name: "create_note",
    description: "Create a new markdown note. Refuses to overwrite an existing note.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Vault-relative note path ending in .md." },
        content: { type: "string", description: "Markdown content for the new note." },
      },
      required: ["path", "content"],
    },
    handler: createNote,
  },
  {
    name: "append_note",
    description: "Append markdown to an existing note. Refuses if the note does not exist.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Vault-relative note path ending in .md." },
        content: { type: "string", description: "Markdown content to append." },
      },
      required: ["path", "content"],
    },
    handler: appendNote,
  },
  {
    name: "list_folder",
    description: "List notes and folders under a vault path (vault root when omitted).",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Vault-relative folder path; omit for the vault root." },
      },
    },
    handler: listFolder,
  },
];

const server = new Server(
  { name: "fermix-obsidian", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })),
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const tool = TOOLS.find((candidate) => candidate.name === request.params.name);
  if (tool === undefined) {
    return { content: [{ type: "text", text: `Error: unknown tool '${request.params.name}'` }], isError: true };
  }
  try {
    return tool.handler(request.params.arguments ?? {});
  } catch (error) {
    return { content: [{ type: "text", text: `Error: ${error.message}` }], isError: true };
  }
});

await server.connect(new StdioServerTransport());
