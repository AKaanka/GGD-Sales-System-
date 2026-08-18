const src = $('Validate and sanitize reply').first().json;

function itemsFrom(nodeName) {
  try {
    return $(nodeName).all()
      .map(function (i) { return i.json; })
      .filter(function (r) { return r && r.id; });
  } catch (e) {
    return [];
  }
}

var candidates = itemsFrom('Get many opportunities');
var threadCandidates = itemsFrom('Get opportunities by thread');

function normEmail(v) {
  var s = String(v || '').trim().toLowerCase();
  var m = s.match(/<([^>]+)>/);
  return (m ? m[1] : s).trim();
}
function normMsgId(v) {
  return String(v || '').trim().replace(/^</, '').replace(/>$/, '');
}

var senderEmail = normEmail(src.sender_email || src.from || src.email_from);
var threadIds = []
  .concat(src.in_reply_to || [])
  .concat(String(src.references || '').split(/\s+/))
  .map(normMsgId)
  .filter(Boolean);

var candidateIds = candidates.map(function (c) { return c.id; });
var describe = function (list) {
  return list.map(function (c) { return c.id + ' ' + (c.name || ''); }).join('; ');
};

function base(o) {
  return Object.assign({
    ggd_reply_analysis_allowed: false,
    matched_by: null,
    opportunity_id: null,
    id: null,
    candidate_ids: candidateIds,
    thread_candidate_ids: threadCandidates.map(function (c) { return c.id; }),
    thread_ids: threadIds,
    sender_email: senderEmail,
    needs_thread_fallback: false,
    manual_review_unrouted: false,
    review_reason: null
  }, o);
}

function matched(by, id) {
  return [{ json: base({ ggd_reply_analysis_allowed: true, matched_by: by, opportunity_id: id, id: id }) }];
}

// One review note per candidate, so whichever record a human opens shows it.
function review(reason, list, extra) {
  var targets = list && list.length ? list : [];
  if (!targets.length) {
    return [{ json: base(Object.assign({ review_reason: reason, manual_review_unrouted: true }, extra || {})) }];
  }
  return targets.map(function (c) {
    return { json: base(Object.assign({ id: c.id, review_reason: reason }, extra || {})) };
  });
}

// Row 0 - explicit id supplied (manual / fixture test path only)
if (src.opportunity_id) {
  return matched('explicit_id', Number(src.opportunity_id));
}

// Rows 1-2 - thread header confirms exactly one sender candidate
var threadHits = candidates.filter(function (c) {
  return c.ggd_last_message_id && threadIds.indexOf(normMsgId(c.ggd_last_message_id)) !== -1;
});
if (threadHits.length === 1) {
  return matched('thread', threadHits[0].id);
}

// Row 3 - exactly one sender candidate, no usable thread header
if (candidates.length === 1 && threadHits.length === 0) {
  return matched('sender_only', candidates[0].id);
}

// Row 4 - no sender candidate: fall back to the thread search
if (candidates.length === 0) {
  if (threadCandidates.length === 1) {
    return matched('thread_fallback', threadCandidates[0].id);
  }
  if (threadCandidates.length > 1) {
    return review('Thread header matched ' + threadCandidates.length + ' opportunities (' + describe(threadCandidates) + '). Manual review required.', threadCandidates);
  }
  return review('No opportunity matched sender ' + senderEmail + ' and the thread header resolved nothing.', [], { needs_thread_fallback: threadIds.length > 0 });
}

// Rows 5-6 - manual review, no Odoo field writes on any record
return review('Ambiguous sender ' + senderEmail + ': ' + candidates.length + ' opportunities match (' + describe(candidates) + '). No thread header resolved it.', candidates);
