// Offline tests for the Evaluate reply match code node in GGD 04c.
// evaluate-reply-match.js is kept byte-identical to the deployed node; verify
// with:  shasum -a 256 evaluate-reply-match.js   (compare against the workflow)
// Run:   node tests/workflow4/test-evaluate-reply-match.js

const fs = require('fs');
const code = fs.readFileSync(__dirname + '/evaluate-reply-match.js', 'utf8');
const run = new Function('$', code);

function ctx(src, candidates, opts = {}) {
  const threads = opts.threadCandidates || [];
  return (name) => {
    if (name === 'Validate and sanitize reply') return { first: () => ({ json: src }) };
    if (name === 'Get many opportunities') {
      if (opts.throwOnCandidates) throw new Error('node not executed');
      return { all: () => candidates.map((json) => ({ json })) };
    }
    if (name === 'Get opportunities by thread') {
      return { all: () => threads.map((json) => ({ json })) };
    }
    throw new Error('unexpected node ' + name);
  };
}

let pass = 0, fail = 0;
function check(label, fn) {
  let ok = false, err = null;
  try { ok = fn(); } catch (e) { err = e.message; }
  if (ok) { pass++; console.log('PASS  ' + label); }
  else { fail++; console.log('FAIL  ' + label + (err ? '  (' + err + ')' : '')); }
}
const items = (src, cands, opts) => run(ctx(src, cands, opts)).map((i) => i.json);
const one = (src, cands, opts) => items(src, cands, opts)[0];

const F1 = { id: 3, name: 'Nordlicht', email_from: 'f1@ggd-qa.invalid', ggd_last_message_id: '<out-001@example.invalid>' };
const F2 = { id: 4, name: 'Anadolu', email_from: 'shared@ggd-qa.invalid', ggd_last_message_id: '<out-002@example.invalid>' };
const F3 = { id: 5, name: 'Rheintal', email_from: 'shared@ggd-qa.invalid', ggd_last_message_id: false };

console.log('--- decision table ---');

check('Row 0  explicit id wins', () => {
  const r = one({ opportunity_id: 3, sender_email: 'f1@ggd-qa.invalid' }, [F1]);
  return r.ggd_reply_analysis_allowed && r.matched_by === 'explicit_id' && r.opportunity_id === 3 && r.id === 3;
});

check('Row 1  single candidate confirmed by thread', () => {
  const r = one({ sender_email: 'f1@ggd-qa.invalid', in_reply_to: '<out-001@example.invalid>' }, [F1]);
  return r.ggd_reply_analysis_allowed && r.matched_by === 'thread' && r.opportunity_id === 3;
});

check('Row 2  thread disambiguates two candidates', () => {
  const r = one({ sender_email: 'shared@ggd-qa.invalid', in_reply_to: '<out-002@example.invalid>' }, [F2, F3]);
  return r.ggd_reply_analysis_allowed && r.matched_by === 'thread' && r.opportunity_id === 4;
});

check('Row 3  single candidate, no thread header  -> sender_only', () => {
  const r = one({ sender_email: 'f1@ggd-qa.invalid' }, [F1]);
  return r.ggd_reply_analysis_allowed && r.matched_by === 'sender_only' && r.opportunity_id === 3;
});

check('Row 4a  no sender candidate, thread search resolves one  (A3)', () => {
  const r = one({ sender_email: 'stranger@ggd-qa.invalid', in_reply_to: '<out-001@example.invalid>' },
    [], { threadCandidates: [F1] });
  return r.ggd_reply_analysis_allowed && r.matched_by === 'thread_fallback'
    && r.opportunity_id === 3 && r.id === 3;
});

check('Row 4b  thread search resolves several -> review on each', () => {
  const rs = items({ sender_email: 'stranger@ggd-qa.invalid', in_reply_to: '<dup@example.invalid>' },
    [], { threadCandidates: [F2, F3] });
  return rs.length === 2 && rs.every((r) => !r.ggd_reply_analysis_allowed)
    && rs.map((r) => r.id).join(',') === '4,5';
});

check('Row 4c  neither key resolves anything -> unrouted review', () => {
  const rs = items({ sender_email: 'stranger@ggd-qa.invalid', in_reply_to: '<out-009@example.invalid>' },
    [], { threadCandidates: [] });
  const r = rs[0];
  return rs.length === 1 && !r.ggd_reply_analysis_allowed && r.needs_thread_fallback
    && r.manual_review_unrouted && r.id === null;
});

check('sender match takes precedence over the thread search', () => {
  const r = one({ sender_email: 'f1@ggd-qa.invalid' }, [F1], { threadCandidates: [F2] });
  return r.matched_by === 'sender_only' && r.opportunity_id === 3;
});

check('Row 5  ambiguous sender -> one review item per candidate  (A2)', () => {
  const rs = items({ sender_email: 'shared@ggd-qa.invalid' }, [F2, F3]);
  return rs.length === 2
    && rs.map((r) => r.id).join(',') === '4,5'
    && rs.every((r) => !r.ggd_reply_analysis_allowed)
    && rs.every((r) => r.opportunity_id === null)
    && rs.every((r) => JSON.stringify(r.candidate_ids) === JSON.stringify([4, 5]))
    && rs.every((r) => r.review_reason.includes('4 Anadolu') && r.review_reason.includes('5 Rheintal'));
});

check('Row 6  nothing found at all -> unrouted review  (A4)', () => {
  const rs = items({ sender_email: 'nobody@ggd-qa.invalid' }, []);
  const r = rs[0];
  return rs.length === 1 && !r.ggd_reply_analysis_allowed && r.id === null
    && r.manual_review_unrouted && !r.needs_thread_fallback;
});

console.log('--- downstream contract ---');

check('matched path always carries id for downstream nodes', () => {
  const a = one({ opportunity_id: 3 }, [F1]);
  const b = one({ sender_email: 'f1@ggd-qa.invalid' }, [F1]);
  const c = one({ sender_email: 'f1@ggd-qa.invalid', in_reply_to: '<out-001@example.invalid>' }, [F1]);
  return [a, b, c].every((r) => r.id === r.opportunity_id && r.id !== null);
});

check('review items never carry an opportunity_id', () => {
  const rs = items({ sender_email: 'shared@ggd-qa.invalid' }, [F2, F3]);
  return rs.every((r) => r.opportunity_id === null);
});

check('every emitted item has the full field set', () => {
  const keys = ['ggd_reply_analysis_allowed','matched_by','opportunity_id','id','candidate_ids',
    'thread_ids','sender_email','needs_thread_fallback','manual_review_unrouted','review_reason'];
  const all = [].concat(
    items({ opportunity_id: 3 }, [F1]),
    items({ sender_email: 'shared@ggd-qa.invalid' }, [F2, F3]),
    items({ sender_email: 'nobody@ggd-qa.invalid' }, []));
  return all.every((r) => keys.every((k) => k in r));
});

console.log('--- edge cases ---');

check('display-name sender is normalised', () => {
  const r = one({ sender_email: 'Klaus Meier <F1@GGD-QA.invalid>' }, [F1]);
  return r.matched_by === 'sender_only' && r.sender_email === 'f1@ggd-qa.invalid';
});

check('message id matches without angle brackets', () => {
  const r = one({ sender_email: 'f1@ggd-qa.invalid', in_reply_to: 'out-001@example.invalid' }, [F1]);
  return r.matched_by === 'thread' && r.opportunity_id === 3;
});

check('References header is searched too', () => {
  const r = one({ sender_email: 'shared@ggd-qa.invalid', references: '<x@y> <out-002@example.invalid>' }, [F2, F3]);
  return r.matched_by === 'thread' && r.opportunity_id === 4;
});

check('upstream node not executed is treated as no candidates', () => {
  const r = one({ sender_email: 'f1@ggd-qa.invalid' }, [], { throwOnCandidates: true });
  return !r.ggd_reply_analysis_allowed && JSON.stringify(r.candidate_ids) === '[]';
});

check('two candidates sharing a thread id stays manual review', () => {
  const rs = items({ sender_email: 'shared@ggd-qa.invalid', in_reply_to: '<dup@example.invalid>' },
    [{ id: 4, name: 'A', ggd_last_message_id: '<dup@example.invalid>' },
     { id: 5, name: 'B', ggd_last_message_id: '<dup@example.invalid>' }]);
  return rs.length === 2 && rs.every((r) => !r.ggd_reply_analysis_allowed);
});

check('suppressed candidate is still matched (analysis must run)', () => {
  const r = one({ sender_email: 'f1@ggd-qa.invalid' }, [Object.assign({}, F1, { ggd_do_not_contact: true })]);
  return r.ggd_reply_analysis_allowed && r.matched_by === 'sender_only';
});

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
