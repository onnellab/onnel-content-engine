---
title: "Literal text search or pattern search: which should you use?"
card_title: "Literal text search or pattern search: which should you use?"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
language: "en"
description: "Literal text search looks for the characters you entered. Choose it when you know the exact spelling or punctuation. Switch to a pattern only if you need several variants and your reader explicitly supports regular expressions."
status: "review"
topic_id: "TOPIC-0114"
search_intent: "workflow"
primary_keyword: "literal text search"
secondary_keywords: "pattern search|regular expressions|search variants"
related_apps: ""
canonical_url: ""
published_at: ""
updated_at: ""
tags: "literal text search|pattern search|regular expressions|search variants"
short_answer: "Literal text search looks for the characters you entered. Choose it when you know the exact spelling or punctuation. Switch to a pattern only if you need several variants and your reader explicitly supports regular expressions."
---

# Literal text search or pattern search: which should you use?

## Question

How can I choose between literal text search and pattern matching before searching a document?

## Short Answer

Literal text search looks for the characters you entered. Choose it when you know the exact spelling or punctuation. Switch to a pattern only if you need several variants and your reader explicitly supports regular expressions.

A regular expression is a rule that describes a set of matching strings. For example, the brackets in a character class describe alternatives for one character; they do not require literal brackets in the result. A normal search for `[draft]` is a better starting point when the brackets themselves matter.

## Recommended Workflow

1. Start in a small temporary document. Put `[draft]`, `draft`, `Ref-03`, `Ref-42`, and `Ref-AA` on separate lines. Include `Ref-031` on a sixth line so you can spot a partial match.
2. Search for `[draft]` in literal mode. The bare word should not match that query. If you do not see the expected highlight, check whether a pattern option is still active or whether your reader is searching a different file or selection.
3. Enable the regular-expression option if available. Try `Ref-[0-9][0-9]`. It matches both `Ref-03` and `Ref-42`, but not `Ref-AA`. Inspect where the highlight stops in `Ref-031`: finding the prefix is not proof that the whole reference has only two digits.
4. Review which matches you want before moving to the original document. Keep the search read-only; there is no need to use Replace, and the same examples can be tested without pasting private text into a website.

![Known text: Use literal search; Shared form: If supported, use a pattern; Test the query: Include a miss; Check the highlight: Confirm the full result.](/blog-assets/en/choose-literal-or-pattern-search-for-text/workflow-diagram.svg)

| Goal|Use |
| --- | --- |
| Find one known spelling, including its punctuation|Literal mode |
| Find references with a shared form|Pattern mode, if supported |
| Spot unexpected extra matches|Inspect the full highlighted range and surrounding text |

## FAQ

### Can I do this without a regular-expression option?

Yes. Search for known variants separately. If results are too broad, use the case or whole-word setting if available, then check the surrounding text. Neither setting turns a literal search into a pattern search.

### What if my reader returns nothing?

Start with one known result or try a shorter literal string. Check the search scope and case setting before treating an empty result as evidence that the text is absent.

## References

- [MDN: Character classes in regular expressions](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Character_class)

## Conclusion

Start with literal search. Change modes only when the task calls for it, and make sure your test contains both an expected match and an expected miss.
