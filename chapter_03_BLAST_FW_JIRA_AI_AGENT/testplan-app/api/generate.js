const fetch = require('node-fetch');

async function fetchJiraIssue({ jiraBaseUrl, email, token, jiraId }) {
  const base = (jiraBaseUrl || process.env.JIRA_URL || '').replace(/\/$/, '');
  const url = `${base}/rest/api/2/issue/${jiraId}?fields=summary,description,labels,issuetype,project,customfield_10000`;
  const auth = Buffer.from(`${email || process.env.JIRA_EMAIL}:${token || process.env.JIRA_TOKEN}`).toString('base64');
  const res = await fetch(url, {
    headers: { Authorization: `Basic ${auth}`, Accept: 'application/json' }
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`JIRA fetch failed: ${res.status} ${txt}`);
  }
  return res.json();
}

async function callGroq(groqUrl, groqKey, prompt) {
  const res = await fetch(groqUrl, {
    method: 'POST',
    headers: { Authorization: `Bearer ${groqKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'open-gpt-120billion', prompt, max_tokens: 2000 })
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`GROQ API failed: ${res.status} ${txt}`);
  }
  const data = await res.json();
  return data.text || data.output || data.result || JSON.stringify(data);
}

function buildTestPlanMarkdown({ jiraId, fields }) {
  const summary = fields.summary || '';
  const description = fields.description || '';
  const labels = (fields.labels || []).join(', ');
  const acceptance = (fields.customfield_10000 && fields.customfield_10000.value) || '';

  return `# Test Plan: ${jiraId} — ${summary}

- JIRA ID: ${jiraId}
- Source: JIRA (read-only)

## Objective
${summary}

## Description
${description}

## Acceptance Criteria
${acceptance}

## Scope
- In scope: Produce a formal Test Plan markdown file containing Objective, Scope, Strategy, Entry/Exit Criteria, Risks, Assumptions, Dependencies, Traceability, and Sign-off sections.
- Out of scope: Individual test cases, automated test scripts, or JIRA edits.

## Strategy
- Use the JIRA issue fields to populate plan sections.
- Reuse VWO template structure where applicable.

## Entry Criteria
- Read-only access to the JIRA issue via API token in .env or supplied credentials.

## Exit Criteria
- A markdown Test Plan file saved at chapter_03_BLAST_FW/${jiraId}_Test_Plan.md and returned in the response.

## Risks
- JIRA fields may be incomplete or ambiguous.
- API rate limits or authentication failures.

## Assumptions
- JIRA issue contains sufficient details.

## Dependencies
- Atlassian JIRA (read-only) via API

## Traceability
- Source: JIRA issue ${jiraId}

## Sign-off
- Test Lead: ___________________
- Product Owner: ___________________

---

`;
}

function buildTestStrategyMarkdown({ jiraId, fields }) {
  const summary = fields.summary || '';
  const description = (fields.description || '').split('\n').slice(0, 3).join(' ');
  const labels = (fields.labels || []).join(', ');

  return `# Test Strategy: ${jiraId}

**Objective:** ${summary}

**Approach:**
- Focus on reproducing the reported issue using lightweight exploratory tests.
- Prioritise browser compatibility checks (Chrome ${labels || 'latest'}, Windows 10) and network/environment permutations.
- Reproduce using the minimal steps from the issue, then broaden to regression flows.

**Scope & Focus Areas:**
- UI interaction flows around login (form validation, button click handlers, client-side JS errors).
- Backend auth endpoints and CORS/network issues if repro suggests requests are sent.
- Environment matrix: Browser versions, OS, network conditions.

**Entry Criteria:**
- Access to the JIRA issue and environment details.

**Exit Criteria:**
- Reproduction steps documented and root-cause hypothesis produced, plus recommended regression checks.

**Notes:**
- Source: JIRA issue ${jiraId}
`;
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }
  try {
    const {
      jiraBaseUrl, jiraEmail, jiraToken,
      groqApiUrl, groqApiKey, jiraId, useGroq
    } = req.body;

    let fields = {};
    if (req.body.mockFields) {
      fields = req.body.mockFields;
    } else {
      try {
        const issue = await fetchJiraIssue({ jiraBaseUrl, email: jiraEmail, token: jiraToken, jiraId });
        fields = issue.fields || {};
      } catch (jiraErr) {
        console.warn('[api/generate] JIRA unavailable:', jiraErr.message);
        fields = {
          summary: `${jiraId} (JIRA unavailable)`,
          description: `Unable to fetch JIRA issue ${jiraId}. Using fallback description.`,
          labels: []
        };
      }
    }

    if (useGroq && groqApiUrl && groqApiKey) {
      const prompt =
        `You are an automation assistant following the VWO test plan template.\n` +
        `Produce a Formal Test Plan in Markdown for JIRA issue ${jiraId}.\n` +
        `Use the following fields and DO NOT include individual test cases. Use sections: Objective, Scope, Strategy, Entry/Exit Criteria, Risks, Assumptions, Dependencies, Traceability, Sign-off.\n` +
        `JIRA Summary: ${fields.summary || ''}\n` +
        `JIRA Description: ${fields.description || ''}\n` +
        `Acceptance Criteria: ${(fields.customfield_10000 && fields.customfield_10000.value) || ''}\n` +
        `Labels: ${(fields.labels || []).join(', ')}\n` +
        `Adhere to the VWO template and produce a markdown document.`;
      const generated = await callGroq(groqApiUrl, groqApiKey, prompt);
      const strategy = buildTestStrategyMarkdown({ jiraId, fields });
      return res.status(200).json({ markdown: generated, strategy, fields });
    }

    const markdown = buildTestPlanMarkdown({ jiraId, fields });
    const strategy = buildTestStrategyMarkdown({ jiraId, fields });
    return res.status(200).json({ markdown, strategy, fields });
  } catch (err) {
    console.error('[api/generate] error:', err.stack || err.message);
    return res.status(500).json({ error: err.message });
  }
};
