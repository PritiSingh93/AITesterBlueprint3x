# Test Plan: KAN-5 — Dropdown menu overlaps footer on mobile view

- JIRA ID: KAN-5
- Source: JIRA (read-only)

## Objective
Dropdown menu overlaps footer on mobile view

## Description
*Description:*   On mobile devices, the navigation dropdown menu expands beyond the viewport and overlaps the footer section. This makes the footer links inaccessible. The issue occurs only in portrait orientation.

*Steps to Reproduce:*

# Open {{https://app.example.com}} on a mobile device (tested on iPhone 13, Safari).
# Tap the hamburger menu in the top‑right corner.
# Scroll down to the bottom of the expanded dropdown.
# Observe that the footer is hidden behind the dropdown.

*Expected Result:*   Dropdown menu should collapse within the viewport and footer should remain visible.

*Actual Result:*   Dropdown menu overlaps footer, blocking access to footer links.

*Environment:*

* Device: iPhone 13
* OS: iOS 17.3
* Browser: Safari Mobile
* Orientation: Portrait

## Acceptance Criteria


## Scope
- In scope: Produce a formal Test Plan markdown file containing Objective, Scope, Strategy, Entry/Exit Criteria, Risks, Assumptions, Dependencies, Traceability, and Sign-off sections.
- Out of scope: Individual test cases, automated test scripts, or JIRA edits.

## Strategy
- Use the JIRA issue fields to populate plan sections.
- Reuse VWO template structure where applicable.

## Entry Criteria
- Read-only access to the JIRA issue via API token in .env or supplied credentials.

## Exit Criteria
- A markdown Test Plan file saved at chapter_03_BLAST_FW/KAN-5_Test_Plan.md and returned in the response.

## Risks
- JIRA fields may be incomplete or ambiguous.
- API rate limits or authentication failures.

## Assumptions
- JIRA issue contains sufficient details.

## Dependencies
- Atlassian JIRA (read-only) via API

## Traceability
- Source: JIRA issue KAN-5

## Sign-off
- Test Lead: ___________________
- Product Owner: ___________________

---

