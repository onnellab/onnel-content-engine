---
title: "Aufnahmedatum und Veröffentlichungsdatum in Musik-Metadaten unterscheiden"
description: "Trennen Sie Aufnahme, Erstveröffentlichung und Ausgabe, notieren Sie die Quellen und lassen Sie unbekannte Musikdaten offen."
language: "de"
slug: "distinguish-recording-date-from-release-date"
category: "music"
short_answer: "Das Aufnahmedatum bezeichnet den Zeitpunkt der Aufnahme, das Veröffentlichungsdatum den Zeitpunkt der Veröffentlichung. Bestimmen Sie die genaue Ausgabe, vergleichen Sie offizielle Angaben und Booklet und notieren Sie die Quelle jeder Datumsangabe. Leiten Sie das Aufnahmejahr nicht aus dem Veröffentlichungsjahr ab."
primary_keyword: "Aufnahmedatum und Veröffentlichungsdatum"
secondary_keywords: ""
card_title: "Aufnahmedatum und Veröffentlichungsdatum in Musik-Metadaten unterscheiden"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "Aufnahmedatum und Veröffentlichungsdatum"
canonical_url: "https://onnellab.com/blog/de/distinguish-recording-date-from-release-date/"
---

# Aufnahmedatum und Veröffentlichungsdatum in Musik-Metadaten unterscheiden

Das Aufnahmedatum bezeichnet den Zeitpunkt der Aufnahme, das Veröffentlichungsdatum den Zeitpunkt der Veröffentlichung. Bestimmen Sie die genaue Ausgabe, vergleichen Sie offizielle Angaben und Booklet und notieren Sie die Quelle jeder Datumsangabe. Leiten Sie das Aufnahmejahr nicht aus dem Veröffentlichungsjahr ab.

## Beginnen Sie mit einer bestimmten Ausgabe

In einem Albumordner können mehrere plausible Jahreszahlen stehen. Bestimmen Sie vor einer Änderung die Ausgabe anhand von Format, Label, Katalognummer und Titelliste. Angaben zu einer anderen Ausgabe müssen nicht auf Ihre Dateien zutreffen.

Die [Release-Dokumentation von MusicBrainz](https://musicbrainz.org/doc/Release) behandelt das Erscheinungsdatum einer Ausgabe als Veröffentlichungsangabe. Prüfen Sie für Ihr Exemplar die offiziellen Informationen des Künstlers oder Labels und das passende Booklet.

## Trennen Sie drei Fragen

| Frage | Gesuchte Belege | Unzulässige Annahme |
| --- | --- | --- |
| Wann wurde diese Darbietung aufgenommen? | Ausdrückliches Aufnahmedatum im Booklet oder in offiziellen Erläuterungen | Veröffentlichungsjahr gleich Aufnahmejahr |
| Wann wurde diese Aufnahme erstmals veröffentlicht? | Offizielle Angaben zur Erstveröffentlichung | Datum einer Neuauflage gleich Erstveröffentlichung |
| Wann erschien diese Ausgabe? | Angaben zur passenden Ausgabe und zum Veröffentlichungsgebiet | Alle Ausgaben haben dasselbe Datum |

Ein Remastering-Jahr, ein Copyright-Vermerk oder der Änderungszeitpunkt einer Datei beantwortet diese drei Fragen für sich genommen nicht.

## Fünf Schritte vor einer Änderung

1. Bewahren Sie eine Sicherung auf und prüfen Sie zunächst einen Titel. Notieren Sie vorhandene Datumswerte, ohne sie zu überschreiben.
2. Gleichen Sie die Ausgabe ab. Erfassen Sie, soweit bekannt, Label, Katalognummer, Format und Veröffentlichungsgebiet.
3. Lesen Sie Booklet und offizielle Veröffentlichungsseite. Halten Sie fest, was das jeweilige Datum laut Quelle bezeichnet, einschließlich Seitenzahl oder URL.
4. Bleiben Sie bei der belegten Genauigkeit. Ist nur das Jahr bekannt, erfinden Sie weder Monat noch Tag. Notieren Sie Widersprüche separat.
5. Prüfen Sie vor dem Speichern einer Testkopie die Felddefinitionen des Editors und die Anzeige im Player. Ein Feld namens „Jahr“ erhält möglicherweise nicht alle Unterschiede. Öffnen Sie die gespeicherte Kopie erneut und kontrollieren Sie sie, bevor Sie weitere Dateien bearbeiten.

Die [ID3v2.4-Spezifikation](https://id3.org/id3v2.4.0-frames) unterscheidet Zeitangaben für Aufnahme, Erstveröffentlichung und Veröffentlichung. Das beweist nicht, dass ein bestimmter Editor alle Felder anbietet oder ein Player sie wie erwartet anzeigt. Diese Anleitung legt keine Zuordnung zu Tag-Feldern fest.

## Ein erfundenes Beispiel

Angenommen, das Booklet nennt ausdrücklich 1998 als Aufnahmejahr, offizielle Erläuterungen nennen 2000 als Erstveröffentlichung und Ihre Ausgabe erschien 2024. Bewahren Sie die drei Angaben getrennt mit ihren Quellen auf. Eine Ausgabe von 2024 macht die Darbietung nicht zu einer Aufnahme von 2024.

Fehlt das Aufnahmedatum, schreiben Sie „unbekannt“ in Ihre Recherchenotizen. Übernehmen Sie nicht einfach 2000 oder 2024 in das Aufnahmefeld, um eine Lücke zu füllen.

## Häufige Fragen

### Kann ich alle Titel gemeinsam ändern?
Prüfen Sie zuerst, ob die Belege für alle Titel gelten. Ein Album kann mehrere Aufnahmesitzungen oder Bonustitel enthalten.

### Welches Datum soll mein Player anzeigen?
Das hängt von Ihrem Ordnungsziel und dem Verhalten des Players ab. Bewahren Sie zunächst die getrennten Fakten und testen Sie anschließend eine Kopie. Verzichten Sie nicht zugunsten einer aufgeräumten Anzeige auf Quellenangaben.

### Was tun bei widersprüchlichen Quellen?
Bewahren Sie beide Verweise auf und beschreiben Sie den Widerspruch. Prüfen Sie, ob dieselbe Ausgabe und dasselbe Veröffentlichungsgebiet gemeint sind. Lassen Sie die Angabe offen, statt das bequemere Jahr auszuwählen.

## Nächster Schritt

Wählen Sie ein Album und erstellen Sie vor der Tag-Bearbeitung eine Quellennotiz. Ein anderes Thema behandelt die Anleitung zum [Unterscheiden doppelter Dateien von verschiedenen Aufnahmen](/blog/de/distinguish-duplicate-music-files-from-different-recordings/). Datumsangaben allein beweisen nicht, dass zwei Dateien dieselbe Aufnahme enthalten.
