#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const skillsDir = path.join(root, 'skills');
const namePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

if (!fs.existsSync(skillsDir)) {
  console.error('Missing skills/ directory.');
  process.exit(1);
}

const entries = fs.readdirSync(skillsDir, { withFileTypes: true });
const skillDirs = entries.filter((entry) => entry.isDirectory());
const errors = [];

for (const entry of skillDirs) {
  const skillName = entry.name;
  const skillPath = path.join(skillsDir, skillName);
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
