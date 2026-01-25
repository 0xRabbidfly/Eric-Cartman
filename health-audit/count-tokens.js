#!/usr/bin/env node

/**
 * Count tokens in all SKILL.md files
 *
 * Validates:
 * - Main SKILL.md files stay under 5,000 token threshold
 * - Supporting files are tracked but not limited
 * - Token distribution across skill hierarchy
 */

const fs = require('fs');
const path = require('path');

const SKILLS_DIR = path.join(__dirname, '..');
const MAX_TOKENS_MAIN = 5000;
const RECOMMENDED_MIN = 200;
const RECOMMENDED_MAX = 325;

function estimateTokens(content) {
  // Simple estimation: word count * 1.3
  // This approximates typical English text tokenization
  const wordCount = content.split(/\s+/).length;
  return Math.round(wordCount * 1.3);
}

function countLinesAndTokens(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n').length;
  const tokens = estimateTokens(content);
  return { lines, tokens };
}

function analyzeSkill(skillName, skillPath) {
  const skillFile = path.join(skillPath, 'SKILL.md');

  if (!fs.existsSync(skillFile)) {
    return null;
  }

  const mainStats = countLinesAndTokens(skillFile);

  // Find supporting files
  const supportingFiles = [];
  const entries = fs.readdirSync(skillPath, { withFileTypes: true });

  for (const entry of entries) {
    if (entry.name === 'SKILL.md') continue;

    const entryPath = path.join(skillPath, entry.name);

    if (entry.isFile() && (entry.name.endsWith('.md') || entry.name.endsWith('.ts') || entry.name.endsWith('.js'))) {
      const stats = countLinesAndTokens(entryPath);
      supportingFiles.push({
        name: entry.name,
        ...stats,
      });
    } else if (entry.isDirectory()) {
      // Recursively count files in subdirectories
      const subFiles = fs.readdirSync(entryPath, { withFileTypes: true })
        .filter(f => f.isFile() && (f.name.endsWith('.md') || f.name.endsWith('.ts') || f.name.endsWith('.js')))
        .map(f => {
          const subPath = path.join(entryPath, f.name);
          const stats = countLinesAndTokens(subPath);
          return {
            name: `${entry.name}/${f.name}`,
            ...stats,
          };
        });
      supportingFiles.push(...subFiles);
    }
  }

  const totalSupportingTokens = supportingFiles.reduce((sum, f) => sum + f.tokens, 0);

  return {
    skillName,
    main: mainStats,
    supporting: supportingFiles,
    totalTokens: mainStats.tokens + totalSupportingTokens,
  };
}

function main() {
  console.log('📊 Counting tokens in skills...\n');

  const skillDirs = fs.readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .filter(dirent => !dirent.name.startsWith('.'))
    .filter(dirent => dirent.name !== 'health-audit')
    .map(dirent => dirent.name);

  const results = [];
  let totalSkills = 0;
  let issueCount = 0;

  for (const skillName of skillDirs) {
    const skillPath = path.join(SKILLS_DIR, skillName);
    const analysis = analyzeSkill(skillName, skillPath);

    if (analysis) {
      results.push(analysis);
      totalSkills++;

      if (analysis.main.tokens > MAX_TOKENS_MAIN) {
        issueCount++;
      }
    }
  }

  // Sort by main file token count (descending)
  results.sort((a, b) => b.main.tokens - a.main.tokens);

  // Print summary table
  console.log('📋 Token Count Summary\n');
  console.log('Skill                    Main Tokens  Lines  Supporting Files  Total Tokens  Status');
  console.log('─'.repeat(95));

  for (const { skillName, main, supporting, totalTokens } of results) {
    const status = main.tokens > MAX_TOKENS_MAIN ? '❌ TOO LARGE' :
                   main.tokens < RECOMMENDED_MIN ? '⚠️  TOO SMALL' :
                   main.tokens > RECOMMENDED_MAX ? '⚠️  LARGE' : '✅ OK';

    const supportingCount = supporting.length;
    const mainTokenStr = main.tokens.toString().padStart(10);
    const linesStr = main.lines.toString().padStart(6);
    const supportingStr = supportingCount.toString().padStart(16);
    const totalStr = totalTokens.toString().padStart(13);

    console.log(`${skillName.padEnd(24)} ${mainTokenStr} ${linesStr} ${supportingStr} ${totalStr}  ${status}`);
  }

  console.log('─'.repeat(95));
  console.log(`Total Skills: ${totalSkills}`);
  console.log('');

  // Print issues
  const oversizedSkills = results.filter(r => r.main.tokens > MAX_TOKENS_MAIN);
  const undersizedSkills = results.filter(r => r.main.tokens < RECOMMENDED_MIN);
  const largeSkills = results.filter(r => r.main.tokens > RECOMMENDED_MAX && r.main.tokens <= MAX_TOKENS_MAIN);

  if (oversizedSkills.length > 0) {
    console.log('❌ Skills exceeding 5,000 token limit:\n');
    for (const { skillName, main } of oversizedSkills) {
      console.log(`   ${skillName}: ${main.tokens} tokens (${main.lines} lines)`);
      console.log(`   → Should extract content to supporting files`);
      console.log('');
    }
  }

  if (largeSkills.length > 0) {
    console.log('⚠️  Skills above recommended range (325 tokens):\n');
    for (const { skillName, main } of largeSkills) {
      console.log(`   ${skillName}: ${main.tokens} tokens (${main.lines} lines)`);
      console.log(`   → Consider extracting detailed examples or reference material`);
      console.log('');
    }
  }

  if (undersizedSkills.length > 0) {
    console.log('⚠️  Skills below recommended range (200 tokens):\n');
    for (const { skillName, main } of undersizedSkills) {
      console.log(`   ${skillName}: ${main.tokens} tokens (${main.lines} lines)`);
      console.log(`   → May need more context or examples`);
      console.log('');
    }
  }

  // Print supporting files breakdown for oversized skills
  if (oversizedSkills.length > 0) {
    console.log('📁 Supporting Files Breakdown:\n');
    for (const { skillName, supporting } of oversizedSkills) {
      if (supporting.length > 0) {
        console.log(`   ${skillName}/`);
        for (const file of supporting) {
          console.log(`      ${file.name}: ${file.tokens} tokens (${file.lines} lines)`);
        }
        console.log('');
      }
    }
  }

  // Print recommendations
  console.log('💡 Recommendations:\n');
  console.log(`   Target range for main SKILL.md: ${RECOMMENDED_MIN}-${RECOMMENDED_MAX} tokens`);
  console.log(`   Hard limit for main SKILL.md: ${MAX_TOKENS_MAIN} tokens`);
  console.log('   Supporting files: No limit (loaded on-demand)');
  console.log('');
  console.log('   Progressive disclosure pattern:');
  console.log('   1. SKILL.md = Essential workflow + quick start');
  console.log('   2. pattern-*.md = Detailed examples and patterns');
  console.log('   3. templates/ = Copy-paste code templates');
  console.log('');

  // Exit with error if any skills exceed hard limit
  process.exit(oversizedSkills.length > 0 ? 1 : 0);
}

main();
