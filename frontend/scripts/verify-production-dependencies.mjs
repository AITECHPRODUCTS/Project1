import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const failures = [];
const configPath = path.join(root, "next.config.ts");
if (!existsSync(configPath)) {
  failures.push("next.config.ts is missing");
} else if (!/images\s*:\s*\{\s*unoptimized\s*:\s*true\s*\}/s.test(readFileSync(configPath, "utf8"))) {
  failures.push("Next image optimization must remain disabled while sharp/libvips is excluded");
}

const sourceRoots = ["app", "components", "lib", "pages"]
  .map((part) => path.join(root, part))
  .filter((dir) => existsSync(dir));
const codeExtensions = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);
const forbiddenImageImport = /\bfrom\s*["']next\/image["']|\brequire\s*\(\s*["']next\/image["']\s*\)|<Image\b/;
const scannedFiles = [];
function scanDirectory(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const absolute = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!["node_modules", ".next", ".git", "dist", "coverage"].includes(entry.name)) scanDirectory(absolute);
      continue;
    }
    if (!codeExtensions.has(path.extname(entry.name))) continue;
    const source = readFileSync(absolute, "utf8");
    scannedFiles.push(path.relative(root, absolute));
    if (forbiddenImageImport.test(source)) {
      failures.push(path.relative(root, absolute) + " uses next/image; review image optimization and native package licensing first");
    }
  }
}
for (const dir of sourceRoots) scanDirectory(dir);

if (!existsSync(path.join(root, ".next", "BUILD_ID"))) failures.push("Next production build output .next/BUILD_ID is missing");
if (!existsSync(path.join(root, "node_modules", "next", "package.json"))) failures.push("Next.js runtime dependency is missing");

const nativePackageRoot = path.join(root, "node_modules");
const prohibitedInstalledPackages = [];
if (existsSync(path.join(nativePackageRoot, "sharp"))) prohibitedInstalledPackages.push("sharp");
const scopedImagePackages = path.join(nativePackageRoot, "@img");
if (existsSync(scopedImagePackages)) {
  for (const name of readdirSync(scopedImagePackages)) {
    if (/^sharp(?:-|$)/.test(name)) prohibitedInstalledPackages.push("@img/" + name);
  }
}
if (prohibitedInstalledPackages.length) {
  failures.push("Production runtime still contains optional native image packages: " + prohibitedInstalledPackages.join(", "));
}

if (failures.length) {
  for (const failure of failures) console.error("PRODUCTION DEPENDENCY BOUNDARY: " + failure);
  process.exitCode = 1;
} else {
  console.log(JSON.stringify({
    status: "verified",
    scope: "frontend production runtime tree",
    nextImageImports: 0,
    sharpInstalled: false,
    libvipsNativePackagesInstalled: false,
    sourceFilesScanned: scannedFiles.length,
    productionBuildPresent: true,
  }, null, 2));
}
