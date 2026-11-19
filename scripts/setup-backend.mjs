// Creates backend/.venv and installs the backend package with dev extras.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const backend = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const run = (cmd, args) => {
  const r = spawnSync(cmd, args, { cwd: backend, stdio: "inherit", shell: process.platform === "win32" });
  if (r.status !== 0) process.exit(r.status ?? 1);
};
if (!existsSync(join(backend, ".venv"))) {
  run(process.platform === "win32" ? "python" : "python3", ["-m", "venv", ".venv"]);
}
const py = process.platform === "win32" ? join(".venv", "Scripts", "python.exe") : join(".venv", "bin", "python");
run(py, ["-m", "pip", "install", "--upgrade", "pip"]);
run(py, ["-m", "pip", "install", "-e", ".[dev]"]);
