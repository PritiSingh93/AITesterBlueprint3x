## Test Plan: KAN-4 — Login button not working on Chrome (v114)

- JIRA ID: KAN-4
- Source: JIRA (read-only)

### Objective
Login button not working on Chrome (v114)

### Description
When attempting to log in using Chrome version 114, the login button does not respond after entering valid credentials. The issue is reproducible consistently on Windows 10.

*Steps to Reproduce:*

## Navigate to [https://app.example.com/login](https://app.example.com/login)

## Enter valid username and password

## Click on the *Login* button

## Observe that nothing happens
*Expected Result:* User should be redirected to the dashboard after successful login.

*Actual Result:* Login button appears clickable but no action is triggered. No error message is displayed.

*Environment:*

- Browser: Chrome 114.0.5735.110
- OS: Windows 10 Pro (64-bit)
- Device: Dell Latitude 5420
- Network: Office Wi-Fi

### Acceptance Criteria

### Scope

- In scope: Produce a formal Test Plan markdown file containing Objective, Scope, Strategy, Entry/Exit Criteria, Risks, Assumptions, Dependencies, Traceability, and Sign-off sections.
- Out of scope: Individual test cases, automated test scripts, or JIRA edits.

### Strategy

- Use the JIRA issue fields to populate plan sections.
- Reuse VWO template structure where applicable.

### Entry Criteria

- Read-only access to the JIRA issue via API token in .env or supplied credentials.

### Exit Criteria

- A markdown Test Plan file saved at chapter_03_BLAST_FW/KAN-4_Test_Plan.md and returned in the response.

### Risks

- JIRA fields may be incomplete or ambiguous.
- API rate limits or authentication failures.

### Assumptions

- JIRA issue contains sufficient details.

### Dependencies

- Atlassian JIRA (read-only) via API

### Traceability

- Source: JIRA issue KAN-4

### Sign-off

- Test Lead: ___________________
- Product Owner: ___________________
