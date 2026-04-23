---
name: report-writing
description: Only if the user specifies to use this, this is a skill specific to writing reports for coding assignments in school, and nothing else. Write clear, readable technical reports for academic assignments. Produces prose that reads naturally, avoids jargon-heavy shorthand, and presents evidence-based reasoning in plain English.
---

# Report Writing

## Before you start

1. **Ask the user about pronoun preference.** Ask whether they want to use "I" (first-person singular) or "We" (first-person plural, common in academic writing even for solo authors). Use their choice consistently throughout the entire report. Do not mix pronouns.

2. **Ask about page or word limits.** If the user hasn't mentioned constraints, ask. Academic reports almost always have a page limit. Knowing the limit upfront prevents having to cut content later.

3. **Read the assignment instructions.** If an assignment brief or rubric is available in the workspace, read it before writing. Identify what sections are required, what the grading weights are, and what the instructor explicitly asks for (e.g. "explain why, not just what").

## Language and readability

4. **Never abbreviate domain terms in prose.** Write "preprocessing" not "PP", "feature engineering" not "FE", "Logistic Regression" not "LR" in running text. Abbreviations are acceptable inside tables, figure labels, and code references where space is tight, but the first mention in a table should still use the full name.

5. **Do not use internal experiment indices to refer to concepts.** Never write "as shown in PP-01" or "FE-03 improved F1". Instead, refer to the actual thing: "adding contraction expansion improved F1" or "character n-grams contributed +0.026". Index codes belong in table rows for reference, not in explanatory prose.

6. **Write in complete, natural sentences.** Avoid telegraphic note-style prose like "Aids negation detection. Marginal on formal reviews." Instead write: "Expanding contractions aids negation detection. Repeat normalisation has a marginal effect on formal reviews."

7. **Separate hyperparameters from explanations.** When describing a method, first explain what it does and why it works in plain language. Then, if specific hyperparameters matter, state them in a separate sentence. Bad: "Word (1,3)-grams (200K, min_df=5, sublinear_tf) + character (2,6)-grams (150K, min_df=5)." Good: "We extract word-level unigrams, bigrams, and trigrams using TF-IDF. We set the maximum vocabulary to 200,000 features, require each term to appear in at least 5 documents, and use sublinear term frequency scaling."

8. **Prefer words over symbols in prose.** Write "improved by 0.03" not "+0.03", "approximately" not "~", "change" or "difference" not "Δ". Symbols are fine inside tables.

9. **Avoid stacking parenthetical qualifiers.** Bad: "LR (C=10.0, L2, liblinear, balanced)". Good: "Logistic Regression with L2 regularisation, C=10.0, and balanced class weights."

## Structure and content

10. **Lead with the "why", not just the "what".** For each design choice, explain the reasoning before or alongside the result. Don't just list things you tried — explain why you expected them to work and why they did or didn't.

11. **Keep tables focused.** Each table should answer one clear question. If a table has more than 7-8 rows, consider whether all rows are necessary or whether some can be summarised in prose. Use tables for numerical comparisons; use prose for explanations.

12. **Don't over-detail things that didn't work.** Mention failed approaches briefly (one sentence each) to show you explored alternatives. Spend the word budget on what actually made it into the final system and why.

13. **Consolidate related ablation results.** If you have four separate ablation tables, consider whether two would suffice — one incremental, one leave-one-out. Discuss the most important findings rather than mechanically narrating every row.

14. **End analysis sections with insights, not just numbers.** After presenting ablation results, state the takeaway in plain language: "This tells us that feature selection is more important than any individual preprocessing step."

## Formatting

15. **Bold key results and decisions.** Use bold sparingly for the most important numbers (e.g. final F1 score) and critical design choices. Don't bold everything.

16. **Use consistent heading levels.** Don't skip levels (e.g. jumping from ## to ####). Match heading structure to the assignment rubric sections when possible.

17. **Keep the declaration and references minimal.** These are required sections but don't need elaboration. State facts plainly.

## Common mistakes to avoid

- Writing a report that reads like a lab notebook (listing every experiment chronologically) instead of a coherent narrative about design decisions.
- Using so many abbreviations that the report requires a glossary to read.
- Presenting numbers without interpreting them. Every table should be followed by a sentence explaining what the numbers mean.
- Making the report longer than allowed and then having to aggressively cut it. Plan for the page limit from the start.
- Copy-pasting raw console output or code into the report. Summarise results in clean tables instead.
