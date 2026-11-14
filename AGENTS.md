# Source result extraction

For requests containing fire-sport result URLs, use the source extraction pipeline
in `backend/app/extraction`, NOT the MongoDB seed/import command. The complete user
specification is in `docs/extraction-request.cs.md`; operating instructions and
supported formats are in `docs/extraction.cs.md`. These instructions apply to all
future imports and parser changes.

- Never invent missing data, estimate years of birth, derive districts from regions
  or teams, compute ranking, or calculate final time from attempts. Use null and
  actionable warnings for unavailable/ambiguous values. Regions are not districts,
  lanes/profile IDs are not start numbers or FSCodes.
- Inspect all pages/categories; retain exact source category names and combined
  categories. Ignore separately labelled final runs, not races called final rounds.
  One file per race; never merge independent races.
- The strict schema in `backend/app/extraction/results.schema.json` is the output
  contract. No additional properties. UTF-8, actual UTC generation time. Preserve
  official ranks (including gaps) and official final times. No minimum-of-tries.
- Keep tries 1 and 2 in order. Additional tries are noted and ignored. Blank/dash
  attempts are invalid; missing means absent/unpublished information. P is valid,
  N invalid; invalid sentinels are null. Preserve measured trailing-dash values only
  when unambiguous. Context-specific placeholders must never become real results.
- Assign numbered penalty reasons only to their explicit try; preserve source text.
  Unnumbered/third/fourth-try reasons and conflicts require warnings. A reason must
  not silently overwrite an official valid status. Audit source and output counts.
- FSCodes must be explicitly labelled, >=4 digits, integer/null; warn on leading
  zero loss. Profile enrichment retrieves only the required birth year. Ambiguous
  names remain null with original text in warnings. Do not guess from word count.
- Prefer HTML; detect source types from bytes, not suffixes. For PDFs inspect all
  pages, repeated headers, category transitions and wrapping. OCR must be visually
  verified; save page images/text as diagnostics until a verified adapter exists.
- Fail closed for incomplete/unsupported layouts, unavailable categories/pages,
  unresolved pagination or multiple ambiguous attachments. Save diagnostics outside
  result JSON and never replace a good existing result with a partial import.
- Store every new result ONLY in `data/{year}/{competition-folder}/`, NEVER in
  `data/results/`. The year comes from competition.date. Reuse an unambiguous
  existing race folder based on source URL or full event metadata, never place
  alone; preserve existing folder names. Use readable ASCII filenames
  `YYYY-MM-DD-{race-name}-{place}.json`, with no repeated place. On a collision,
  use the explicit stable race ID from the source URL, never a random hash/UUID.
- Reimports of the same source update the same file with atomic replacement,
  schema/content validation, and guards against loss of results or known identity
  fields. Unknown dates or destination conflicts retain pending JSON in ignored
  diagnostics outside final data. Do not guess a year or overwrite conflicting data.
- Migrate legacy hash files with the byte-preserving migration command and git mv
  for tracked files. Inspect existing same-race JSON first; preserve both versions
  and report conflicts. Remove data/results only when truly empty. Diagnostic
  directory IDs may remain hashed; final result filenames may not.
- Add offline regression fixtures and tests for every new supported source format.
  Run backend lint/tests and revalidate all newly generated JSON before committing.
- Preserve unrelated user work. Stage only task files. Use a working branch and PR;
  do not claim commit, push, or PR success unless confirmed. Never commit cookies,
  tokens, raw operational profile snapshots or other unnecessary personal data.
