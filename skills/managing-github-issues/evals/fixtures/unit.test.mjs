// Unit tests for managing-github-issues/scripts/sync-issues.mjs pure helpers.
// Run: node skills/managing-github-issues/evals/fixtures/unit.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  parseRoadmap,
  findSourceFiles,
  findSectionHints,
  extractChecklist,
  buildBody,
  isBacked,
  priorityForScore,
  findOpenTableSourcesCol,
} from '../../scripts/sync-issues.mjs';

const OPEN_TABLE = `| id | Title | Category | Impact | Urgency | Score | Status | Sources | Notes |
|----|-------|----------|--------|---------|-------|--------|---------|-------|
| feat-1 | Login | feature | 3 | 3 | 9 | Planned | src/login.md (login:1) | do it |
| done-old | Old | feature | 2 | 2 | 4 | Done | src/old.md | done |
`;

test('parseRoadmap extracts open-table rows with score/status/sources', () => {
  const items = parseRoadmap(OPEN_TABLE);
  assert.equal(items.length, 2);
  const feat = items.find((i) => i.id === 'feat-1');
  assert.ok(feat);
  assert.equal(feat.score, '9');
  assert.equal(feat.status, 'Planned');
  assert.equal(feat.sourcesRaw, 'src/login.md (login:1)');
  assert.equal(feat.notes, 'do it');
});

test('findSourceFiles extracts .md filenames only', () => {
  assert.deepEqual(findSourceFiles('src/login.md, src/notes.md'), ['src/login.md', 'src/notes.md']);
  assert.deepEqual(findSourceFiles(''), []);
  assert.deepEqual(findSourceFiles('no files here'), []);
});

test('findSectionHints extracts section hints from (hint:n)', () => {
  assert.deepEqual(findSectionHints('src/login.md (login:1), src/x.md (auth:2)'), ['login', 'auth']);
  assert.deepEqual(findSectionHints(''), []);
});

test('findOpenTableSourcesCol locates the Sources column index', () => {
  assert.equal(findOpenTableSourcesCol(OPEN_TABLE), 7);
  assert.equal(findOpenTableSourcesCol('| id | foo |\n|---|---|'), -1);
});

test('priorityForScore bands', () => {
  assert.equal(priorityForScore(9), 'High');
  assert.equal(priorityForScore(6), 'High');
  assert.equal(priorityForScore(4), 'Medium');
  assert.equal(priorityForScore(3), 'Medium');
  assert.equal(priorityForScore(1), 'Low');
  assert.equal(priorityForScore('garbage'), 'Low');
});

test('isBacked detects the write-back signal owner/repo#n', () => {
  assert.equal(isBacked({ sourcesRaw: 'acme/widgets#12' }, 'acme/widgets'), true);
  assert.equal(isBacked({ sourcesRaw: 'src/login.md' }, 'acme/widgets'), false);
  assert.equal(isBacked({ sourcesRaw: '' }, 'acme/widgets'), false);
});

test('extractChecklist pulls bullets from hinted source sections; skips path escapes', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sync-'));
  try {
    writeFileSync(join(dir, 'login.md'), '# Login\n\n## Login flow\n- show error on bad password\n- lock after 5 tries\n', 'utf8');
    const inside = extractChecklist({ id: 'feat-1', sourcesRaw: 'login.md (login:1)' }, dir);
    assert.ok(inside.length >= 2, `expected >=2 bullets, got ${JSON.stringify(inside)}`);
    // containment guard: a ../ escape is NOT read
    const escaped = extractChecklist({ id: 'feat-1', sourcesRaw: '../escape.md (login:1)' }, dir);
    assert.deepEqual(escaped, []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('buildBody renders header + extracted checklist', () => {
  const dir = mkdtempSync(join(tmpdir(), 'syncb-'));
  try {
    writeFileSync(join(dir, 'login.md'), '# Login\n\n## Login flow\n- show error on bad password\n', 'utf8');
    const item = {
      id: 'feat-1', title: 'Login', category: 'feature',
      impact: '3', urgency: '3', score: '9', status: 'Planned',
      sourcesRaw: 'login.md (login:1)', notes: 'do it',
    };
    const body = buildBody(item, dir);
    assert.match(body, /Roadmap ID.*feat-1/);
    assert.match(body, /Acceptance \/ source checklist/);
    assert.match(body, /show error on bad password/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
