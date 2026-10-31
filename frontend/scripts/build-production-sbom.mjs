import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const [sourcePath, outputPath] = process.argv.slice(2);
if (!sourcePath || !outputPath) {
  console.error("Usage: node scripts/build-production-sbom.mjs <full-build-sbom.json> <production-sbom.json>");
  process.exit(2);
}
const source = path.resolve(sourcePath);
const output = path.resolve(outputPath);
if (!existsSync(source)) throw new Error("The full build/install SBOM does not exist: " + source);
const bom = JSON.parse(readFileSync(source, "utf8"));
if (bom.bomFormat !== "CycloneDX" || !Array.isArray(bom.components)) {
  throw new Error("Expected a CycloneDX SBOM with a components array");
}

const installedPackages = new Set();
const visitedModuleDirs = new Set();
function readPackage(packageDir) {
  const manifestPath = path.join(packageDir, "package.json");
  if (!existsSync(manifestPath)) return;
  try {
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    if (typeof manifest.name === "string" && typeof manifest.version === "string") {
      installedPackages.add(manifest.name + "@" + manifest.version);
    }
  } catch (error) {
    throw new Error("Cannot read installed package manifest " + manifestPath + ": " + String(error));
  }
  const nestedModules = path.join(packageDir, "node_modules");
  if (existsSync(nestedModules)) visitNodeModules(nestedModules);
}

function visitNodeModules(modulesDir) {
  if (!existsSync(modulesDir) || visitedModuleDirs.has(modulesDir)) return;
  visitedModuleDirs.add(modulesDir);
  for (const entry of readdirSync(modulesDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === ".bin" || entry.name === ".cache") continue;
    const entryPath = path.join(modulesDir, entry.name);
    if (entry.name.startsWith("@")) {
      for (const scoped of readdirSync(entryPath, { withFileTypes: true })) {
        if (scoped.isDirectory()) readPackage(path.join(entryPath, scoped.name));
      }
    } else {
      readPackage(entryPath);
    }
  }
}

visitNodeModules(path.resolve("node_modules"));
if (!installedPackages.has("next@" + JSON.parse(readFileSync(path.join("node_modules", "next", "package.json"), "utf8")).version)) {
  throw new Error("The actual production tree does not contain Next.js");
}

const originalComponents = bom.components;
const productionComponents = originalComponents.filter((component) =>
  typeof component.name === "string" &&
  typeof component.version === "string" &&
  installedPackages.has(component.name + "@" + component.version)
);
if (!productionComponents.length) throw new Error("Filtering produced an empty production component set");

const prohibited = productionComponents.filter((component) =>
  component.name === "sharp" || /^@img\/sharp(?:-|$)/.test(component.name)
);
if (prohibited.length) {
  throw new Error("Production SBOM still contains forbidden optional native image packages: " +
    prohibited.map((component) => component.name + "@" + component.version).join(", "));
}

const allowedRefs = new Set(productionComponents.map((component) => component["bom-ref"]).filter(Boolean));
const rootRef = bom.metadata?.component?.["bom-ref"];
if (rootRef) allowedRefs.add(rootRef);
const filteredDependencies = Array.isArray(bom.dependencies)
  ? bom.dependencies
      .filter((dependency) => allowedRefs.has(dependency.ref))
      .map((dependency) => ({
        ...dependency,
        dependsOn: (dependency.dependsOn || []).filter((ref) => allowedRefs.has(ref)),
      }))
  : [];

const productionBom = {
  ...bom,
  components: productionComponents,
  dependencies: filteredDependencies,
};
writeFileSync(output, JSON.stringify(productionBom, null, 2) + "\n", "utf8");
console.log(JSON.stringify({
  status: "generated",
  scope: "production node_modules installed package set",
  source_components: originalComponents.length,
  production_components: productionComponents.length,
  filtered_build_only_components: originalComponents.length - productionComponents.length,
  installed_packages_seen: installedPackages.size,
  sharp_or_libvips_components: prohibited.length,
  output,
}, null, 2));
