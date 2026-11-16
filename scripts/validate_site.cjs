#!/usr/bin/env node
'use strict';
/** Offline static checks for the published v2 pages. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..', 'v2');
const pages = ['index.html', 'spiele.html', 'vereine.html', 'tabellen.html', 'daten.html'];
let checks = 0;
for (const page of pages) {
  const html = fs.readFileSync(path.join(root, page), 'utf8');
  if (!/<html\b/i.test(html) || !/<title>[^<]+<\/title>/i.test(html)) throw Error(page + ': invalid HTML skeleton');
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
  for (const [, code] of scripts) {
    if (code.trim()) {
      new vm.Script(code, {filename: page});
      checks++;
    }
  }
  for (const [, link] of html.matchAll(/\bhref=["']([^"'#?]+\.html)(?:[?#][^"']*)?["']/gi)) {
    if (!fs.existsSync(path.join(root, link))) throw Error(page + ': broken link ' + link);
    checks++;
  }
  if (!html.includes('daten.html') && page !== 'daten.html') throw Error(page + ': missing methodology link');
  checks++;
  console.log('OK ' + page);
}
for (const filename of ['countries.json', 'clubs.json', 'fixtures.json']) {
  const file = JSON.parse(fs.readFileSync(path.join(root, 'data', filename), 'utf8'));
  if (!Array.isArray(file.rows) || file.rows.length !== file.count) throw Error(filename + ': row count mismatch');
  checks++;
}
console.log('Passed ' + checks + ' offline checks.');
