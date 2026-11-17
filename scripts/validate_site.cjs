#!/usr/bin/env node
'use strict';
/** Offline static checks for the published v2 pages. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..', 'v2');
const pages = ['index.html', 'spiele.html', 'vereine.html', 'tabellen.html', 'daten.html', 'nations-league.html'];
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
// Eurocoeff club ranking: descending score is the default, equal scores share rank.
const clubsPayload = JSON.parse(fs.readFileSync(path.join(root, 'data', 'clubs.json'), 'utf8'));
const clubRows = clubsPayload.rows;
if (clubsPayload.source !== 'https://eurocoeff.com/en/rankings/clubs/' ||
    clubRows.length < 100 ||
    clubRows.some(x => !Number.isFinite(x.score) || !Number.isInteger(x.rank))) {
  throw Error('clubs.json: invalid Eurocoeff ranking');
}
const sortedClubs = [...clubRows].sort((a,b) => b.score - a.score || a.rank - b.rank || a.name.localeCompare(b.name));
for (let i=0; i<sortedClubs.length; i++) {
  const expected = i && sortedClubs[i].score === sortedClubs[i-1].score ? sortedClubs[i-1].rank : i+1;
  if (sortedClubs[i].rank !== expected && !(i && sortedClubs[i].score === sortedClubs[i-1].score && sortedClubs[i].rank === i+1)) throw Error('clubs.json: Eurocoeff rank/score mismatch at '+i);
}
const clubsPage = fs.readFileSync(path.join(root,'vereine.html'),'utf8');
if (!/<option value="score">Höchste Punkte zuerst<\/option>/.test(clubsPage) ||
    !clubsPage.includes('b.score-a.score')) throw Error('vereine.html: default club ranking must be descending');
checks += 3;
// All three UEFA men's club competitions must be explicitly represented.
const requiredCompetitions = ['UCL','UEL','UECL'];
const presentCompetitions = new Set(fixturePayloadPlaceholder());
function fixturePayloadPlaceholder() {
  return JSON.parse(fs.readFileSync(path.join(root,'data','fixtures.json'),'utf8')).rows.map(x=>x.competition);
}
for (const competition of requiredCompetitions) {
  if (!presentCompetitions.has(competition)) throw Error('fixtures.json: missing '+competition);
  checks++;
}
// Cross-check the 3/1/0 partial standings against every recorded match.
const fixturePayload = JSON.parse(fs.readFileSync(path.join(root, 'data', 'fixtures.json'), 'utf8'));
const fixtures = fixturePayload.rows;
for (const competition of ['UCL', 'UEL', 'UECL']) {
  for (const season of ['2025/26', '2026/27']) {
    const matches = fixtures.filter(x => x.season === season && x.competition === competition);
    const played = matches.filter(x => x.status === 'finished');
    const clubs = new Map();
    const get = name => {
      if (!clubs.has(name)) clubs.set(name, {p: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, pts: 0});
      return clubs.get(name);
    };
    for (const match of matches) {get(match.home); get(match.away);}
    for (const match of played) {
      const h = get(match.home), a = get(match.away);
      h.p++; a.p++; h.gf += match.hg; h.ga += match.ag;
      a.gf += match.ag; a.ga += match.hg;
      if (match.hg > match.ag) {h.w++; a.l++; h.pts += 3;}
      else if (match.hg < match.ag) {a.w++; h.l++; a.pts += 3;}
      else {h.d++; a.d++; h.pts++; a.pts++;}
    }
    const stats = [...clubs.values()];
    const sum = key => stats.reduce((n, x) => n + x[key], 0);
    const homeGoals = played.reduce((n, x) => n + x.hg, 0);
    const awayGoals = played.reduce((n, x) => n + x.ag, 0);
    if (sum('p') !== played.length * 2 || sum('w') !== sum('l') ||
        sum('d') !== played.filter(x => x.hg === x.ag).length * 2 ||
        sum('gf') !== homeGoals + awayGoals || sum('ga') !== sum('gf') ||
        sum('pts') !== sum('w') * 3 + sum('d') ||
        stats.some(x => x.p !== x.w + x.d + x.l)) {
      throw Error(season + ' ' + competition + ': inconsistent match statistics');
    }
    checks++;
  }
}
console.log('Passed ' + checks + ' offline checks.');
