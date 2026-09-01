// Static, offline contract checks for the reproducible n8n workflow exports.
// Run: node tests/workflows/test-workflow-exports.js

const fs = require('fs');
const path = require('path');

const project = path.resolve(__dirname, '../..');
const workflowDir = path.join(project, 'workflows');
const required = [
  'GGD-00-shared-error-handler.json',
  'GGD-01-lead-qualification.json',
  'GGD-02-draft-approval-queue.json',
  'GGD-03-approved-send.json',
  'GGD-04-reply-and-bounce-intake.json',
  'GGD-05-daily-follow-up.json',
];

let passed = 0;
let failed = 0;

function check(condition, message) {
  if (!condition) throw new Error(message);
}

function run(label, fn) {
  try {
    fn();
    passed += 1;
    console.log(`PASS  ${label}`);
  } catch (error) {
    failed += 1;
    console.log(`FAIL  ${label}: ${error.message}`);
  }
}

function load(file) {
  return JSON.parse(fs.readFileSync(path.join(workflowDir, file), 'utf8'));
}

function nodeByName(workflow, name) {
  const node = workflow.nodes.find((candidate) => candidate.name === name);
  check(node, `missing node ${name}`);
  return node;
}

function runPerItemCode(node, json, lookup = {}) {
  const execute = new Function('$json', '$', node.parameters.jsCode);
  return execute(json, (name) => ({item: {json: lookup[name]}}));
}

function runAllItemsCode(node, rows) {
  const execute = new Function('$input', node.parameters.jsCode);
  return execute({all: () => rows.map((json) => ({json}))});
}

function graph(workflow) {
  const edges = new Map();
  for (const node of workflow.nodes) edges.set(node.name, []);
  for (const [source, groups] of Object.entries(workflow.connections || {})) {
    for (const outputs of Object.values(groups)) {
      for (const branch of outputs || []) {
        for (const edge of branch || []) edges.get(source).push(edge.node);
      }
    }
  }
  return edges;
}

function reaches(edges, start, target) {
  const pending = [start];
  const seen = new Set();
  while (pending.length) {
    const current = pending.shift();
    if (current === target) return true;
    if (seen.has(current)) continue;
    seen.add(current);
    pending.push(...(edges.get(current) || []));
  }
  return false;
}

for (const file of required) {
  run(`${file} is a structurally valid inactive export`, () => {
    const workflow = load(file);
    check(typeof workflow.name === 'string' && workflow.name.startsWith('GGD-'), 'missing workflow name');
    check(workflow.active === false, 'tracked workflows must remain inactive');
    check(Array.isArray(workflow.nodes) && workflow.nodes.length > 1, 'workflow has no useful nodes');
    const names = new Set(workflow.nodes.map((node) => node.name));
    const ids = new Set(workflow.nodes.map((node) => node.id));
    check(names.size === workflow.nodes.length, 'duplicate node name');
    check(ids.size === workflow.nodes.length, 'duplicate node id');

    for (const node of workflow.nodes) {
      check(node.name && node.id && node.type, 'node is missing name, id, or type');
      check(node.type !== 'n8n-nodes-base.sendEmail', `${node.name} uses obsolete sendEmail type`);
      check(node.type !== 'n8n-nodes-base.anthropicChatModel', `${node.name} uses obsolete Anthropic type`);
      if (node.type === 'n8n-nodes-base.code') {
        check(typeof node.parameters.jsCode === 'string', `${node.name} must use jsCode`);
        new Function(node.parameters.jsCode);
      }
      const jsonBody = node.parameters.jsonBody;
      if (typeof jsonBody === 'string' && jsonBody.startsWith('={{') && jsonBody.endsWith('}}')) {
        const expression = jsonBody.slice(3, -2).trim();
        new Function(`return (${expression});`);
      }
      const serialized = JSON.stringify(node);
      check(!serialized.includes('$env.'), `${node.name} reads blocked environment variables`);
      check(!/(api[_ -]?key|password|secret)\s*[:=]\s*[^R\[{]/i.test(serialized), `${node.name} may contain a secret`);
    }

    for (const [source, groups] of Object.entries(workflow.connections || {})) {
      check(names.has(source), `connection source ${source} is not a node name`);
      for (const outputs of Object.values(groups)) {
        for (const branch of outputs || []) {
          for (const edge of branch || []) {
            check(names.has(edge.node), `connection target ${edge.node} is not a node name`);
          }
        }
      }
    }
  });
}

run('Workflow 2 stores a draft and has no email-send node', () => {
  const workflow = load('GGD-02-draft-approval-queue.json');
  check(workflow.nodes.some((node) => String(node.parameters.url || '').endsWith('/ggd_prepare_draft')), 'missing ggd_prepare_draft call');
  check(!workflow.nodes.some((node) => node.type === 'n8n-nodes-base.emailSend'), 'draft workflow may not send email');
});

run('Workflow 3 claims before SMTP and finalizes after SMTP', () => {
  const workflow = load('GGD-03-approved-send.json');
  const edges = graph(workflow);
  const claim = 'Claim send key before SMTP';
  const send = 'Send exact reviewed draft via Zoho';
  const finalize = 'Finalize complete send audit in Odoo';
  check(reaches(edges, claim, send), 'claim does not precede SMTP');
  check(reaches(edges, send, finalize), 'finalize does not follow SMTP');
  check(!reaches(edges, finalize, send), 'workflow can loop from finalize back to SMTP');
  check(reaches(edges, send, 'Record uncertain send for manual recovery'), 'SMTP errors are not recorded for manual recovery');
  check(reaches(edges, finalize, 'Record uncertain send for manual recovery'), 'final-audit errors are not recorded for manual recovery');
  check(workflow.nodes.filter((node) => node.type === 'n8n-nodes-base.emailSend').length === 1, 'expected exactly one SMTP node');
});

run('Workflow 3 enforces the temporary recipient allowlist before claiming a send key', () => {
  const workflow = load('GGD-03-approved-send.json');
  const allowlistName = 'Gate 4 recipient allowlist (temporary)';
  const rejectName = 'Reject recipient outside Gate 4 allowlist';
  const allowlist = nodeByName(workflow, allowlistName);
  const reject = nodeByName(workflow, rejectName);
  const prepareOutputs = workflow.connections['Prepare exact reviewed send']?.main || [];
  const allowlistOutputs = workflow.connections[allowlistName]?.main || [];
  const condition = allowlist.parameters.conditions?.conditions?.[0];

  check(allowlist.type === 'n8n-nodes-base.if' && allowlist.typeVersion === 2.2, 'allowlist must be an If v2.2 node');
  check(prepareOutputs[0]?.some((edge) => edge.node === allowlistName), 'prepare does not connect directly to allowlist');
  check(allowlistOutputs[0]?.some((edge) => edge.node === 'Claim send key before SMTP'), 'allowlist true branch does not connect directly to claim');
  check(allowlistOutputs[1]?.some((edge) => edge.node === rejectName), 'allowlist false branch does not fail loud');
  check(condition?.leftValue === '={{ $json.email_from }}', 'allowlist does not inspect email_from');
  check(condition?.rightValue === 'REPLACE_WITH_KAAN_TEST_RECIPIENT', 'tracked export must contain only the recipient placeholder');
  check(reject.parameters.jsCode.includes('Recipient is not on the Gate 4 test allowlist; nothing was sent.'), 'allowlist rejection message changed');
});

run('Workflow 3 drops an already-claimed item without an execution error', () => {
  const workflow = load('GGD-03-approved-send.json');
  const node = nodeByName(workflow, 'Continue only for new claim');
  const result = runPerItemCode(node, {body: false}, {
    'Prepare exact reviewed send': {id: 42},
  });
  check(result === null, 'duplicate claim path must return null');
});

run('Workflow 4 contains both reply and bounce recording paths', () => {
  const workflow = load('GGD-04-reply-and-bounce-intake.json');
  const urls = workflow.nodes.map((node) => String(node.parameters.url || ''));
  check(urls.some((url) => url.endsWith('/ggd_record_reply')), 'missing reply recorder');
  check(urls.some((url) => url.endsWith('/ggd_record_bounce')), 'missing bounce recorder');
  check(!workflow.nodes.some((node) => node.type === 'n8n-nodes-base.emailSend'), 'reply workflow may not send email');
});

run('Workflow 4 routes exact, ambiguous, and unsafe bounce matches correctly', () => {
  const workflow = load('GGD-04-reply-and-bounce-intake.json');
  const node = nodeByName(workflow, 'Require one unambiguous match');
  const inbound = {
    sender: 'fictional@example.invalid',
    subject: 'Fictional reply',
    message_id: '<reply@example.invalid>',
    is_bounce: false,
  };
  const lookup = {'Normalize and sanitize inbound email': inbound};

  const exact = runPerItemCode(node, {
    match_type: 'message_id',
    candidates: [{id: 17, ggd_do_not_contact: false}],
  }, lookup);
  check(exact.json.matched === true && exact.json.lead_id === 17, 'exact match did not continue');

  const ambiguous = runPerItemCode(node, {
    match_type: 'sender',
    candidates: [{id: 17}, {id: 18}],
  }, lookup);
  check(ambiguous.json.matched === false && ambiguous.json.candidate_ids.length === 2, 'ambiguous match did not enter review');

  const unsafeBounce = runPerItemCode(node, {
    match_type: 'sender',
    candidates: [{id: 17}],
  }, {'Normalize and sanitize inbound email': {...inbound, is_bounce: true}});
  check(unsafeBounce.json.matched === false, 'sender-only bounce must not update delivery state');
});

run('Workflow 4 keeps IMAP retry-safe and persists unmatched mail in Odoo', () => {
  const workflow = load('GGD-04-reply-and-bounce-intake.json');
  const imap = nodeByName(workflow, 'Zoho IMAP inbox');
  const edges = graph(workflow);
  const review = nodeByName(workflow, 'Queue unmatched inbound for Odoo review');
  check(imap.typeVersion >= 2.2, 'IMAP node needs persistent message tracking');
  check(imap.parameters.postProcessAction === 'nothing', 'IMAP must not mark mail read before durable handling');
  check(String(review.parameters.url).endsWith('/ggd_queue_unmatched_inbound'), 'missing unmatched-inbound Odoo method');
  check(reaches(edges, 'Require one unambiguous match', review.name), 'unmatched branch does not reach Odoo review');
});

run('Workflow 1 selects the visible GGD research source field', () => {
  const workflow = load('GGD-01-lead-qualification.json');
  const selector = nodeByName(workflow, 'Select unqualified opportunities');
  const fetch = nodeByName(workflow, 'Fetch approved public company page');
  check(String(selector.parameters.jsonBody).includes('ggd_source_url'), 'selector ignores ggd_source_url');
  check(String(fetch.parameters.url).includes('approved_source_url'), 'fetch bypasses the validated source URL');
});

run('Workflows 1 and 2 park records already marked for automation review', () => {
  const qualification = load('GGD-01-lead-qualification.json');
  const drafting = load('GGD-02-draft-approval-queue.json');
  const qualificationDomain = String(nodeByName(qualification, 'Select unqualified opportunities').parameters.jsonBody);
  const draftingDomain = String(nodeByName(drafting, 'Select qualified leads without drafts').parameters.jsonBody);
  check(qualificationDomain.includes("['ggd_automation_needs_review','=',false]"), 'qualification selector retries parked records');
  check(draftingDomain.includes("['ggd_automation_needs_review','=',false]"), 'draft selector retries parked records');
});

run('Workflow 1 rejects direct internal and non-HTTP source URLs before fetch', () => {
  const workflow = load('GGD-01-lead-qualification.json');
  const node = nodeByName(workflow, 'One qualification candidate per item');
  const accepted = runAllItemsCode(node, [{id: 1, ggd_source_url: 'https://example.invalid/about'}]);
  check(accepted[0].json.approved_source_url === 'https://example.invalid/about', 'public HTTPS URL was not accepted');
  for (const blocked of ['http://odoo:8069/web', 'http://127.0.0.1/test', 'ftp://example.invalid/file']) {
    let rejected = false;
    try { runAllItemsCode(node, [{id: 2, ggd_source_url: blocked}]); } catch { rejected = true; }
    check(rejected, `unsafe source URL was accepted: ${blocked}`);
  }
});

run('Workflow 5 uses the weekday 08:30 schedule and deduplicating Odoo method', () => {
  const workflow = load('GGD-05-daily-follow-up.json');
  const serialized = JSON.stringify(workflow);
  check(serialized.includes('30 8 * * 1-5'), 'incorrect follow-up schedule');
  check(serialized.includes('/ggd_queue_follow_up'), 'missing deduplicating follow-up call');
  check(!workflow.nodes.some((node) => node.type === 'n8n-nodes-base.emailSend'), 'follow-up workflow may not send email');
});

run('Only Workflow 3 contains an email-send node', () => {
  for (const file of required) {
    const count = load(file).nodes.filter((node) => node.type === 'n8n-nodes-base.emailSend').length;
    check(count === (file === 'GGD-03-approved-send.json' ? 1 : 0), `${file} has an unexpected email-send count`);
  }
});

run('Workflow 3 cannot draft or call an LLM after human approval', () => {
  const workflow = load('GGD-03-approved-send.json');
  check(!workflow.nodes.some((node) => node.type.startsWith('@n8n/n8n-nodes-langchain.')), 'send workflow contains an LLM node');
});

run('All LLM workflows pin one identical current Anthropic model', () => {
  const llmFiles = [
    'GGD-01-lead-qualification.json',
    'GGD-02-draft-approval-queue.json',
    'GGD-04-reply-and-bounce-intake.json',
    'GGD-05-daily-follow-up.json',
  ];
  const retired = new Set(['claude-sonnet-4-20250514']);
  const models = [];
  for (const file of llmFiles) {
    const nodes = load(file).nodes.filter((node) => node.type === '@n8n/n8n-nodes-langchain.lmChatAnthropic');
    check(nodes.length === 1, `${file} must contain exactly one Anthropic model node`);
    const model = nodes[0].parameters.model?.value;
    check(typeof model === 'string' && model.length > 0, `${file} has no pinned model ID`);
    check(!retired.has(model), `${file} pins a retired model ID`);
    models.push(model);
  }
  check(new Set(models).size === 1, `LLM workflows pin different models: ${models.join(', ')}`);
  check(models[0] === 'claude-sonnet-5', `unexpected live-selected model: ${models[0]}`);
});

run('Workflow 3 fails closed at claim and records uncertain SMTP or finalize results', () => {
  const workflow = load('GGD-03-approved-send.json');
  check(!nodeByName(workflow, 'Claim send key before SMTP').onError, 'claim errors may continue toward SMTP');
  check(nodeByName(workflow, 'Send exact reviewed draft via Zoho').onError === 'continueErrorOutput', 'SMTP errors are not routed for uncertain-send review');
  check(nodeByName(workflow, 'Finalize complete send audit in Odoo').onError === 'continueErrorOutput', 'finalize errors are not routed for uncertain-send review');
});

run('All workflow credential references remain explicit placeholders', () => {
  for (const file of required) {
    for (const node of load(file).nodes) {
      for (const credential of Object.values(node.credentials || {})) {
        check(String(credential.id || '').startsWith('REPLACE_WITH_'), `${file}/${node.name} has a non-placeholder credential id`);
      }
    }
  }
});

run('Every Odoo workflow call uses the local JSON-2 crm.lead endpoint', () => {
  for (const file of required) {
    for (const node of load(file).nodes) {
      const url = String(node.parameters.url || '');
      if (url.includes('odoo:8069')) check(/^http:\/\/odoo:8069\/json\/2\/crm\.lead\//.test(url), `${file}/${node.name} uses an unexpected Odoo endpoint`);
    }
  }
});

run('Workflow 4 routes bounce and ordinary reply branches to their durable Odoo recorders', () => {
  const workflow = load('GGD-04-reply-and-bounce-intake.json');
  const branch = workflow.connections['Is delivery bounce']?.main || [];
  check(branch[0]?.some((edge) => edge.node === 'Record matched bounce in Odoo'), 'bounce branch misses ggd_record_bounce');
  check(branch[1]?.some((edge) => edge.node === 'Classify sanitized reply'), 'ordinary reply branch misses classification');
  check(reaches(graph(workflow), 'Classify sanitized reply', 'Record reply and response draft in Odoo'), 'ordinary reply branch misses ggd_record_reply');
});

// n8n runs Code nodes with vm.runInContext against a bare context, so Node
// globals that exist in this process do NOT exist there. runAllItemsCode uses
// `new Function`, which inherits this process's globals, so it happily passes
// code that cannot run in n8n at all. A guard written with `new URL()` shipped
// green through this suite and then rejected every URL in production, because
// the ReferenceError landed in its catch block. These two tests close that gap.

run('No workflow Code node relies on globals the n8n sandbox does not provide', () => {
  const unavailable = ['new URL(', 'URLSearchParams', 'fetch(', 'structuredClone(', 'TextEncoder', 'TextDecoder'];
  for (const file of required) {
    for (const node of load(file).nodes) {
      const code = node.parameters?.jsCode;
      if (typeof code !== 'string') continue;
      for (const token of unavailable) {
        check(!code.includes(token), `${file}/${node.name} uses ${token}, undefined in the n8n Code sandbox`);
      }
    }
  }
});

run('Workflow 1 source-URL guard behaves correctly inside a bare vm sandbox', () => {
  const vm = require('vm');
  const node = nodeByName(load('GGD-01-lead-qualification.json'), 'One qualification candidate per item');
  const runSandboxed = (rows) => {
    const context = vm.createContext({$input: {all: () => rows.map((row) => ({json: row}))}});
    return vm.runInContext(`(function(){${node.parameters.jsCode}})()`, context);
  };

  const accepted = runSandboxed([{id: 1, ggd_source_url: 'https://example.invalid/about'}]);
  check(accepted[0].json.approved_source_url === 'https://example.invalid/about', 'public HTTPS URL was not accepted in the sandbox');

  const blocked = [
    'http://odoo:8069/web',
    'http://127.0.0.1/test',
    'ftp://example.invalid/file',
    'http://192.168.1.5/x',
    'https://trusted.example.invalid@127.0.0.1/x',
    'http://[::1]/x',
  ];
  for (const url of blocked) {
    let rejected = false;
    try { runSandboxed([{id: 2, ggd_source_url: url}]); } catch { rejected = true; }
    check(rejected, `unsafe source URL was accepted in the sandbox: ${url}`);
  }
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed) process.exit(1);
