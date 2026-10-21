---
title: "Einheitliche Dateinamen: eine einfache Konvention entwickeln"
card_title: "Einheitliche Dateinamen: eine einfache Konvention entwickeln"
slug: "design-consistent-file-naming-system"
category: "productivity"
language: "de"
description: "Entwickeln Sie eine verständliche Dateinamen-Konvention mit stabilen Kennungen, eindeutigen Datumsangaben, Nummernfolgen und klar bezeichneten Revisionen."
status: "published"
topic_id: "TOPIC-0083"
search_intent: "workflow"
primary_keyword: "einheitliche Dateinamen"
secondary_keywords: "Dateinamen-Konvention | Dateien organisieren | Datumsformat für Dateinamen | Revisionen kennzeichnen"
tags: "einheitliche Dateinamen"
short_answer: "Legen Sie wenige Felder mit einer festen Reihenfolge und eindeutiger Bedeutung fest. Verwenden Sie eine stabile Kennung, ein unmissverständliches Datum und bei Bedarf Nummern mit führenden Nullen. Trennen Sie Revisionen von Freigaben, dokumentieren Sie ein Beispiel und prüfen Sie die Regel an typischen Dateien."
related_apps: "Aligna"
canonical_url: "https://onnellab.com/blog/de/design-consistent-file-naming-system/"
published_at: "2026-10-21T09:00:00+09:00"
updated_at: "2026-10-21T09:00:00+09:00"
related_articles: "Wiederkehrende Texte in wiederverwendbare Textbausteine umwandeln => https://onnellab.com/blog/de/turn-repeated-text-into-reusable-snippets/|Konvertierte Mediendateien prüfen, bevor Sie das Original ersetzen => https://onnellab.com/blog/de/test-converted-media-before-replacing-original/|Musikdateien auf Android für die Offline-Wiedergabe ordnen => https://onnellab.com/blog/de/organize-local-music-library-offline-android/|Inhaltsverzeichnis und Kapitelreihenfolge einer EPUB prüfen => https://onnellab.com/blog/de/check-epub-table-of-contents-and-reading-order/"
---

# Einheitliche Dateinamen: eine einfache Konvention entwickeln

## Frage

Wie entwickelt man ein System für Dateinamen, das im Alltag verständlich bleibt?

## Kurzantwort

Legen Sie wenige Felder mit einer festen Reihenfolge und eindeutiger Bedeutung fest. Verwenden Sie eine stabile Kennung, ein unmissverständliches Datum und bei Bedarf Nummern mit führenden Nullen. Trennen Sie Revisionen von Freigaben, dokumentieren Sie ein Beispiel und prüfen Sie die Regel an typischen Dateien.

## Eine kleine Konvention festlegen

Eine Dateinamen-Konvention beschreibt, wie Dateien benannt werden. Ein Feld ist dabei ein einzelner Bestandteil mit einer vereinbarten Aufgabe, etwa Projektkennung, Datum oder Revision. Die Regel sollte auch dann verständlich sein, wenn eine andere Person die Datei übernimmt oder Sie sie Monate später wiederfinden.

Das manuell erstellte Beispiel `atlas_2026-10-05_notes_003_v02.txt` dient der Erklärung. Es zeigt keine zugesicherte App-Funktion. Atlas ist ein fiktives Projekt; die einzelnen Bestandteile haben hier folgende Bedeutung:

| Feld | Bedeutung im Beispiel |
| --- | --- |
| `atlas` | Stabile Kennung des Projekts Atlas |
| `2026-10-05` | Besprechungsdatum: 5. Oktober 2026 |
| `notes` | Dokumentart: Notizen |
| `003` | Eintrag 003 innerhalb der Notizen dieser Besprechung |
| `v02` | Gespeicherte Revision 02 |
| `.txt` | Dateiendung der Textdatei |

Die englische Bezeichnung `notes` gehört nur zu diesem Beispiel. Ein Team kann deutsche Begriffe wählen, sofern es deren Bedeutung festhält und sie einheitlich verwendet.

## Empfohlener Ablauf

1. **Den wichtigsten Suchschlüssel wählen.** Überlegen Sie, wie Sie Dateien tatsächlich wiederfinden. Beginnen Sie mit dem Datum, wenn Sie überwiegend chronologisch suchen, oder mit der Projektkennung, wenn das Projekt der Ausgangspunkt ist. Bei lexikografischer Sortierung ordnet eine vorangestellte Projektkennung die Datumsangaben innerhalb der Projekte. Sie erzeugt keine projektübergreifende chronologische Reihenfolge.

2. **Die Bedeutung des Datums bestimmen.** Nutzen Sie `YYYY-MM-DD` (Jahr-Monat-Tag) mit zweistelligem Monat und Tag. Halten Sie fest, ob damit das Ereignis-, Aufnahme- oder Ausstellungsdatum gemeint ist. Fehlt die Information, lassen Sie das Feld weg oder verwenden Sie eine dokumentierte Kennzeichnung für ein unbekanntes Datum. Das heutige Datum einzusetzen, nur um das Feld zu füllen, würde eine falsche Bedeutung vermitteln.

3. **Eine stabile Identität verwenden.** Wählen Sie eine kurze Projekt- oder Vorgangskennung. Namen vorübergehend zuständiger Personen und Wörter wie „dringend“ verändern ihre Bedeutung im Laufe der Zeit. Vermeiden Sie unnötige personenbezogene oder vertrauliche Angaben. Dateinamen können in Anhängen, Links und Benachrichtigungen sichtbar werden, auch wenn der ursprüngliche Ordner geschützt ist.

4. **Den Nummernkreis festlegen.** Gilt die Folge für ein Projekt, eine Besprechung oder einen Stapel? Wählen Sie passend zur erwarteten Menge eine Stellenzahl. `001`, `002` und `010` bleiben bei einfacher Textsortierung in numerischer Reihenfolge. Manche Programme nutzen bereits eine natürliche Sortierung. Wird die Stellenzahl überschritten, passen Sie die betroffene Nummernfolge geplant und einheitlich an.

5. **Revision und Freigabe trennen.** Definieren Sie, wann aus `v01` eine `v02` wird, beispielsweise bei jeder neu gespeicherten Revision, die unterscheidbar bleiben soll. Eine höhere Nummer belegt keine Freigabe. Dokumentieren Sie diese im vorgesehenen Verfahren. Auch „final-final“ sagt nicht zuverlässig aus, ob jemand den Inhalt geprüft oder genehmigt hat.

6. **Die Regel aufschreiben und fünf Dateien testen.** Notieren Sie Feldreihenfolge, optionale Bestandteile, Trennzeichen und Ausnahmen. Wählen Sie fünf repräsentative Dateien, darunter einen Fall mit unbekanntem Datum und einen mit neuer Revision. Prüfen Sie Benennung, Suche, Darstellung und Sortierung in den tatsächlich verwendeten Anwendungen und beim empfangenden System.

## Die vier Bausteine im Überblick

![Vier Bausteine eines Dateinamens: stabile Identität, Datum mit definierter Bedeutung, Nummernfolge mit führenden Nullen und gekennzeichnete Revision.](/blog-assets/de/design-consistent-file-naming-system/workflow-diagram.svg)

## Die Regel leicht anwendbar halten

Verwenden Sie Trennzeichen einheitlich. Kleinschreibung ist eine redaktionelle Entscheidung, keine allgemeine technische Pflicht. Prüfen Sie erlaubte Zeichen und Längenbegrenzungen der empfangenden Systeme. Behalten Sie die Dateiendung bei: Eine andere Endung wandelt den Dateiinhalt nicht in ein anderes Format um.

Eine Benennungsregel ersetzt weder Versionshistorie noch Zugriffsrechte oder eine sinnvolle Ordnerstruktur. Ändert sich die Regel, benennen Sie nicht automatisch das gesamte Archiv um. Klären Sie zuerst, welche Links, Verweise und Abläufe von vorhandenen Namen abhängen.

## ONNELLAB im Einsatz

Für mehrere Dateien kommt [Aligna](/apps/aligna/) als Stapelumbenenner für iOS und Android infrage. Die Store-Beschreibungen nennen acht feste Vorlagen, eine Vorschau und Konfliktbehandlung. Wählen Sie nur eine Vorlage, die zum benötigten Ergebnis passt. Prüfen Sie die ausgewählte Vorlage und die Vorschau, bevor Sie die Änderung anwenden. Daraus lässt sich weder ein frei konfigurierbarer Regelbaukasten noch die Unterstützung der Feldkombination aus diesem Artikel ableiten.

## Weiterführende Anleitungen

- [Dateien mit Vorschau sicher umbenennen](https://onnellab.com/blog/de/rename-files-safely-preview-workflow/)
- [Downloads mit wenigen Ordnern organisieren](https://onnellab.com/blog/de/organize-downloads-small-folder-system/)

## Quellen

Die Produktangaben stammen aus den Aligna-Beschreibungen im [App Store](https://apps.apple.com/us/app/aligna-file-renamer/id6783642658) und bei [Google Play](https://play.google.com/store/apps/details?id=com.onnellab.aligna). Die Benennungsempfehlungen sind redaktionelle Orientierung, keine gemessenen Leistungs- oder Zeitersparnisversprechen.

## Fazit

Ein brauchbares System besteht aus wenigen Feldern mit klarer Bedeutung. Dokumentieren Sie die Regel und prüfen Sie typische Ausnahmen, bevor Sie viele Dateien damit benennen.

## Häufige Fragen

### Braucht jeder Dateiname ein Datum?

Nein. Ein Datum ist sinnvoll, wenn es beim Suchen oder Einordnen hilft. Legen Sie dann ausdrücklich fest, welche Art von Datum es bezeichnet.

### Sollte das Datum oder das Projekt zuerst stehen?

Entscheidend ist Ihr wichtigster Suchschlüssel. Das Datum unterstützt die chronologische Suche; die Projektkennung hält Dateien zunächst nach Projekten zusammen.

### Bedeutet `v03`, dass eine Datei freigegeben ist?

Nein. Die Kennzeichnung beschreibt eine Revision nach Ihrer Regel. Eine Freigabe braucht einen eigenen nachvollziehbaren Nachweis.

### Kann Aligna genau dieses Namensmuster erzeugen?

Das ist durch die genannten Produktinformationen nicht belegt. Aligna bietet feste Vorlagen. Prüfen Sie, ob eine davon Ihren konkreten Bedarf abdeckt.
