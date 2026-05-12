#!/usr/bin/env node
/**
 * Chạy Postman collection bằng Newman và ghi kết quả pass/fail vào CSV.
 *
 * Usage:
 *   node run_tests.js                        # chạy toàn bộ collection
 *   node run_tests.js --folder 01_Auth       # chỉ chạy folder cụ thể
 *   node run_tests.js --env ./env.json       # dùng environment file khác
 */

const newman = require('newman');
const fs = require('fs');
const path = require('path');

// ── Paths ─────────────────────────────────────────────────────────────────────
const ROOT = __dirname;
const COLLECTION = path.join(ROOT, 'collections', 'Educational_Platform_API_Tests.postman_collection.json');
const ENVIRONMENT = path.join(ROOT, 'environments', 'Educational_Platform_Dev.postman_environment.json');
const CSV_IN = path.join(ROOT, 'test_cases', 'test_cases_comprehensive.csv');
const CSV_OUT = path.join(ROOT, 'test_cases', 'test_results.csv');
const REPORTS_DIR = path.join(ROOT, 'reports');

// ── CLI args ──────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const folderIdx = args.indexOf('--folder');
const folder = folderIdx !== -1 ? args[folderIdx + 1] : null;
const envIdx = args.indexOf('--env');
const envFile = envIdx !== -1 ? args[envIdx + 1] : ENVIRONMENT;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Parse CSV preserving quoted commas */
function parseCSV(content) {
  const lines = content.replace(/\r/g, '').trim().split('\n');
  const headers = splitCSVLine(lines[0]);
  return lines.slice(1).map(line => {
    const cells = splitCSVLine(line);
    return headers.reduce((obj, h, i) => { obj[h] = cells[i] ?? ''; return obj; }, {});
  });
}

function splitCSVLine(line) {
  const result = [];
  let cur = '', inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQuote && line[i + 1] === '"') { cur += '"'; i++; }
      else inQuote = !inQuote;
    } else if (c === ',' && !inQuote) {
      result.push(cur); cur = '';
    } else cur += c;
  }
  result.push(cur);
  return result;
}

function quoteCSVCell(val) {
  if (val == null) return '';
  const s = String(val);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function writeCSV(headers, rows, filePath) {
  const lines = [headers.map(quoteCSVCell).join(',')];
  rows.forEach(row => lines.push(headers.map(h => quoteCSVCell(row[h])).join(',')));
  fs.writeFileSync(filePath, lines.join('\n'), 'utf8');
}

/** Extract TC_XXX_NNN from a Newman item name */
function extractTCID(name) {
  const m = name.match(/^(TC_[A-Z]+_\d+)/i);
  return m ? m[1].toUpperCase() : null;
}

/** Ensure reports directory exists */
function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

// ── Main ──────────────────────────────────────────────────────────────────────

if (!fs.existsSync(COLLECTION)) {
  console.error('Collection not found:', COLLECTION);
  process.exit(1);
}

ensureDir(REPORTS_DIR);

const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const jsonReportPath = path.join(REPORTS_DIR, `results_${timestamp}.json`);

console.log('\n========================================');
console.log(' Educational Platform - Postman Tests');
console.log('========================================');
if (folder) console.log(' Folder:', folder);
console.log(' Collection:', path.basename(COLLECTION));
console.log(' Environment:', path.basename(envFile));
console.log('========================================\n');

const runOptions = {
  collection: COLLECTION,
  environment: envFile,
  reporters: ['cli', 'json'],
  reporter: { json: { export: jsonReportPath } },
  delayRequest: 100,
  timeoutRequest: 10000,
};
if (folder) runOptions.folder = folder;

newman.run(runOptions, (err, summary) => {
  if (err) {
    console.error('\nNewman run error:', err.message);
    process.exit(1);
  }

  // ── Build pass/fail map: tcId → { result, assertions } ───────────────────
  const resultMap = {};   // TC_AUTH_001 → { result:'PASS'|'FAIL', assertions:[], requestName }

  summary.run.executions.forEach(exec => {
    const reqName = exec.item.name || '';
    const tcId = extractTCID(reqName);
    if (!tcId) return;

    const assertions = exec.assertions || [];
    const hasFail = assertions.some(a => a.error);
    const hasNetworkError = exec.requestError != null;

    const result = hasNetworkError ? 'ERROR' : hasFail ? 'FAIL' : 'PASS';
    const details = assertions.map(a => a.error ? `FAIL: ${a.assertion}: ${a.error.message}` : `OK: ${a.assertion}`).join(' | ');

    // Merge multiple assertions from same TC (e.g. global + local)
    if (!resultMap[tcId]) {
      resultMap[tcId] = { result, details, requestName: reqName };
    } else {
      // If any execution of same TC fails, mark FAIL
      if (result === 'FAIL' || result === 'ERROR') resultMap[tcId].result = result;
      resultMap[tcId].details += ' | ' + details;
    }
  });

  // ── Read existing CSV and add/update Result column ────────────────────────
  if (!fs.existsSync(CSV_IN)) {
    console.warn('CSV not found, skipping update:', CSV_IN);
  } else {
    const rows = parseCSV(fs.readFileSync(CSV_IN, 'utf8'));
    const headers = Object.keys(rows[0] || {});
    if (!headers.includes('Result')) headers.push('Result');
    if (!headers.includes('Run Time')) headers.push('Run Time');
    if (!headers.includes('Details')) headers.push('Details');

    const runTime = new Date().toLocaleString('vi-VN');

    rows.forEach(row => {
      const tcId = (row['Test case ID'] || '').trim().toUpperCase();
      if (resultMap[tcId]) {
        row['Result'] = resultMap[tcId].result;
        row['Run Time'] = runTime;
        row['Details'] = resultMap[tcId].details;
      } else if (!row['Result']) {
        row['Result'] = 'NOT RUN';
        row['Run Time'] = runTime;
        row['Details'] = '';
      }
    });

    writeCSV(headers, rows, CSV_OUT);
    console.log('\n CSV results written to:', CSV_OUT);
  }

  // ── Summary ───────────────────────────────────────────────────────────────
  const stats = summary.run.stats;
  const total = stats.assertions.total;
  const failed = stats.assertions.failed;
  const passed = total - failed;

  console.log('\n========================================');
  console.log(' TEST SUMMARY');
  console.log('========================================');
  console.log(` Requests  : ${stats.requests.total}`);
  console.log(` Assertions: ${total}`);
  console.log(` Passed    : ${passed}`);
  console.log(` Failed    : ${failed}`);
  console.log('========================================');

  if (Object.keys(resultMap).length > 0) {
    const passCount = Object.values(resultMap).filter(r => r.result === 'PASS').length;
    const failCount = Object.values(resultMap).filter(r => r.result === 'FAIL').length;
    const errCount  = Object.values(resultMap).filter(r => r.result === 'ERROR').length;
    console.log('\n Test Cases matched from CSV:');
    console.log(`   PASS  : ${passCount}`);
    console.log(`   FAIL  : ${failCount}`);
    console.log(`   ERROR : ${errCount}`);

    if (failCount > 0 || errCount > 0) {
      console.log('\n Failed / Error tests:');
      Object.entries(resultMap)
        .filter(([, v]) => v.result !== 'PASS')
        .forEach(([id, v]) => console.log(`   [${v.result}] ${id} — ${v.requestName}`));
    }
  }

  console.log('\n Full JSON report:', jsonReportPath);
  if (fs.existsSync(CSV_OUT)) console.log(' Updated CSV    :', CSV_OUT);
  console.log('');

  process.exit(failed > 0 ? 1 : 0);
});
