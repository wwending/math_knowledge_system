import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const installScriptNames = ["preinstall", "install", "postinstall"];
const nodeModulesPath = path.resolve("node_modules");
const findings = new Map();

async function inspectPackage(packagePath) {
  const packageJsonPath = path.join(packagePath, "package.json");

  try {
    const packageJson = JSON.parse(await readFile(packageJsonPath, "utf8"));
    const scripts = installScriptNames.filter(
      (scriptName) => typeof packageJson.scripts?.[scriptName] === "string",
    );

    if (scripts.length > 0) {
      const name = packageJson.name ?? path.basename(packagePath);
      const version = packageJson.version ?? "unknown";
      const key = `${name}\u0000${version}\u0000${scripts.join(",")}`;
      findings.set(key, { name, version, scripts });
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw new Error(`Unable to inspect ${packageJsonPath}: ${error.message}`);
    }
  }

  await walkNodeModules(path.join(packagePath, "node_modules"), true);
}

async function walkNodeModules(directory, allowMissing = false) {
  let entries;

  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (allowMissing && error?.code === "ENOENT") {
      return;
    }
    throw error;
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) {
      continue;
    }

    const entryPath = path.join(directory, entry.name);
    if (entry.name.startsWith("@")) {
      const scopedPackages = await readdir(entryPath, { withFileTypes: true });
      for (const scopedPackage of scopedPackages) {
        if (scopedPackage.isDirectory()) {
          await inspectPackage(path.join(entryPath, scopedPackage.name));
        }
      }
      continue;
    }

    await inspectPackage(entryPath);
  }
}

try {
  await walkNodeModules(nodeModulesPath);
} catch (error) {
  if (error?.code === "ENOENT") {
    console.error("node_modules was not found; install dependencies before running this check.");
    process.exitCode = 1;
  } else {
    throw error;
  }
}

if (process.exitCode !== 1) {
  const sortedFindings = [...findings.values()].sort(
    (left, right) =>
      left.name.localeCompare(right.name) || left.version.localeCompare(right.version),
  );

  console.log("PACKAGE\tVERSION\tINSTALL_SCRIPTS");
  for (const finding of sortedFindings) {
    console.log(`${finding.name}\t${finding.version}\t${finding.scripts.join(",")}`);
  }
  console.log(`Total packages declaring install lifecycle scripts: ${sortedFindings.length}`);
}
