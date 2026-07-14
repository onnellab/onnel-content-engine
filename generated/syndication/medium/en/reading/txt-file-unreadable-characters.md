> ONNELLAB note: This edit focuses on the practical encoding checks before recommending tools.

The first useful move is not to convert the file. It is to check whether the app is interpreting the same bytes with the right encoding.

# Why TXT Files Show Unreadable Characters

## Question

Why do TXT files show unreadable characters?

## Short Answer

TXT files show unreadable characters when an app interprets the file with the wrong text encoding. A TXT file stores bytes, not a guaranteed visual format. If the bytes were saved as UTF-8, Shift JIS, EUC-KR, Windows-1252, or another encoding, the reader must decode them with the matching rule. Before assuming the file is damaged, check the encoding, confirm that the file is plain text, and avoid resaving the only original copy.

## Why This Problem Happens

TXT unreadable characters usually appear because the file and the app disagree about encoding. Encoding is the rule an app uses to turn bytes into readable characters. UTF-8 is common today, but older files, regional exports, logs, subtitles, and backup files may use another encoding.

A TXT file does not include the same layout and font information as a PDF or word processor document. It is intentionally simple. That simplicity is useful, but it also means the app has to decide how to decode the bytes. If the app guesses wrong, normal text can appear as boxes, question marks, random symbols, or broken mixed characters.

The file may still be valid. The visible problem is often a decoding mismatch rather than permanent data loss.

## What Makes This Problem Feel Worse

The problem feels worse when the file comes from an older system, a different language environment, or an export tool that does not clearly label encoding. It can also appear when a file was copied between devices, downloaded from a browser, or opened by a general note app that assumes one default encoding.

Large TXT files add another layer of difficulty. If a large file opens slowly and also shows broken characters, it is easy to blame file size. In practice, file size and encoding are separate issues. A large file may need efficient reading, while unreadable characters need correct decoding.

## What To Check First

- Confirm that the file is actually plain text, not a renamed document, archive, or binary file.
- Open a copy of the file before changing encoding or resaving anything.
- Try UTF-8 first, then consider the encoding used by the source system or language.
- If only some characters are broken, check whether the file combines content from multiple sources.
- Avoid converting the file to PDF or EPUB until the text displays correctly.

## Recommended Workflow

1. Keep the original TXT file unchanged.
2. Open a copy in a reader or editor that lets you choose encoding.
3. Start with UTF-8 and check whether the text becomes readable.
4. If UTF-8 fails, try encodings that match the file source, such as EUC-KR, Shift JIS, or Windows-1252.
5. Once the text is readable, save a new copy only if you understand which encoding will be used.
6. Use search and bookmarks after the text is readable, not before.

> The safest workflow is to solve the encoding problem before making format changes.

![Workflow diagram](https://onnellab.github.io/blog-assets/en/txt-file-unreadable-characters/workflow-diagram.svg "Workflow diagram: copy file, check encoding, preview text, save only after verification")

## UTF-8 vs Wrong Encoding Symptoms

| Situation | What it means | Best first action |
| --- | --- | --- |
| Text opens normally in UTF-8 | The app and file encoding match. | Keep the workflow unchanged. |
| Text shows boxes or question marks | The app may be using the wrong decoding rule. | Reopen a copy with another encoding. |
| Only part of the file is broken | The file may combine text from multiple sources. | Identify where the broken section begins. |
| The file opens slowly and looks broken | Performance and encoding may both be involved. | Check encoding first, then optimize reading. |

Virtual rendering is a technique where an app renders only the visible portion of a large document. It can help with performance, but it does not fix unreadable characters by itself. Encoding must still be interpreted correctly.

## ONNELLAB Application

If you often inspect large plain-text files, [VaultXT](https://onnellab.github.io/apps/vaultxt/) may be relevant after the encoding issue is understood. VaultXT is designed for reading and lightly editing large plain-text files, so it fits workflows where the same files must be opened, searched, and reviewed repeatedly.

VaultXT should not be treated as a magic repair tool for damaged files. It is most useful when the file is plain text and the reader needs a calmer way to open, inspect, search, and navigate it.

## Related Topics

- Text encoding basics
- UTF-8 and plain text files
- Large TXT file reading performance
- Search and bookmarks in long documents

## References

- [The Unicode Standard](https://www.unicode.org/versions/latest/) for official Unicode and character encoding references.

## Conclusion

When a TXT file shows unreadable characters, start with encoding. Keep the original file safe, open a copy, try the most likely encoding, and only save a converted copy after the text is readable. After that, choose a reader or editor based on the actual task: reading, searching, bookmarking, or editing.

## FAQ

### Is a TXT file with broken characters always damaged?

No. The file may be intact. The app may simply be using the wrong encoding to read it.

### Should I convert the file immediately?

No. Conversion can preserve the wrong characters if the text is decoded incorrectly first. Fix the display problem before converting.

### Is UTF-8 always the correct encoding?

No. UTF-8 is common, but older files and regional exports may use another encoding.

### When should I use VaultXT?

Use VaultXT when the file is plain text and your recurring task is opening, reading, searching, or lightly editing large TXT files.

---

Originally published at https://onnellab.github.io/blog/en/txt-file-unreadable-characters/
