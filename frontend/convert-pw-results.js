#!/usr/bin/env node
/**
 * convert-pw-results.js
 *
 * Converts Playwright's native JSON reporter output (playwright-results.json)
 * into the 3ioNetra test result format (test-results.json) that the merge
 * script can consume.
 *
 * Usage:  node convert-pw-results.js
 *
 * Reads:  frontend/playwright-results.json
 * Writes: frontend/test-results.json
 */

const fs = require('fs');
const path = require('path');

const INPUT = path.join(__dirname, 'playwright-results.json');
const OUTPUT = path.join(__dirname, 'test-results.json');

// Test ID pattern: extract "AUTH-01" etc. from test title
const ID_RE = /\b([A-Z]+-\d{2})\b/;

function main() {
  if (!fs.existsSync(INPUT)) {
    console.error(`Input file not found: ${INPUT}`);
    process.exit(1);
  }

  const raw = JSON.parse(fs.readFileSync(INPUT, 'utf-8'));
  const results = [];

  // Playwright JSON format has: { suites: [ { suites: [...], specs: [...] } ] }
  function walkSuites(suites) {
    for (const suite of suites) {
      if (suite.specs) {
        for (const spec of suite.specs) {
          const title = spec.title || '';
          const idMatch = title.match(ID_RE);
          const testId = idMatch ? idMatch[1] : title.replace(/\s+/g, '_').slice(0, 20);

          let status = 'SKIP';
          let details = '';
          let latencyMs = 0;

          if (spec.tests && spec.tests.length > 0) {
            const test = spec.tests[0];
            const result = test.results && test.results[0];

            if (result) {
              latencyMs = Math.round(result.duration || 0);
              if (result.status === 'passed') {
                status = 'PASS';
                details = `Passed in ${latencyMs}ms`;
              } else if (result.status === 'failed') {
                status = 'FAIL';
                const errMsg = result.error?.message || 'Unknown failure';
                details = errMsg.slice(0, 200);
              } else if (result.status === 'timedOut') {
                status = 'FAIL';
                details = 'Timed out';
              } else if (result.status === 'skipped') {
                status = 'SKIP';
                details = 'Skipped';
              }
            }

            // Check expected status for "soft" assertions
            if (test.expectedStatus === 'skipped') {
              status = 'SKIP';
            }
          }

          // Determine priority from test ID prefix
          let priority = 'P1';
          if (testId.startsWith('AUTH') || testId.startsWith('SAFE')) priority = 'P0';
          else if (testId.startsWith('EDGE') || testId.startsWith('PERF')) priority = 'P2';

          results.push({
            id: testId,
            title: title,
            priority,
            status,
            details,
            latency_ms: latencyMs,
          });
        }
      }
      if (suite.suites) {
        walkSuites(suite.suites);
      }
    }
  }

  walkSuites(raw.suites || []);

  // Build output in the standard format
  const counts = { PASS: 0, PARTIAL: 0, FAIL: 0, SKIP: 0 };
  for (const r of results) {
    counts[r.status] = (counts[r.status] || 0) + 1;
  }
  const total = results.length;
  const passRate = total > 0 ? Math.round((counts.PASS / total) * 10000) / 100 : 0;

  const output = {
    timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
    total,
    counts,
    pass_rate: passRate,
    results,
  };

  fs.writeFileSync(OUTPUT, JSON.stringify(output, null, 2));
  console.log(`Converted ${total} test results -> ${OUTPUT}`);
  console.log(`  PASS: ${counts.PASS} | PARTIAL: ${counts.PARTIAL} | FAIL: ${counts.FAIL} | SKIP: ${counts.SKIP}`);
}

main();
