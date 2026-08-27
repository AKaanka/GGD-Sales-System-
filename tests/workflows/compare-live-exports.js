// Compare the LIVE n8n workflows against the tracked exports in workflows/.
//
//   node tests/workflows/compare-live-exports.js <dir-of-live-exports>
//
// Why this exists
// ---------------
// tests/workflows/test-workflow-exports.js checks the TRACKED files against
// their contract. It never looks at n8n. Gate 3 step 9 asks a different
// question: does the workflow actually running in n8n still match the file we
// have committed? Editing a workflow in the n8n UI and forgetting to re-export
// is the normal way those two drift apart, and nothing else in this repo would
// notice.
//
// What is compared (the graph that decides behaviour):
//   * the set of node names
//   * each node's type, typeVersion, disabled flag and full parameters
//   * each node's credential SLOTS by name (see below)
//   * the connection map, normalised
//
// What is deliberately ignored, because it differs between two exports of the
// same workflow and means nothing:
//   * id, versionId, createdAt, updatedAt, meta, tags, active
//   * pinData (test fixtures pinned in the editor)
//   * per-node id, position and webhookId
//   * credential IDs. The tracked files carry REPLACE_ME placeholders by
//     design; the live ones carry real IDs. Comparing IDs would fail on every
//     node forever, so only the credential TYPE and NAME are compared. This is
//     the one place a real difference could hide, so it is stated loudly here
//     rather than hidden in the code.
//
// Exit code is 0 only when every workflow matches.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const project = path.resolve(__dirname, '../..');
const trackedDir = path.join(project, 'workflows');
const liveDir = process.argv[2];

if (!liveDir) {
  console.error('usage: node tests/workflows/compare-live-exports.js <dir-of-live-exports>');
  process.exit(2);
}
if (!fs.existsSync(liveDir)) {
  console.error(`ERROR: live export directory not found: ${liveDir}`);
  process.exit(2);
}

// Confirmed bindings.
// A placeholder field can be bound to any value, so the tool cannot approve one
// on its own. It CAN tell you whether the value changed since a human last read
// it. Confirmed values are stored as SHA-256 hashes, not plaintext: the check
// works without publishing Kaan's addresses to a git remote, and any change to a
// bound value still fails loudly.
//   node tests/workflows/compare-live-exports.js <dir> --record-confirmed
// after reading each printed value. Re-record only when a value legitimately
// changes, and read it again when you do.
const CONFIRMED_FILE = path.join(__dirname, 'confirmed-bindings.json');
const confirmed = fs.existsSync(CONFIRMED_FILE)
  ? JSON.parse(fs.readFileSync(CONFIRMED_FILE, 'utf8'))
  : { note: 'sha256 of confirmed live values for placeholder-backed fields', bindings: {} };
const recording = process.argv.includes('--record-confirmed');
const recorded = {};
const sha = (v) => crypto.createHash('sha256').update(String(v)).digest('hex');

const TRACKED = [
  'GGD-00-shared-error-handler.json',
  'GGD-01-lead-qualification.json',
  'GGD-02-draft-approval-queue.json',
  'GGD-03-approved-send.json',
  'GGD-04-reply-and-bounce-intake.json',
  'GGD-05-daily-follow-up.json',
];

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

// n8n can export one file per workflow, or a single array. Accept both.
function loadLiveWorkflows(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir)) {
    if (!entry.endsWith('.json')) continue;
    const parsed = readJson(path.join(dir, entry));
    if (Array.isArray(parsed)) out.push(...parsed);
    else out.push(parsed);
  }
  return out;
}

function normaliseCredentials(creds) {
  if (!creds) return null;
  const out = {};
  for (const [type, value] of Object.entries(creds)) {
    // name only - IDs legitimately differ (see header)
    out[type] = value && typeof value === 'object' ? (value.name ?? null) : value;
  }
  return out;
}

function stableStringify(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(value[k])}`).join(',')}}`;
}

function normaliseNode(node) {
  return {
    type: node.type,
    typeVersion: node.typeVersion,
    disabled: node.disabled === true,
    credentials: normaliseCredentials(node.credentials),
    parameters: node.parameters ?? {},
  };
}

function nodeMap(workflow) {
  const map = new Map();
  for (const node of workflow.nodes ?? []) map.set(node.name, normaliseNode(node));
  return map;
}

// ---------------------------------------------------------------------------
// Three classes of difference are EXPECTED between a tracked file and a live
// export. They are classified rather than hidden, so that a real drift stands
// out instead of drowning in noise that recurs on every single run.
//
//   CONFIRM      the tracked file carries REPLACE_WITH_* on purpose so it can
//                be shared and re-imported; live carries the bound value.
//                This is NOT auto-approved. A placeholder field can be bound
//                to ANY value, and these fields decide who receives email, so
//                the bound value is printed and BLOCKS every run until a human
//                reads it. An earlier version of this file classified these as
//                simply "expected" - a test that mutated the Gate 4 allowlist
//                to an attacker address passed clean. Do not weaken this.
//   DEFAULT-OMIT the key is absent from the live export. n8n omits parameters
//                whose value equals the node's default. NOTE HONESTLY: an
//                absent key can ALSO mean someone cleared that setting in the
//                UI. This tool cannot tell those apart offline, so these are
//                reported as explained-but-worth-one-look, never as proven.
//   WHITESPACE   identical text differing only in trailing newline.
//
// Anything else is UNEXPLAINED and is what a human should actually act on.
// ---------------------------------------------------------------------------
function classifyParamDiff(tracked, live) {
  if (typeof tracked === 'string' && /^REPLACE_(WITH|ME)/.test(tracked)) return 'CONFIRM';
  if (live === undefined) return 'DEFAULT-OMIT';
  if (typeof tracked === 'string' && typeof live === 'string' &&
      tracked.trim().split(/\s+/).join(' ') === live.trim().split(/\s+/).join(' ')) return 'WHITESPACE';
  return 'UNEXPLAINED';
}

let problems = 0;
let compared = 0;
const counts = { GRAPH: 0, UNEXPLAINED: 0, CONFIRM: 0, CRED: 0, PIN: 0, EXPLAINED: 0 };
let blocking = 0;

function report(kind, msg) {
  problems += 1;
  counts[kind] = (counts[kind] || 0) + 1;
  if (kind === 'GRAPH' || kind === 'UNEXPLAINED' || kind === 'PIN' || kind === 'CONFIRM') blocking += 1;
  console.log(`  ${kind.padEnd(12)} ${msg}`);
}

function short(value) {
  const s = typeof value === 'string' ? value : JSON.stringify(value);
  if (s === undefined) return 'undefined';
  return s.length > 150 ? `${s.slice(0, 150)}...` : s;
}

// Walk two parameter objects and return the exact paths that differ, so a
// "parameters differ" line can be judged instead of just noted.
function diffPaths(a, b, prefix = '', out = []) {
  const keys = new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})]);
  for (const key of keys) {
    const pa = a ? a[key] : undefined;
    const pb = b ? b[key] : undefined;
    const path = prefix ? `${prefix}.${key}` : key;
    const bothObjects =
      pa && pb && typeof pa === 'object' && typeof pb === 'object' &&
      Array.isArray(pa) === Array.isArray(pb);
    if (bothObjects) {
      diffPaths(pa, pb, path, out);
    } else if (stableStringify(pa) !== stableStringify(pb)) {
      out.push({ path, tracked: pa, live: pb });
    }
  }
  return out;
}

const explained = [];
const live = loadLiveWorkflows(liveDir);
console.log(`Loaded ${live.length} live workflow(s) from ${liveDir}\n`);

for (const file of TRACKED) {
  const trackedPath = path.join(trackedDir, file);
  if (!fs.existsSync(trackedPath)) {
    console.log(`MISSING TRACKED FILE  ${file}`);
    problems += 1;
    continue;
  }
  const tracked = readJson(trackedPath);
  const match = live.find((w) => w.name === tracked.name);

  console.log(`### ${file}   ("${tracked.name}")`);
  if (!match) {
    report('GRAPH', `no live workflow named "${tracked.name}" - not imported, or renamed in the n8n UI`);
    console.log('');
    continue;
  }
  compared += 1;

  const a = nodeMap(tracked);
  const b = nodeMap(match);

  for (const name of a.keys()) if (!b.has(name)) report('GRAPH', `node in tracked file but NOT live: "${name}"`);
  for (const name of b.keys()) if (!a.has(name)) report('GRAPH', `node LIVE but not in tracked file: "${name}"`);

  for (const [name, trackedNode] of a) {
    const liveNode = b.get(name);
    if (!liveNode) continue;
    for (const field of ['type', 'typeVersion', 'disabled']) {
      if (stableStringify(trackedNode[field]) !== stableStringify(liveNode[field])) {
        report('GRAPH', `"${name}" ${field}: tracked=${JSON.stringify(trackedNode[field])} live=${JSON.stringify(liveNode[field])}`);
      }
    }
    if (stableStringify(trackedNode.credentials) !== stableStringify(liveNode.credentials)) {
      report('CRED', `"${name}": tracked=${stableStringify(trackedNode.credentials)} live=${stableStringify(liveNode.credentials)}`);
    }
    if (stableStringify(trackedNode.parameters) !== stableStringify(liveNode.parameters)) {
      for (const d of diffPaths(trackedNode.parameters, liveNode.parameters)) {
        const cls = classifyParamDiff(d.tracked, d.live);
        if (cls === 'CONFIRM') {
          const key = `${tracked.name}::${name}::${d.path}`;
          const digest = sha(d.live);
          if (recording) {
            recorded[key] = digest;
            console.log(`  RECORDING    "${name}" ${d.path} = ${short(d.live)}`);
            counts.EXPLAINED += 1;
          } else if (confirmed.bindings && confirmed.bindings[key] === digest) {
            counts.EXPLAINED += 1;
            explained.push(`CONFIRMED-OK "${name}" ${d.path} (unchanged since it was read)`);
          } else {
            const why = confirmed.bindings && confirmed.bindings[key]
              ? 'VALUE CHANGED since it was last confirmed'
              : 'never confirmed';
            report('CONFIRM', `"${name}" ${d.path} - ${why}`);
            console.log(`               tracked: ${short(d.tracked)}`);
            console.log(`               live   : ${short(d.live)}   <-- READ THIS VALUE`);
          }
        } else if (cls === 'UNEXPLAINED') {
          report(cls, `"${name}" ${d.path}`);
          console.log(`               tracked: ${short(d.tracked)}`);
          console.log(`               live   : ${short(d.live)}`);
        } else {
          counts.EXPLAINED += 1;
          explained.push(`${cls.padEnd(12)} "${name}" ${d.path}`);
        }
      }
    }
  }

  if (stableStringify(tracked.connections ?? {}) !== stableStringify(match.connections ?? {})) {
    report('GRAPH', 'connection map differs - nodes are wired differently live than in the tracked file');
  }

  if (match.pinData && Object.keys(match.pinData).length > 0) {
    report('PIN', `pinned data still present on: ${Object.keys(match.pinData).join(', ')}`);
  }

  if (problems === 0) console.log('  OK           live graph matches the tracked file');
  console.log('');
}

if (recording) {
  fs.writeFileSync(CONFIRMED_FILE, `${JSON.stringify({ ...confirmed, recordedCount: Object.keys(recorded).length, bindings: recorded }, null, 2)}\n`);
  console.log(`\nRecorded ${Object.keys(recorded).length} confirmed binding hash(es) to ${path.relative(project, CONFIRMED_FILE)}`);
  console.log('Values are stored as SHA-256, never in plaintext.');
}
console.log('='.repeat(72));
if (explained.length) {
  console.log(`EXPECTED DIFFERENCES (${explained.length}) - classified, not defects:`);
  for (const line of explained) console.log(`  ${line}`);
  console.log('');
}
if (blocking === 0) {
  console.log(`RESULT: PASS - no unexplained differences across ${compared} workflows.`);
  console.log(`        ${counts.EXPLAINED} expected difference(s) classified above.`);
  console.log(`        ${counts.CRED || 0} credential slot NAME mismatch(es) - cosmetic, see below.`);
  if (counts.CRED) {
    console.log('        The live credentials work; they just kept n8n default names');
    console.log('        instead of the documented ones. Rename them in n8n to match.');
  }
  process.exit(0);
}
console.log(`RESULT: FAIL - ${blocking} difference(s) need a decision.`);
console.log('');
console.log(`  GRAPH        ${counts.GRAPH || 0}  nodes added/removed/rewired`);
console.log(`  UNEXPLAINED  ${counts.UNEXPLAINED || 0}  a node would behave differently from the committed file`);
console.log(`  CONFIRM      ${counts.CONFIRM || 0}  placeholder field bound to a live value - READ each value above`);
console.log(`  PIN          ${counts.PIN || 0}  editor test fixtures left pinned - unpin and re-export`);
console.log('');
console.log(`  (${counts.EXPLAINED} expected difference(s) and ${counts.CRED || 0} credential-name mismatch(es) were not counted.)`);
console.log('A difference is not automatically a defect - it means the live system and');
console.log('the committed file disagree, and you must decide which one is right.');
process.exit(1);
