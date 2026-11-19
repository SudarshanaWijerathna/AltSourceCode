// Runs a command with the backend virtualenv's Python, cross-platform.
// Usage: node scripts/py.mjs <args...>   (cwd = backend/)
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const backend = join(root, "backend");
const candidates = [
  join(backend, ".venv", "Scripts", "python.exe"),
  join(backend, ".venv", "bin", "python"),
];
const python = candidates.find(existsSync);
if (!python) {
  console.error("Backend venv not found. Run `npm run setup` first.");
  process.exit(1);
}
const result = spawnSync(python, process.argv.slice(2), { cwd: backend, stdio: "inherit" });
process.exit(result.status ?? 1);
