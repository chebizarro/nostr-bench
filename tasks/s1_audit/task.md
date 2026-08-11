# S1 — Security audit of an Express service

<!-- KIND: audit -->
<!-- TARGET: findings.json -->

<!-- T1 -->
Audit the TypeScript Express service in `src/` for security vulnerabilities.
Return your findings as a JSON array; each item: `{ "title", "file", "severity",
"description" }`. Report only real, exploitable issues.
<!-- /T1 -->

<!-- T2 -->
Perform a security review of the Express (TypeScript) service in `src/`. Identify
concrete, exploitable vulnerabilities — injection, broken auth/authorization,
SSRF, unsafe deserialization/merging, weak crypto, path handling, and unsafe
comparisons are all in scope.

For each real vulnerability output one object with:
`{ "title": short name, "file": path, "severity": "low|medium|high|critical",
"description": what an attacker does and how to fix }`.

Return **only** a JSON array of findings and nothing else. Precision counts: do
not pad the list with defense-in-depth nitpicks or dead code — false alarms are
penalized as heavily as misses.
<!-- /T2 -->
