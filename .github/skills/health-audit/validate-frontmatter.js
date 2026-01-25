#!/usr/bin/env node

/**
 * Validate YAML frontmatter in all SKILL.md files
 *
 * Checks:
 * - Presence of required fields (name, description)
 * - Field constraints (length, format)
 * - Version field present
 */

const fs = require('fs');
const path = require('path');

const SKILLS_DIR = path.join(__dirname, '..');
const MAX_NAME_LENGTH = 64;
const MAX_DESCRIPTION_LENGTH = 1024;

function parseYAMLFrontmatter(content) {
  const frontmatterRegex = /^---\s*\n([\s\S]*?)\n---/;
  const match = content.match(frontmatterRegex);

  if (!match) {
    return null;
  }

  const frontmatter = {};
  const lines = match[1].split('\n');

  for (const line of lines) {
    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) continue;

    const key = line.substring(0, colonIndex).trim();
    const value = line.substring(colonIndex + 1).trim();

    frontmatter[key] = value;
  }

  return frontmatter;
}

function validateSkill(skillPath, skillName) {
  const errors = [];
  const warnings = [];

  const skillFile = path.join(skillPath, 'SKILL.md');

  if (!fs.existsSync(skillFile)) {
    return { errors: [`No SKILL.md found`], warnings: [] };
  }

  const content = fs.readFileSync(skillFile, 'utf8');
  const frontmatter = parseYAMLFrontmatter(content);

  if (!frontmatter) {
    errors.push('No YAML frontmatter found');
    return { errors, warnings };
  }

  // Check required field: name
  if (!frontmatter.name) {
    errors.push('Missing required field: name');
  } else {
    // Validate name format
    if (!/^[a-z0-9\-]+$/.test(frontmatter.name)) {
      errors.push(`Invalid name format: "${frontmatter.name}" (use lowercase, hyphens only)`);
    }

    if (frontmatter.name.length > MAX_NAME_LENGTH) {
      errors.push(`Name too long: ${frontmatter.name.length} chars (max ${MAX_NAME_LENGTH})`);
    }

    // Name should match directory name
    if (frontmatter.name !== skillName) {
      warnings.push(`Name "${frontmatter.name}" doesn't match directory "${skillName}"`);
    }
  }

  // Check required field: description
  if (!frontmatter.description) {
    errors.push('Missing required field: description');
  } else {
    if (frontmatter.description.length > MAX_DESCRIPTION_LENGTH) {
      errors.push(`Description too long: ${frontmatter.description.length} chars (max ${MAX_DESCRIPTION_LENGTH})`);
    }

    // Description should mention "when" or "use"
    if (!/when|use/i.test(frontmatter.description)) {
      warnings.push('Description should mention when to use this skill');
    }
  }

  // Check version field
  if (!frontmatter.version) {
    warnings.push('Missing version field (recommended for tracking changes)');
  } else {
    // Validate semantic versioning format
    if (!/^\d+\.\d+\.\d+$/.test(frontmatter.version)) {
      warnings.push(`Version should follow semantic versioning (x.y.z): "${frontmatter.version}"`);
    }
  }

  return { errors, warnings };
}

function main() {
  console.log('🔍 Validating skill frontmatter...\n');

  const skillDirs = fs.readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .filter(dirent => !dirent.name.startsWith('.'))
    .filter(dirent => dirent.name !== 'health-audit')
    .map(dirent => dirent.name);

  let totalErrors = 0;
  let totalWarnings = 0;
  const results = [];

  for (const skillName of skillDirs) {
    const skillPath = path.join(SKILLS_DIR, skillName);
    const { errors, warnings } = validateSkill(skillPath, skillName);

    if (errors.length > 0 || warnings.length > 0) {
      results.push({ skillName, errors, warnings });
      totalErrors += errors.length;
      totalWarnings += warnings.length;
    }
  }

  // Print results
  if (results.length === 0) {
    console.log('✅ All skills have valid frontmatter!\n');
    console.log(`📊 Validated ${skillDirs.length} skills`);
    process.exit(0);
  }

  console.log('❌ Found issues:\n');

  for (const { skillName, errors, warnings } of results) {
    console.log(`📁 ${skillName}/`);

    if (errors.length > 0) {
      errors.forEach(error => {
        console.log(`   ❌ ERROR: ${error}`);
      });
    }

    if (warnings.length > 0) {
      warnings.forEach(warning => {
        console.log(`   ⚠️  WARNING: ${warning}`);
      });
    }

    console.log('');
  }

  console.log('📊 Summary:');
  console.log(`   Total skills: ${skillDirs.length}`);
  console.log(`   Skills with issues: ${results.length}`);
  console.log(`   Errors: ${totalErrors}`);
  console.log(`   Warnings: ${totalWarnings}\n`);

  // Exit with error if there are errors
  process.exit(totalErrors > 0 ? 1 : 0);
}

main();
