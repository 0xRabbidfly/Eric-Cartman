---
name: i18n
description: Bilingual EN/FR content validation using next-intl. Use when adding translated content, testing language switching, or validating message key coverage before deployment.
---

# i18n Validation Skill

## Purpose

Validate bilingual content completeness and correctness for EN/FR localization in the AI-HUB-Portal using next-intl.

## When to Use

- Adding new UI strings or content
- Before production deployment (validate translation coverage)
- Testing language switching functionality
- Reviewing translation completeness
- Debugging missing or incorrect translations

## Validation Checklist

### 1. Message Key Coverage

**Verify all keys exist in both languages:**

```bash
# Run message key audit
node .github/skills/i18n/message-key-audit.js
```

Expected output:
```
✓ All EN keys have FR translations
✓ All FR keys have EN equivalents
✗ Missing translations:
  - HomePage.newFeature (missing FR)
  - Navigation.logout (missing EN)
```

### 2. No Hardcoded Strings

**Bad:**
```tsx
<h1>Welcome to AI Hub</h1>  // Hardcoded English
```

**Good:**
```tsx
import { useTranslations } from 'next-intl';

const t = useTranslations('HomePage');
<h1>{t('welcome')}</h1>
```

### 3. Locale-Aware Formatting

```tsx
// Dates
<p>{format(new Date(), 'PPP', { locale })}</p>

// Numbers
<p>{new Intl.NumberFormat(locale).format(1234567)}</p>
```

### 4. Language Switching

Test both languages load correctly:

```bash
# Run E2E language switching test
npm run test:e2e -- i18n-test-template.ts
```

## Quick Reference

| Task | Command/Pattern |
|------|-----------------|
| Find missing keys | `node message-key-audit.js` |
| Add new message | Update `messages/en.json` and `messages/fr.json` |
| Test language switch | Use E2E template |
| Validate pluralization | Check `{count, plural, ...}` syntax |

## Common Issues

**Issue**: Text not translating
- Check message key exists in both `en.json` and `fr.json`
- Verify `useTranslations` namespace matches file structure

**Issue**: Language switch not working
- Verify locale cookie is being set
- Check middleware configuration

**See**: `i18n-test-template.ts` for E2E test template

## Related Skills

- `testing` - Use for comprehensive i18n testing
- `code-review` - Validates no hardcoded strings
- `deployment` - Verify translations before production

## Supporting Files

- `message-key-audit.js` - Script to find missing translations
- `i18n-test-template.ts` - E2E test template for language switching
