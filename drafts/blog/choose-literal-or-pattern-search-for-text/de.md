---
title: "Wörtliche Suche oder Mustersuche für Text wählen"
description: "Wählen Sie den Suchmodus, prüfen Sie Satzzeichen an einem erfundenen Beispiel und kontrollieren Sie den Suchbereich, bevor Sie Treffer bewerten."
language: "de"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
short_answer: "Suchen Sie eine bekannte Zeichenfolge zunächst wörtlich. Verwenden Sie ein Muster nur, wenn Sie mehrere Varianten nach einer Regel finden müssen und die Syntax der Anwendung geprüft haben. Testen Sie gewünschte und unerwünschte Treffer an erfundenem Text. Prüfen Sie danach das Dokument, ohne etwas zu ersetzen."
primary_keyword: "wörtliche Suche oder Mustersuche"
secondary_keywords: "Text wörtlich suchen|Suche mit regulären Ausdrücken|Satzzeichen suchen"
card_title: "Wörtliche Suche oder Mustersuche für Text wählen"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "wörtliche Suche oder Mustersuche"
canonical_url: "https://onnellab.com/blog/de/choose-literal-or-pattern-search-for-text/"
---

# Wörtliche Suche oder Mustersuche für Text wählen

Eine Suche nach einer Kennzeichnung mit Punkt kann eine unerwartete Stelle finden. Vielleicht werden die eingegebenen Zeichen als Anweisungen statt als Text interpretiert. Prüfen Sie den Suchmodus, bevor Sie den Ausdruck komplizierter machen.

## Frage

Wann sollte ich Text wörtlich suchen, und wann eignet sich ein Suchmuster?

## Kurzantwort

Suchen Sie eine bekannte Zeichenfolge zunächst wörtlich. Verwenden Sie ein Muster nur, wenn Sie mehrere Varianten nach einer Regel finden müssen und die Syntax der Anwendung geprüft haben. Testen Sie gewünschte und unerwünschte Treffer an erfundenem Text. Prüfen Sie danach das Dokument, ohne etwas zu ersetzen.

## Zwei Bedeutungen einer Suchanfrage

Die wörtliche Suche sucht die eingegebenen Zeichen, ohne sie als Musteroperatoren auszulegen. Die Mustersuche interpretiert bestimmte Zeichen als Regeln. Ein regulärer Ausdruck ist eine Art von Muster. Platzhalter für Dateinamen verwenden nicht automatisch dieselbe Sprache.

Wörtlich bedeutet nicht zwingend ganze Zeile, ganzes Wort, Unterscheidung von Groß- und Kleinschreibung oder identische Dateibytes. Das sind getrennte Fragen. Auch ein Teil einer längeren Aussage kann ein wörtlicher Treffer sein.

| Aufgabe | Ausgangspunkt | Vor der Bewertung prüfen |
| --- | --- | --- |
| Die Kennzeichnung `A.7` finden | Wörtliche Suche | Satzzeichen und Groß-/Kleinschreibung |
| Mehrere definierte Varianten finden | Unterstützter Mustermodus | Syntax und unerwünschte Treffer |
| Durchsuchte Dateien eingrenzen | Dateibereich festlegen | Pfadfilter von Inhaltssuche trennen |

## Eine kleine erfundene Probe

Legen Sie eine temporäre lokale Notiz mit diesen drei Zeilen an. Verwenden Sie keine privaten Daten oder echten Dokumentauszüge.

```text
A.7
Ax7
A-7
```

Für die Aufgabe „die Kennzeichnung `A.7` finden“ ist nur die erste Zeile erwünscht. Beginnen Sie wörtlich und prüfen Sie die hervorgehobenen Zeichen, nicht nur die Trefferzahl.

In der [RE2-Syntax](https://github.com/google/re2/wiki/Syntax) ist der Punkt ein Platzhalter; maskiert steht er für den Punkt selbst. Die Muster `A.7` und `A\.7` drücken hier daher verschiedene Absichten aus. Daraus folgt keine Zusage, dass Ihr Leseprogramm beide versteht. Fügen Sie einer wörtlichen Anfrage keinen Rückstrich hinzu, wenn Sie ihn nicht selbst suchen möchten.

Eine bestandene Probe macht das Muster noch nicht zur vollständigen Regel für Ihr Dokument. Entscheiden Sie etwa gesondert, ob die Zeichenfolge innerhalb von `ZA.70` zählen soll. Nehmen Sie diesen Fall bei Bedarf in die Probe auf.

## Empfohlenes Vorgehen

1. **Beschreiben Sie das Ziel in Worten.** Geht es um eine bekannte Formulierung oder mehrere Varianten? Notieren Sie einen gewünschten und einen ähnlichen, aber unerwünschten Treffer.
2. **Bewahren Sie die Quelle unverändert auf.** Nutzen Sie eine schreibgeschützte Ansicht oder Arbeitskopie. Halten Sie Testtext und Beobachtungen separat. Laden Sie keine vertraulichen Inhalte in einen Online-Mustertester.
3. **Prüfen Sie das tatsächliche Suchfeld.** Lesen Sie die Hilfe zu Modus, Maskierung und unterstützter Syntax. Die [Google-Hilfe](https://support.google.com/docs/answer/62754?hl=en) beschreibt die eigene Regex-Option und Rückstrich-Maskierung. Das sind produktspezifische Hinweise.
4. **Testen Sie ohne Ersetzen.** Prüfen Sie alle erwarteten Treffer und Ausschlüsse an der erfundenen Probe. Ändern Sie jeweils nur eine Option. Bei unklarem Verhalten hilft zunächst die wörtliche Suche nach einer kurzen, markanten Formulierung.
5. **Prüfen und notieren Sie den Bereich.** Bestätigen Sie Datei, Version, Auswahl und Filter. Lesen Sie den Kontext und notieren Sie Anfrage, Modus und wichtige Optionen außerhalb des Originals.

## Der Suchbereich verändert das Ergebnis

Die [VS-Code-Dokumentation](https://code.visualstudio.com/docs/editing/codebasics) trennt Inhaltssuchoptionen von Glob-Mustern zum Ein- und Ausschließen von Dateien. Verwechseln Sie diese Felder nicht.

Null Treffer können fehlenden Text bedeuten, aber auch eine falsche Auswahl, einen Filter oder eine unpassende Anfrage. Suchen Sie eine sicher vorhandene Stelle. Fehlt auch sie, klären Sie zunächst Bereich und Zeichenunterschiede, bevor Sie das Muster erweitern. Prüfen Sie ähnlich aussehende Satzzeichen und unerwartete Leerzeichen. Vereinheitlichen Sie nicht das Original, nur damit die Suche gelingt.

## Fazit

Wählen Sie den einfachsten Modus, der zur Aufgabe passt. Bei einer erfolgreichen Suche finden Sie relevante Textstellen und kennen die Grenzen der Suche. Das Ergebnis belegt weder die Vollständigkeit der Suche noch rechtfertigt es das Ersetzen.

## Häufige Fragen

### Muss ich wörtlichen Text in Anführungszeichen setzen?

Nur wenn die Anwendungshilfe das verlangt. Sonst können die Anführungszeichen selbst Teil des gesuchten Textes werden.

### Garantiert eine erweiterte Suche reguläre Ausdrücke?

Nein. Lesen Sie die Beschreibung des konkreten Feldes. Muster aus anderen Werkzeugen können nicht unterstützt werden oder etwas anderes bedeuten.

### Darf ich nach einem erfolgreichen Test alles ersetzen?

Der Test allein reicht nicht aus. Ersetzen ist eine eigene Bearbeitungsaufgabe mit nutzbarer Sicherung, Prüfung der tatsächlichen Treffer und anschließender Kontrolle. Dieser Ablauf endet beim Suchen und Dokumentieren.

## Weiterführende Artikel

- [Lange Textdokumente leichter navigieren](https://onnellab.com/blog/de/make-long-plain-text-easier-to-navigate/)

## Quellen

- [RE2-Syntax](https://github.com/google/re2/wiki/Syntax)
- [Google-Editoren: Suche](https://support.google.com/docs/answer/62754?hl=en)
- [VS Code: grundlegende Bearbeitung](https://code.visualstudio.com/docs/editing/codebasics)
