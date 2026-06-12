const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');
const { fetchJiraIssue } = require('./jira');

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));

const PORT = process.env.PORT || 4000;

// Use `fetchJiraIssue` from ./jira which reads from process.env when parameters omitted

async function callGroq(groqUrl, groqKey, prompt) {
  const res = await fetch(groqUrl, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${groqKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'open-gpt-120billion',
      prompt: prompt,
      max_tokens: 2000
    })
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`GROQ API failed: ${res.status} ${txt}`);
  }
  const data = await res.json();
  // Attempt to extract text from common shapes
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
  const summary = fields.summary || ''
  const description = (fields.description || '').split('\n').slice(0,3).join(' ')
  const labels = (fields.labels || []).join(', ')

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
`
}

app.post('/api/generate', async (req, res) => {
  try {
    console.log('[api/generate] request body:', JSON.stringify(req.body).slice(0,2000))
    const {
      jiraBaseUrl,
      jiraEmail,
      jiraToken,
      groqApiUrl,
      groqApiKey,
      jiraId,
      useGroq
    } = req.body;

    let fields = {};
    // Allow passing mockFields for local verification/testing without contacting JIRA
    if (req.body.mockFields) {
      fields = req.body.mockFields;
    } else {
      const jiraParams = { jiraBaseUrl, email: jiraEmail, token: jiraToken, jiraId };
      try {
        // if values missing, fetchJiraIssue will read from process.env
        const issue = await fetchJiraIssue(jiraParams);
        fields = issue.fields || {};
      } catch (jiraErr) {
        console.warn('[api/generate] fetchJiraIssue failed, using fallback fields:', jiraErr.message)
        // Provide a minimal fallback so the generator and client always have fields to work with
        fields = {
          summary: `${jiraId} (JIRA unavailable)`,
          description: `Unable to fetch JIRA issue ${jiraId}. Using fallback description.`,
          labels: []
        }
      }
    }

    if (useGroq && groqApiUrl && groqApiKey) {
      const prompt = `You are an automation assistant following the VWO test plan template.\n` +
        `Produce a Formal Test Plan in Markdown for JIRA issue ${jiraId}.\n` +
        `Use the following fields and DO NOT include individual test cases. Use sections: Objective, Scope, Strategy, Entry/Exit Criteria, Risks, Assumptions, Dependencies, Traceability, Sign-off.\n` +
        `JIRA Summary: ${fields.summary || ''}\n` +
        `JIRA Description: ${fields.description || ''}\n` +
        `Acceptance Criteria: ${(fields.customfield_10000 && fields.customfield_10000.value) || ''}\n` +
        `Labels: ${(fields.labels || []).join(', ')}\n` +
        `Adhere to the VWO template and produce a markdown document.`;

      const generated = await callGroq(groqApiUrl, groqApiKey, prompt);
      // Also return a deterministic strategy derived from fields for UI display
      const strategy = buildTestStrategyMarkdown({ jiraId, fields })
      return res.json({ markdown: generated, strategy, fields });
    }

    const markdown = buildTestPlanMarkdown({ jiraId, fields });
    const strategy = buildTestStrategyMarkdown({ jiraId, fields })
    return res.json({ markdown, strategy, fields });
  } catch (err) {
    console.error('[api/generate] error:', err && err.stack ? err.stack : err)
    const msg = (err && err.message) ? err.message : 'unknown error'
    return res.status(500).json({ error: msg, detail: (err && err.stack) ? err.stack.split('\n').slice(0,5).join('\n') : undefined });
  }
});

app.post('/api/save', async (req, res) => {
  try {
    const { jiraId, markdown } = req.body;
    if (!jiraId || !markdown) return res.status(400).json({ error: 'Missing jiraId or markdown' });
    const outDir = path.join(__dirname, '..');
    const fileName = `${jiraId}_Test_Plan.md`;
    const filePath = path.join(outDir, fileName);
    fs.writeFileSync(filePath, markdown, 'utf8');
    return res.json({ saved: true, path: filePath });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
});

app.post('/api/save-strategy', async (req, res) => {
  try {
    const { jiraId, strategy } = req.body;
    if (!jiraId || !strategy) return res.status(400).json({ error: 'Missing jiraId or strategy' });
    const outDir = path.join(__dirname, '..');
    const fileName = `${jiraId}_Test_Strategy.md`;
    const filePath = path.join(outDir, fileName);
    fs.writeFileSync(filePath, strategy, 'utf8');
    return res.json({ saved: true, path: filePath });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
});

// Serve static client in production (if built)
const clientBuild = path.join(__dirname, '..', 'client', 'dist');
app.use(express.static(clientBuild));
app.get('*', (req, res) => {
  res.sendFile(path.join(clientBuild, 'index.html'));
});

app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
