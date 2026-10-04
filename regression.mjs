// Real disposable Unix-socket regression tests; no Herdr, model, or credentials.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import net from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { pathToFileURL } from "node:url";

const pluginURL = process.argv[2] ? pathToFileURL(process.argv[2]) : new URL("./herdr-tui-session.js", import.meta.url);
const plugin = (await import(pluginURL.href)).default;
const directory = await fs.mkdtemp(join(tmpdir(), "herdr-v2-regression-"));
const socketPath = join(directory, "test.sock");
const requests = [];
const server = net.createServer((socket) => {
  let input = "";
  socket.on("data", (chunk) => {
    input += chunk;
    if (!input.includes("\n")) return;
    requests.push(JSON.parse(input.split("\n")[0]));
    socket.end('{"result":{"type":"ok"}}\n');
  });
});
await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(socketPath, resolve);
});
Object.assign(process.env, { HERDR_ENV: "1", HERDR_SOCKET_PATH: socketPath, HERDR_PANE_ID: "fixture:p1" });

async function scenario(name, initial, events, expected) {
  requests.length = 0;
  const sessions = new Map([
    ["parent", { id: "parent" }],
    ["child", { id: "child", parentID: "parent" }],
    ["other", { id: "other" }],
  ]);
  const statuses = new Map(Object.entries(initial));
  const listeners = new Set();
  const dispose = plugin.setup({
    ui: { router: { current: () => ({ type: "session", sessionID: "parent" }) } },
    data: {
      session: {
        get: (id) => sessions.get(id),
        family: () => [...sessions.keys()],
        status: (id) => statuses.get(id) ?? "idle",
        permission: { list: () => [] },
        form: { list: () => [] },
      },
      listen: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    },
  });
  try {
    await delay(200);
    for (const [type, sessionID] of events) {
      statuses.set(sessionID, type.endsWith("started") ? "running" : "idle");
      for (const listener of listeners) listener({ details: { type, data: { sessionID } } });
      await delay(75);
    }
    await delay(200);
    const states = requests.filter((r) => r.params.state).map((r) => r.params.state);
    assert.equal(states.at(-1), expected, name);
    assert.ok(requests.every((r) => r.params.agent_session_id === "parent"));
    console.log(`PASS: ${name} -> ${expected}`);
  } finally { dispose(); }
}

try {
  await scenario("Parent finishes while child is running", {}, [
    ["session.execution.started", "parent"],
    ["session.execution.started", "child"],
    ["session.execution.succeeded", "parent"],
  ], "working");
  await scenario("Child starts while parent is idle", {}, [
    ["session.execution.started", "child"],
  ], "working");
  await scenario("Attach while child is already running", { child: "running" }, [], "working");
  await scenario("Child finishes while parent keeps running", {}, [
    ["session.execution.started", "parent"],
    ["session.execution.started", "child"],
    ["session.execution.succeeded", "child"],
  ], "working");
  await scenario("Unrelated session does not mark parent working", {}, [
    ["session.execution.started", "other"],
  ], "idle");
  console.log("All five socket regression tests passed.");
} finally {
  await new Promise((resolve) => server.close(resolve));
  await fs.unlink(socketPath).catch(() => {});
  await fs.rmdir(directory);
}
