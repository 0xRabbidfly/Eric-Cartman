#!/usr/bin/env node

/**
 * Check cross-references in SKILL.md files
 *
 * Validates:
 * - Referenced supporting files exist
 * - Referenced skills exist
 * - External file paths are valid
 */

const fs = require('fs');
const path = require('path');

const SKILLS_DIR = path.join(__dirname, '..');
const PROJECT_ROOT = path.join(SKILLS_DIR, '..', '..');

function extractReferences(content, skillPath) {
  const refs = {
    supportingFiles: [],
    skills: [],
    projectFiles: [],
  };

  // Extract "See: filename.md" or **See**: `filename.md`
  const seePattern = /(?:See|see):\s*`([^`]+)`/g;
  let match;
  while ((match = seePattern.exec(content)) !== null) {
    refs.supportingFiles.push(match[1]);
  }

  // Extract skill references like `skill-name` in Related Skills section
  const relatedSkillsSection = content.match(/## Related Skills\s+([\s\S]*?)(?=\n##|$)/);
  if (relatedSkillsSection) {
    const skillPattern = /`([a-z0-9\-]+)`/g;
    while ((match = skillPattern.exec(relatedSkillsSection[1])) !== null) {
      refs.skills.push(match[1]);
    }
  }

  // Extract project file references (paths starting with specs/, design/, etc.)
  const projectFilePattern = /`((?:specs|design|app|lib|tests|components)\/[^`]+)`/g;
  while ((match = projectFilePattern.exec(content)) !== null) {
    refs.projectFiles.push(match[1]);
  }

  return refs;
}

function validateReferences(skillName, skillPath, refs) {
  const issues = [];

  // Check supporting files
  for (const file of refs.supportingFiles) {
    const filePath = path.join(skillPath, file);

    if (!fs.existsSync(filePath)) {
      issues.push({
        type: 'missing-file',
        message: `Referenced file not found: ${file}`,
      });
    }
  }

  // Check referenced skills
  for (const refSkill of refs.skills) {
    const refSkillPath = path.join(SKILLS_DIR, refSkill);

    if (!fs.existsSync(refSkillPath)) {
      issues.push({
        type: 'missing-skill',
        message: `Referenced skill not found: ${refSkill}`,
      });
    }
  }

  // Check project files
  for (const file of refs.projectFiles) {
    const filePath = path.join(PROJECT_ROOT, file);

    if (!fs.existsSync(filePath)) {
      issues.push({
        type: 'missing-project-file',
        message: `Referenced project file not found: ${file}`,
      });
    }
  }

  return issues;
}

function main() {
  console.log('🔍 Checking cross-references...\n');

  const skillDirs = fs.readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .filter(dirent => !dirent.name.startsWith('.'))
    .filter(dirent => dirent.name !== 'health-audit')
    .map(dirent => dirent.name);

  let totalIssues = 0;
  const results = [];

  for (const skillName of skillDirs) {
    const skillPath = path.join(SKILLS_DIR, skillName);
    const skillFile = path.join(skillPath, 'SKILL.md');

    if (!fs.existsSync(skillFile)) {
      continue;
    }

    const content = fs.readFileSync(skillFile, 'utf8');
    const refs = extractReferences(content, skillPath);
    const issues = validateReferences(skillName, skillPath, refs);

    if (issues.length > 0) {
      results.push({
        skillName,
        refs,
        issues,
      });
      totalIssues += issues.length;
    }
  }

  // Print results
  if (results.length === 0) {
    console.log('✅ All cross-references are valid!\n');
    console.log(`📊 Validated ${skillDirs.length} skills`);
    process.exit(0);
  }

  console.log('❌ Found broken references:\n');

  for (const { skillName, refs, issues } of results) {
    console.log(`📁 ${skillName}/`);
    console.log(`   References found:`);
    console.log(`   - Supporting files: ${refs.supportingFiles.length}`);
    console.log(`   - Skills: ${refs.skills.length}`);
    console.log(`   - Project files: ${refs.projectFiles.length}`);
    console.log('');

    issues.forEach(issue => {
      const icon = issue.type === 'missing-file' ? '📄' :
                   issue.type === 'missing-skill' ? '🔗' : '📂';
      console.log(`   ${icon} ${issue.message}`);
    });

    console.log('');
  }

  console.log('📊 Summary:');
  console.log(`   Total skills: ${skillDirs.length}`);
  console.log(`   Skills with broken refs: ${results.length}`);
  console.log(`   Total broken refs: ${totalIssues}\n`);

  process.exit(totalIssues > 0 ? 1 : 0);
}

main();
