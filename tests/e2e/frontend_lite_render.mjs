import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM, VirtualConsole } from "jsdom";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const frontendLiteDir = path.join(repoRoot, "services", "frontend-lite");

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {
    backend: "",
    timeoutMs: 20000,
  };
  for (let i = 0; i < args.length; i += 1) {
    const cur = args[i];
    if (cur === "--backend") {
      out.backend = String(args[i + 1] || "").trim();
      i += 1;
      continue;
    }
    if (cur === "--timeout-ms") {
      out.timeoutMs = Number(args[i + 1] || "20000");
      i += 1;
      continue;
    }
  }
  if (!out.backend) {
    throw new Error("missing required argument: --backend <url>");
  }
  return out;
}

async function waitFor(checkFn, timeoutMs, intervalMs = 100) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const value = await checkFn();
    if (value) {
      return value;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return null;
}

async function main() {
  const { backend, timeoutMs } = parseArgs();
  const indexHtml = await fs.readFile(path.join(frontendLiteDir, "index.html"), "utf-8");
  const appJs = await fs.readFile(path.join(frontendLiteDir, "app.js"), "utf-8");

  const stageLogs = [];
  const logStage = (stage, msg) => {
    const line = `[${stage}] ${msg}`;
    stageLogs.push(line);
    console.log(line);
  };

  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (err) => {
    logStage("frontend-jsdom", `error: ${err.message}`);
  });

  const dom = new JSDOM(indexHtml, {
    url: "http://sql2bi-frontend-lite.local/",
    runScripts: "dangerously",
    resources: "usable",
    virtualConsole,
    beforeParse(window) {
      window.fetch = fetch;
      window.alert = (message) => {
        logStage("frontend-alert", String(message));
      };
    },
  });

  process.on("unhandledRejection", (reason) => {
    logStage("frontend-unhandled", String(reason));
  });

  dom.window.localStorage.setItem("sql2bi_backend", backend);

  const scriptEl = dom.window.document.createElement("script");
  scriptEl.textContent = appJs;
  dom.window.document.body.appendChild(scriptEl);

  const result = await waitFor(() => {
    const title = dom.window.document.querySelector("#title")?.textContent?.trim() || "";
    const widgets = Array.from(dom.window.document.querySelectorAll(".widget-title")).map((el) =>
      (el.textContent || "").trim(),
    );
    if (widgets.length > 0) {
      return { title, widgets };
    }
    return null;
  }, timeoutMs);

  if (!result) {
    const title = dom.window.document.querySelector("#title")?.textContent?.trim() || "";
    const htmlSnapshot = dom.window.document.querySelector("#grid")?.innerHTML || "";
    throw new Error(
      `frontend render timeout after ${timeoutMs}ms; title="${title}"; grid="${htmlSnapshot}"; logs=${JSON.stringify(
        stageLogs,
      )}`,
    );
  }

  const response = {
    ok: true,
    backend,
    pageTitle: result.title,
    widgetCount: result.widgets.length,
    widgetTitles: result.widgets,
  };
  console.log(JSON.stringify(response));
}

main().catch((err) => {
  console.error(`[frontend-e2e] ${err.stack || err.message}`);
  process.exit(1);
});
