#!/usr/bin/env node
/**
 * WCAG 2.1 Token Contrast Verification Script for RefMotion Design System.
 * Parses frontend/src/index.css directly and verifies:
 *  - body text (--text) vs (--bg, --surface, --surface-2) >= 4.5:1
 *  - muted text (--text-muted) vs (--bg, --surface, --surface-2) >= 4.5:1
 *  - UI border (--border-ui) & semantic accents/icons vs (--bg, --surface, --surface-2) >= 3.0:1
 *  - primary button foreground vs button background >= 4.5:1
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cssPath = path.join(__dirname, "src", "index.css");
const cssContent = fs.readFileSync(cssPath, "utf8");

function parseBlock(selectorRegex) {
  const match = cssContent.match(selectorRegex);
  if (!match) throw new Error(`Could not find CSS block for ${selectorRegex}`);
  const body = match[1];
  const tokens = {};
  const lineRegex = /(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g;
  let m;
  while ((m = lineRegex.exec(body)) !== null) {
    tokens[m[1]] = m[2].toLowerCase();
  }
  return tokens;
}

const THEMES = {
  dark: parseBlock(/html\[data-theme="dark"\]\s*\{([^}]+)\}/),
  light: parseBlock(/html\[data-theme="light"\]\s*\{([^}]+)\}/),
};

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function relativeLuminance([r, g, b]) {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function contrastRatio(hex1, hex2) {
  const l1 = relativeLuminance(hexToRgb(hex1));
  const l2 = relativeLuminance(hexToRgb(hex2));
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

let failures = 0;

for (const [themeName, tokens] of Object.entries(THEMES)) {
  console.log(`\n=== Checking Theme: ${themeName.toUpperCase()} ===`);
  const backgrounds = ["--bg", "--surface", "--surface-2"];

  for (const bgKey of backgrounds) {
    const bgHex = tokens[bgKey];

    // 1. Body text >= 4.5:1
    const textRatio = contrastRatio(tokens["--text"], bgHex);
    const textPass = textRatio >= 4.5;
    if (!textPass) failures++;
    console.log(
      `  [${textPass ? "PASS" : "FAIL"}] --text (${tokens["--text"]}) on ${bgKey} (${bgHex}): ${textRatio.toFixed(2)}:1 (min 4.5:1)`
    );

    // 2. Muted text >= 4.5:1
    const mutedRatio = contrastRatio(tokens["--text-muted"], bgHex);
    const mutedPass = mutedRatio >= 4.5;
    if (!mutedPass) failures++;
    console.log(
      `  [${mutedPass ? "PASS" : "FAIL"}] --text-muted (${tokens["--text-muted"]}) on ${bgKey} (${bgHex}): ${mutedRatio.toFixed(2)}:1 (min 4.5:1)`
    );

    // 3. UI icons / accents / status / borders >= 3.0:1
    for (const uiKey of [
      "--accent",
      "--accent-2",
      "--success",
      "--warning",
      "--danger",
      "--focus-ring",
      "--border-ui",
    ]) {
      const ratio = contrastRatio(tokens[uiKey], bgHex);
      const pass = ratio >= 3.0;
      if (!pass) failures++;
      console.log(
        `  [${pass ? "PASS" : "FAIL"}] ${uiKey} (${tokens[uiKey]}) on ${bgKey} (${bgHex}): ${ratio.toFixed(2)}:1 (min 3.0:1)`
      );
    }
  }

  // 4. Button foreground vs button background >= 4.5:1
  for (const [btnBg, btnFg] of [
    ["--accent-btn", "--accent-btn-text"],
    ["--accent-2-btn", "--accent-2-btn-text"],
  ]) {
    const r = contrastRatio(tokens[btnFg], tokens[btnBg]);
    const p = r >= 4.5;
    if (!p) failures++;
    console.log(
      `  [${p ? "PASS" : "FAIL"}] ${btnFg} (${tokens[btnFg]}) on ${btnBg} (${tokens[btnBg]}): ${r.toFixed(2)}:1 (min 4.5:1)`
    );
  }
}

if (failures > 0) {
  console.error(`\nContrast check FAILED with ${failures} violation(s).`);
  process.exit(1);
} else {
  console.log("\nAll WCAG token contrast checks PASSED (0 violations).");
}
