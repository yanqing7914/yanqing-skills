#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const namePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const reservedDirs = new Set(['.git', '.github', 'templates', 'tools', 'node_modules']);

const entries = fs.readdirSync(root, { withFileTypes: true });
const skillDirs = entries.filter(
  (entry) => entry.isDirectory() && !entry.name.startsWith('.') && !reservedDirs.has(entry.name),
);
const errors = [];

for (const entry of skillDirs) {
  const skillName = entry.name;
  const skillPath = path.join(root, skillName);
  const skillFile = path.join(skillPath, 'SKILL.md');

  if (!namePattern.test(skillName)) {
    errors.push(`${skillName}: directory name must use lowercase letters, numbers, and hyphens`);
  }
  if (!fs.existsSync(skillFile)) {
    errors.push(`${skillName}: missing SKILL.md`);
    continue;
  }

  const content = fs.readFileSync(skillFile, 'utf8');
  const frontMatter = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!frontMatter) {
    errors.push(`${skillName}: SKILL.md must start with YAML front matter`);
    continue;
  }

  const fields = Object.fromEntries(
    frontMatter[1]
      .split(/\r?\n/)
      .filter((line) => /^\w+:\s*.+$/.test(line))
      .map((line) => {
        const index = line.indexOf(':');
        return [line.slice(0, index), line.slice(index + 1).trim()];
      }),
  );

  if (fields.name !== skillName) {
    errors.push(`${skillName}: front matter name must be '${skillName}'`);
  }
  if (!fields.description) {
    errors.push(`${skillName}: front matter description is required`);
  }
}

if (errors.length) {
  console.error('Skill validation failed:');
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`Validated ${skillDirs.length} skill(s).`);
