"""Generate 2,000 VWO test cases as a Jira-import-friendly CSV.

Deterministic (seeded) so re-runs produce a stable file. Output columns are
aligned with the Advanced RAG ingester defaults:

    text-cols : title, steps, expected, tags
    meta-cols : id, jira_id, priority, module

Each row also carries a Jira issue key (``jira_id`` = ``VWO-####``) plus
``preconditions`` so the file doubles as a Jira test-case import.

Usage
-----
    python generate_testcases.py            # writes VWO_2000_Test_Cases.csv
    python generate_testcases.py --rows 500 --out sample.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

# --------------------------------------------------------------------------- #
# Domain model: VWO (Visual Website Optimizer) product areas + their features. #
# --------------------------------------------------------------------------- #

MODULES: dict[str, list[str]] = {
    "Login": [
        "page load", "email field visibility", "password field visibility",
        "Login button enabled state", "Remember Me checkbox", "Forgot Password link",
        "registration link", "password masking", "keyboard tab order",
        "Enter-key submission", "email auto-focus", "invalid credentials error",
        "empty email validation", "empty password validation", "SSO login button",
        "Google OAuth login", "account lockout after 5 attempts", "rate limiting",
        "session timeout", "loading indicator", "successful dashboard redirect",
        "captcha on repeated failures", "unicode email support", "trailing space trim",
    ],
    "Signup": [
        "workspace name field", "email uniqueness check", "password strength meter",
        "terms of service checkbox", "verification email dispatch", "email verification link expiry",
        "duplicate account prevention", "company size dropdown", "role selection",
        "invite teammate step", "free trial activation", "billing skip on trial",
        "welcome onboarding wizard", "resend verification email", "GDPR consent capture",
    ],
    "Dashboard": [
        "widget grid layout", "campaign summary cards", "date range picker",
        "quick-create button", "recent activity feed", "empty state for new account",
        "search across campaigns", "favorites pinning", "responsive mobile layout",
        "dark mode toggle", "notification bell badge", "account switcher",
        "loading skeletons", "refresh data button", "keyboard shortcuts panel",
    ],
    "AB Testing": [
        "create A/B campaign", "add variation", "clone variation", "traffic allocation split",
        "primary goal selection", "secondary metrics", "URL targeting rules",
        "audience segment attach", "preview variation", "start campaign",
        "pause campaign", "resume campaign", "stop campaign with winner",
        "declare winner manually", "statistical significance display", "confidence interval chart",
        "sample size calculator", "variation weight rebalance", "scheduling start/end date",
        "campaign duplication", "archive campaign", "SmartStats Bayesian engine",
    ],
    "Split URL Testing": [
        "create split URL test", "add competing URLs", "redirect rule setup",
        "query param preservation", "traffic distribution", "goal mapping across URLs",
        "preview redirects", "mobile redirect behavior", "301 vs client-side redirect",
        "flicker prevention", "start split test", "cross-domain redirect",
    ],
    "Multivariate Testing": [
        "create MVT campaign", "define sections", "add elements per section",
        "combination generation", "full factorial matrix", "combination limit warning",
        "traffic per combination", "element-level insights", "top combination ranking",
        "interaction effects report", "preview combination", "launch MVT",
    ],
    "Visual Editor": [
        "load editor on target URL", "select element", "edit text inline",
        "change element color", "hide element", "rearrange via drag-and-drop",
        "insert custom HTML", "add custom CSS", "add custom JavaScript",
        "move element position", "resize image", "undo change", "redo change",
        "revert all changes", "responsive breakpoint editing", "editor iframe cross-origin",
        "save variation", "editor on SPA route change", "element highlight on hover",
    ],
    "Heatmaps": [
        "enable heatmap capture", "click map rendering", "scroll map rendering",
        "move map rendering", "device segmentation", "heatmap for variation",
        "date range filter", "screenshot capture accuracy", "dynamic content heatmap",
        "export heatmap image", "element attention score", "sample threshold display",
    ],
    "Session Recordings": [
        "start recording capture", "recording list pagination", "playback controls",
        "playback speed control", "skip inactivity toggle", "rage-click detection",
        "u-turn detection", "console log capture", "network capture masking",
        "PII field masking", "filter by duration", "filter by segment",
        "share recording link", "delete recording", "recording storage quota",
    ],
    "Funnels": [
        "create funnel", "add funnel steps", "reorder steps", "step drop-off rate",
        "conversion rate per step", "segment comparison", "date range analysis",
        "funnel for campaign", "biggest drop-off highlight", "export funnel data",
    ],
    "Forms Analytics": [
        "enable form tracking", "field interaction time", "drop-off field detection",
        "error field frequency", "field re-entry count", "hesitation time metric",
        "conversion vs abandonment", "multi-step form tracking", "export form report",
    ],
    "Surveys": [
        "create on-page survey", "add multiple choice question", "add rating question",
        "add open text question", "survey trigger on scroll", "survey trigger on exit intent",
        "targeting by URL", "survey response collection", "NPS score calculation",
        "response sentiment tagging", "survey scheduling", "thank you message",
        "survey display frequency cap", "mobile survey layout",
    ],
    "Goals": [
        "create revenue goal", "create click goal", "create page-visit goal",
        "create form-submit goal", "create engagement goal", "custom conversion goal",
        "goal value assignment", "duplicate goal detection", "goal edit propagation",
    ],
    "Segmentation": [
        "create custom segment", "segment by device", "segment by browser",
        "segment by geography", "segment by traffic source", "segment by new vs returning",
        "segment by custom dimension", "combine segments with AND/OR", "save segment",
        "apply segment to report", "segment by cookie value", "segment by day of week",
    ],
    "Audience Targeting": [
        "target by URL pattern", "target by referrer", "target by UTM params",
        "target by geolocation", "target by device type", "target by cookie",
        "target by JavaScript condition", "target by day and time", "target by visitor behavior",
        "exclude audience rule", "percentage of traffic include", "returning visitor targeting",
    ],
    "Reports": [
        "campaign report load", "conversion rate table", "improvement percentage",
        "probability to beat baseline", "revenue per visitor", "trend chart over time",
        "compare variations chart", "export report CSV", "export report PDF",
        "schedule email report", "share report link", "report data freshness",
    ],
    "Integrations": [
        "connect Google Analytics", "connect Google Analytics 4", "connect Segment",
        "connect Hotjar", "connect Salesforce", "connect Slack notifications",
        "connect webhook endpoint", "connect Zapier", "connect HubSpot",
        "disconnect integration", "integration auth token refresh", "integration health status",
    ],
    "Account Settings": [
        "update profile name", "change account email", "change password",
        "enable two-factor auth", "manage active sessions", "set timezone",
        "set default currency", "notification preferences", "delete account request",
        "data export request", "API key generation", "API key revocation",
    ],
    "Team Permissions": [
        "invite team member", "assign admin role", "assign editor role",
        "assign viewer role", "revoke access", "resend invite",
        "pending invite expiry", "role-based feature gating", "transfer ownership",
        "workspace-level permissions", "SSO enforced login", "audit log of role changes",
    ],
    "Billing": [
        "view current plan", "upgrade plan", "downgrade plan", "add payment method",
        "update credit card", "view invoices", "download invoice PDF", "apply coupon code",
        "MTU usage meter", "overage warning", "cancel subscription", "reactivate subscription",
        "proration on mid-cycle upgrade", "tax/VAT field", "failed payment retry",
    ],
    "SmartCode": [
        "install SmartCode snippet", "async loading verification", "SmartCode version detection",
        "data collection consent mode", "single-page-app SmartCode", "SmartCode via GTM",
        "settings SmartCode toggle", "anti-flicker snippet", "SmartCode diagnostics tool",
    ],
    "Feature Rollout": [
        "create feature flag", "toggle flag on/off", "percentage rollout", "target flag by segment",
        "flag variable values", "kill switch", "flag rollback", "environment-specific flags",
        "flag change audit", "SDK key retrieval",
    ],
    "Personalization": [
        "create personalization campaign", "define audience", "add personalized content",
        "priority ordering of campaigns", "frequency capping", "goal for personalization",
        "preview personalization", "start personalization", "mutually exclusive groups",
    ],
    "API Webhooks": [
        "authenticate REST API", "list campaigns endpoint", "create campaign via API",
        "rate limit headers", "pagination cursors", "webhook signature verification",
        "webhook retry on failure", "webhook payload schema", "API error 4xx handling",
        "API error 5xx handling", "bulk export endpoint",
    ],
}

PRECONDITIONS = {
    "Login": "The VWO login page is reachable in a supported test environment and no user session is active.",
    "Signup": "A clean browser session with no existing VWO account for the test email.",
    "Dashboard": "A verified user is logged in with at least one workspace provisioned.",
    "AB Testing": "A logged-in user with editor rights and a reachable target website.",
    "Split URL Testing": "A logged-in user with two or more valid destination URLs available.",
    "Multivariate Testing": "A logged-in editor on a page containing multiple editable sections.",
    "Visual Editor": "The Visual Editor can load the target URL and the SmartCode is installed.",
    "Heatmaps": "A running campaign with heatmap capture enabled and traffic recorded.",
    "Session Recordings": "Session recording is enabled and at least one visitor session is captured.",
    "Funnels": "A workspace with tracked pages and recorded conversion data.",
    "Forms Analytics": "A page containing a tracked form with recorded visitor interactions.",
    "Surveys": "A logged-in user with survey builder access on a live target page.",
    "Goals": "A campaign or workspace where conversion goals can be defined.",
    "Segmentation": "A workspace with report data available for at least one campaign.",
    "Audience Targeting": "A draft campaign where targeting rules can be configured.",
    "Reports": "A campaign that has accumulated visitors and conversions.",
    "Integrations": "An admin user with credentials for the third-party service under test.",
    "Account Settings": "A logged-in user viewing their own account settings page.",
    "Team Permissions": "An account owner or admin managing workspace membership.",
    "Billing": "An account owner viewing the billing and subscription area.",
    "SmartCode": "Access to the target site's HTML/tag manager to install the snippet.",
    "Feature Rollout": "A logged-in developer with feature-flag management access.",
    "Personalization": "A logged-in user with the Personalization module enabled.",
    "API Webhooks": "A valid API token and a reachable webhook receiver endpoint.",
}

PRIORITY_WEIGHTS = [
    ("Critical", 0.18),
    ("High", 0.32),
    ("Medium", 0.38),
    ("Low", 0.12),
]

# Features whose keywords bump priority (security / money / data loss).
CRITICAL_HINTS = (
    "password", "credentials", "lockout", "oauth", "sso", "two-factor", "payment",
    "credit card", "billing", "cancel", "delete", "revoke", "kill switch", "rollback",
    "signature", "consent", "gdpr", "pii", "mask", "winner", "significance", "ownership",
)


def _weighted_priority(rng: random.Random, feature: str) -> str:
    low = feature.lower()
    if any(h in low for h in CRITICAL_HINTS):
        return rng.choice(["Critical", "Critical", "High"])
    r = rng.random()
    cum = 0.0
    for name, w in PRIORITY_WEIGHTS:
        cum += w
        if r <= cum:
            return name
    return "Medium"


def _tags(module: str, feature: str, priority: str) -> str:
    base = ["vwo", module.lower().replace(" ", "-")]
    low = feature.lower()
    if any(k in low for k in ("keyboard", "tab order", "focus", "accessible", "aria", "label")):
        base.append("accessibility")
    if any(k in low for k in ("mobile", "responsive", "device", "breakpoint")):
        base.append("responsive")
    if any(k in low for k in ("password", "oauth", "sso", "lockout", "consent", "gdpr", "pii", "mask", "signature", "two-factor")):
        base.append("security")
    if any(k in low for k in ("payment", "billing", "invoice", "coupon", "plan", "subscription", "tax")):
        base.append("billing")
    if any(k in low for k in ("api", "webhook", "endpoint", "sdk")):
        base.append("api")
    if any(k in low for k in ("report", "chart", "export", "significance", "conversion", "metric", "score")):
        base.append("analytics")
    if priority in ("Critical", "High"):
        base.append("regression")
    else:
        base.append("smoke")
    # de-dup, keep order
    seen: list[str] = []
    for t in base:
        if t not in seen:
            seen.append(t)
    return ";".join(seen)


STEP_TEMPLATES = [
    "Navigate to the VWO {module} area in the test environment",
    "Ensure the preconditions and required permissions for '{feature}' are in place",
    "Perform the action under test: {feature}",
    "Submit, save, apply, or continue where the flow requires it",
    "Observe UI feedback, data persistence, navigation, and any security/audit behaviour",
]

EXPECTED_TEMPLATES = [
    "The system handles '{feature}' exactly as the VWO specification requires: the outcome is "
    "correct, the UI gives clear feedback, data is persisted consistently, and no unauthorized "
    "state or data exposure occurs.",
    "'{feature}' behaves correctly end to end — valid input is accepted, invalid input is rejected "
    "with a helpful message, and the resulting state matches the {module} requirements.",
    "After '{feature}', VWO reflects the change accurately across the {module} views, remains "
    "responsive, and records the appropriate audit trail where applicable.",
]


def _steps(rng: random.Random, module: str, feature: str) -> str:
    steps = [t.format(module=module, feature=feature) for t in STEP_TEMPLATES]
    return " | ".join(f"{i + 1}. {s}" for i, s in enumerate(steps))


def _expected(rng: random.Random, module: str, feature: str) -> str:
    return rng.choice(EXPECTED_TEMPLATES).format(module=module, feature=feature)


def _module_code(module: str) -> str:
    letters = "".join(w[0] for w in module.split())[:4].upper()
    if len(letters) < 3:
        letters = module.replace(" ", "")[:4].upper()
    return letters


def generate(rows: int, out_path: Path, seed: int = 20260717) -> None:
    rng = random.Random(seed)

    # Build a flat, shuffled pool of (module, feature) so distribution is varied
    # but every feature appears; cycle with variants to reach the row target.
    pool: list[tuple[str, str]] = []
    for module, feats in MODULES.items():
        for f in feats:
            pool.append((module, f))

    rng.shuffle(pool)

    header = [
        "id", "jira_id", "module", "priority", "title",
        "preconditions", "steps", "expected", "tags",
    ]

    per_module_counter: dict[str, int] = {m: 0 for m in MODULES}
    variant_suffixes = [
        "", " (happy path)", " (negative case)", " (boundary values)",
        " (mobile viewport)", " (slow network)", " (concurrent users)",
        " (after page refresh)", " (with special characters)", " (RTL locale)",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(header)

        for i in range(rows):
            module, feature = pool[i % len(pool)]
            # Add a variant suffix on later cycles so titles stay unique.
            cycle = i // len(pool)
            suffix = variant_suffixes[cycle % len(variant_suffixes)] if cycle else ""
            feature_full = f"{feature}{suffix}"

            per_module_counter[module] += 1
            n = per_module_counter[module]

            tc_id = f"TC-{i + 1:04d}"
            jira_id = f"VWO-{1000 + i}"
            priority = _weighted_priority(rng, feature)
            code = _module_code(module)
            title = f"Verify {module} - {feature_full}"
            precondition = PRECONDITIONS[module]
            steps = _steps(rng, module, feature_full)
            expected = _expected(rng, module, feature_full)
            tags = _tags(module, feature, priority)
            # keep a stable per-module scenario id inside the title-less columns
            _ = f"{code}-{n:03d}"

            writer.writerow([
                tc_id, jira_id, module, priority, title,
                precondition, steps, expected, tags,
            ])

    print(f"Wrote {rows} test cases across {len(MODULES)} modules -> {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate VWO test cases CSV")
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).with_name("VWO_2000_Test_Cases.csv"),
    )
    ap.add_argument("--seed", type=int, default=20260717)
    args = ap.parse_args()
    generate(args.rows, args.out, args.seed)


if __name__ == "__main__":
    main()
