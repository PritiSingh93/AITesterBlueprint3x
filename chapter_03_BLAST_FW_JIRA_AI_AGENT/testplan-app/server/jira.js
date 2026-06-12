const fetch = require('node-fetch');

async function fetchJiraIssue({ jiraBaseUrl, email, token, jiraId }) {
  const base = (jiraBaseUrl || process.env.JIRA_URL || '').replace(/\/$/, '');
  const url = `${base}/rest/api/2/issue/${jiraId}?fields=summary,description,labels,issuetype,project,customfield_10000`;
  const auth = Buffer.from(`${email || process.env.JIRA_EMAIL}:${token || process.env.JIRA_TOKEN}`).toString('base64');
  const res = await fetch(url, {
    headers: {
      Authorization: `Basic ${auth}`,
      Accept: 'application/json'
    }
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`JIRA fetch failed: ${res.status} ${txt}`);
  }
  return res.json();
}

module.exports = { fetchJiraIssue };
