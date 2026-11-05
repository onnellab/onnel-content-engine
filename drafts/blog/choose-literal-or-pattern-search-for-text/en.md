---
title: "Choose Literal or Pattern Search for Text"
description: "Choose a search mode, test punctuation on invented text, and check the scope before trusting matches in a document."
language: "en"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
short_answer: "Use literal search for a known sequence of characters. Use pattern search only when you need a rule for several variants and have checked the application's syntax. Test matches and non-matches on invented text, then inspect the intended document without replacing anything."
primary_keyword: "literal or pattern search"
secondary_keywords: "literal text search|regular expression search|search punctuation"
card_title: "Choose Literal or Pattern Search for Text"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "literal or pattern search"
canonical_url: "https://onnellab.com/blog/en/choose-literal-or-pattern-search-for-text/"
---

# Choose Literal or Pattern Search for Text

A search for a label containing a dot can return an unexpected passage. The characters you typed may be treated as text, or interpreted as instructions. Before making the query more elaborate, check which kind of search you are using.

## Question

When should I search for literal text, and when should I use a pattern?

## Short Answer

Use literal search for a known sequence of characters. Use pattern search only when you need a rule for several variants and have checked the application's syntax. Test matches and non-matches on invented text, then inspect the intended document without replacing anything.

## Two Meanings of a Search Query

Literal search looks for the characters you enter rather than treating them as pattern operators. Pattern search interprets some characters as rules. A regular expression is one kind of pattern; a filename wildcard is not automatically the same language.

Literal does not necessarily mean a whole line, a whole word, case-sensitive text or identical file bytes. Those are separate questions. A match inside a longer sentence can still be a literal match.

| Your task | Starting choice | Check before trusting results |
| --- | --- | --- |
| Find the written label `A.7` | Literal search | Punctuation and case settings |
| Find several deliberately defined variants | Supported pattern mode | Syntax and unwanted matches |
| Limit which files are searched | File-scope controls | Do not confuse path filters with content queries |

## A Small Invented Test

Create a disposable local note containing these three lines, with no private or real document text:

```text
A.7
Ax7
A-7
```

For the task “find the written label `A.7`,” only the first line is wanted. Begin in literal mode and inspect the highlighted characters, not just the result count.

In [RE2 syntax](https://github.com/google/re2/wiki/Syntax), a dot is a wildcard; an escaped dot represents the dot itself. Thus, for this invented test, the patterns `A.7` and `A\.7` express different intentions. These are explanatory examples, not a promise that your reader accepts either expression. Do not add the backslash to a literal query unless you actually want to search for that character.

A pattern that passes this tiny test is not yet a complete rule for your document. For example, decide separately whether a label embedded in `ZA.70` should count. Add that case to your test if it matters.

## Recommended Workflow

1. **Write the goal in plain language.** Decide whether you need one known phrase or a family of variants. List one wanted result and one plausible result you do not want.
2. **Preserve the source.** Leave the original untouched. Use a read-only view or a separate working copy. Keep test text and observations in separate notes; do not upload private material to an online pattern tester.
3. **Check the actual search field.** Read the application's help for the selected mode, escaping and supported syntax. [Google's help](https://support.google.com/docs/answer/62754?hl=en) documents its regex option and backslash escaping. Those instructions are specific to that product.
4. **Test without replacing.** Use the invented sample. Check every expected match and rejection, changing one option at a time. If the behavior is unclear, return to literal search with a shorter distinctive phrase.
5. **Search the intended scope and record it.** Confirm the file, version, selection and filters. Inspect surrounding text and record the query, mode and relevant options outside the source.

## Scope Can Change the Answer

[VS Code's documentation](https://code.visualstudio.com/docs/editing/codebasics) distinguishes content-search options from file include/exclude glob patterns. Keep those fields separate.

Zero matches can mean that the text is absent, but it can also mean the wrong selection, filter or query was used. Check a passage you already know is present. If even that fails, resolve the scope or text mismatch before widening the pattern. Similar-looking punctuation and unexpected spaces deserve inspection; do not normalize the original just to make a search work.

## Conclusion

Choose the simplest mode that describes the task. A successful search locates relevant text with understood limits; it does not prove that every relevant passage was found, nor authorize a replacement.

## FAQ

### Should I put quotation marks around literal text?

Only if the application's search help calls for them. Otherwise they may become part of the text being sought.

### Does an advanced search button guarantee regular expressions?

No. Check the selected field's documentation. A pattern copied from another tool may be unsupported or mean something different.

### Can I replace all matches after a successful test?

Not on that basis alone. Replacement is a separate editing task requiring a usable backup, a review of actual matches and a plan to verify changes. This workflow ends with finding and recording text.

## Related Guides

- [Navigate a long plain-text document](https://onnellab.com/blog/en/make-long-plain-text-easier-to-navigate/)

## References

- [RE2 syntax](https://github.com/google/re2/wiki/Syntax)
- [Google Docs Editors: search](https://support.google.com/docs/answer/62754?hl=en)
- [VS Code: basic editing](https://code.visualstudio.com/docs/editing/codebasics)
