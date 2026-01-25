#!/usr/bin/env node

/**
 * Message Key Audit Script
 * Finds missing translations between EN and FR message files
 */

const fs = require('fs');
const path = require('path');

// Paths to message files (adjust based on your project structure)
const MESSAGES_DIR = path.join(process.cwd(), 'messages');
const EN_FILE = path.join(MESSAGES_DIR, 'en.json');
const FR_FILE = path.join(MESSAGES_DIR, 'fr.json');

function loadMessages(filePath) {
  if (!fs.existsSync(filePath)) {
    console.error(`❌ File not found: ${filePath}`);
    process.exit(1);
  }

  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    console.error(`❌ Failed to parse JSON: ${filePath}`);
    console.error(error.message);
    process.exit(1);
  }
}

function flattenKeys(obj, prefix = '') {
  const keys = [];

  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;

    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      keys.push(...flattenKeys(value, fullKey));
    } else {
      keys.push(fullKey);
    }
  }

  return keys;
}

function findMissingKeys(sourceKeys, targetKeys, sourceLang, targetLang) {
  const missingKeys = sourceKeys.filter(key => !targetKeys.includes(key));

  if (missingKeys.length === 0) {
    console.log(`✅ All ${sourceLang} keys have ${targetLang} translations`);
    return [];
  }

  console.log(`\n❌ Missing ${targetLang} translations (${missingKeys.length}):`);
  missingKeys.forEach(key => {
    console.log(`   - ${key}`);
  });

  return missingKeys;
}

function main() {
  console.log('🔍 Auditing i18n message keys...\n');

  const enMessages = loadMessages(EN_FILE);
  const frMessages = loadMessages(FR_FILE);

  const enKeys = flattenKeys(enMessages);
  const frKeys = flattenKeys(frMessages);

  console.log(`📊 Statistics:`);
  console.log(`   EN keys: ${enKeys.length}`);
  console.log(`   FR keys: ${frKeys.length}`);

  const missingFr = findMissingKeys(enKeys, frKeys, 'EN', 'FR');
  const missingEn = findMissingKeys(frKeys, enKeys, 'FR', 'EN');

  const totalMissing = missingFr.length + missingEn.length;

  if (totalMissing === 0) {
    console.log('\n✅ All translations are complete!');
    process.exit(0);
  } else {
    console.log(`\n⚠️  Total missing translations: ${totalMissing}`);
    process.exit(1);
  }
}

main();
