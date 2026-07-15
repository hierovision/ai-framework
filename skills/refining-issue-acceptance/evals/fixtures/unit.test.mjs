// Unit tests for refining-issue-acceptance/scripts/refine-issue.mjs validators.
// Run: node skills/refining-issue-acceptance/evals/fixtures/unit.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { findLeaks, analyzeAcs, validateRefined } from '../../scripts/refine-issue.mjs';

const GOOD_BODY = `## Summary
Short user-facing description of the change.

## Acceptance Criteria
**AC1 — [e2e]** a user can log in with valid credentials
- [unit] empty email is rejected with an inline error
- [integration] an audit row is written on success
`;

test('findLeaks flags clear code context', () => {
  assert.deepEqual(findLeaks('we add class AuthService {'), ['class AuthService {']);
  assert.ok(findLeaks('the helper lives in src/api/client.ts').length >= 1);
  assert.deepEqual(findLeaks('const token = "abc"'), ['const token =']);
  assert.ok(findLeaks('import { readFile } from "fs"').length >= 1);
  assert.ok(findLeaks('function parse(input) {').length >= 1);
});

test('findLeaks does NOT false-positive on plain behavioral prose', () => {
  assert.deepEqual(findLeaks('export to CSV'), []);
  assert.deepEqual(findLeaks('import records'), []);
  assert.deepEqual(findLeaks('class roster of students'), []);
  assert.deepEqual(findLeaks('function room is open'), []);
  assert.deepEqual(findLeaks('the teacher will import the records'), []);
});

test('analyzeAcs counts one tag per AC line', () => {
  const a = analyzeAcs(GOOD_BODY);
  assert.equal(a.hasSection, true);
  assert.deepEqual(a.acLines, [1, 1, 1]);
  assert.equal(a.total, 3);

  const untagged = analyzeAcs(`## Acceptance Criteria\n**AC1 — login** do it\n`);
  assert.deepEqual(untagged.acLines, [0]);

  const two = analyzeAcs(`## Acceptance Criteria\n- [unit][e2e] both layers\n`);
  assert.deepEqual(two.acLines, [2]);

  const none = analyzeAcs(`## Description\njust text\n`);
  assert.equal(none.hasSection, false);
  assert.deepEqual(none.acLines, []);
});

test('validateRefined passes a clean, single-tagged spec', () => {
  const r = validateRefined(GOOD_BODY);
  assert.equal(r.pass, true);
  assert.deepEqual(r.violations, []);
});

test('validateRefined rejects untagged AC', () => {
  const body = `## Acceptance Criteria\n**AC1 — login** do it\n`;
  const r = validateRefined(body);
  assert.equal(r.pass, false);
  assert.ok(r.violations.some((v) => v.rule === 'AC tag'));
});

test('validateRefined rejects more than one tag per AC', () => {
  const body = `## Acceptance Criteria\n- [unit][e2e] both layers\n`;
  const r = validateRefined(body);
  assert.equal(r.pass, false);
  assert.ok(r.violations.some((v) => /exactly one/.test(v.detail)));
});

test('validateRefined detects an implementation leak', () => {
  const body = `## Acceptance Criteria\n- [unit] we add class AuthService { to hold state\n`;
  const r = validateRefined(body);
  assert.equal(r.pass, false);
  assert.ok(r.violations.some((v) => v.rule === 'implementation leak'));
});

test('validateRefined requires an Acceptance Criteria section', () => {
  const r = validateRefined(`## Description\nno criteria here\n`);
  assert.equal(r.pass, false);
  assert.ok(r.violations.some((v) => v.rule === 'AC section'));
});
