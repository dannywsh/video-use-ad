"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const SKILL_NAME = "video-use";

function skillRootDir() {
  return path.resolve(__dirname, "..");
}

function userEnvPath() {
  const explicit = (process.env.VIDEO_USE_ENV || "").trim();
  if (explicit) return explicit;
  const xdg = (process.env.XDG_CONFIG_HOME || "").trim();
  if (xdg) return path.join(xdg, SKILL_NAME, ".env");
  return path.join(os.homedir(), ".config", SKILL_NAME, ".env");
}

function envFiles(skillRoot) {
  const root = skillRoot || skillRootDir();
  const ordered = [userEnvPath(), path.join(root, ".env"), path.join(process.cwd(), ".env")];
  const seen = new Set();
  const unique = [];
  for (const file of ordered) {
    if (seen.has(file)) continue;
    seen.add(file);
    unique.push(file);
  }
  return unique;
}

function parseDotEnv(filePath) {
  if (!fs.existsSync(filePath)) return {};
  let text = fs.readFileSync(filePath, "utf8");
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const values = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const eq = line.indexOf("=");
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function migrateSkillRootEnv(skillRoot) {
  const root = skillRoot || skillRootDir();
  const source = path.join(root, ".env");
  const dest = userEnvPath();
  if (!fs.existsSync(source) || fs.existsSync(dest)) return null;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(source, dest);
  try {
    fs.chmodSync(dest, 0o600);
  } catch {
    // Windows cannot apply Unix 0600; the file is still usable.
  }
  return dest;
}

function loadEnvValue(name, skillRoot) {
  migrateSkillRootEnv(skillRoot);
  for (const file of envFiles(skillRoot)) {
    const value = (parseDotEnv(file)[name] || "").trim();
    if (value) return value;
  }
  return (process.env[name] || "").trim();
}

module.exports = {
  skillRootDir,
  userEnvPath,
  envFiles,
  parseDotEnv,
  migrateSkillRootEnv,
  loadEnvValue,
};
