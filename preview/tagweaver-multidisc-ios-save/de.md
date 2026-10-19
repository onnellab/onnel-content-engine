---
title: "Tracks in einem MP3-Album mit mehreren Discs nummerieren"
card_title: "Tracks in einem MP3-Album mit mehreren Discs nummerieren"
slug: "number-tracks-multi-disc-mp3-album"
category: "music"
language: "de"
description: "Tracknummer und Discnummer in mehrteiligen MP3-Alben getrennt eintragen: TRCK, TPOS, geprüfte Gesamtzahlen, Sicherung und ein kleiner Test in der Zielbibliothek."
status: "published"
topic_id: "TOPIC-0029"
search_intent: "workflow"
primary_keyword: "Tracks in einem MP3-Album mit mehreren Discs nummerieren"
secondary_keywords: "MP3-Tracknummer|Discnummer-Tags|ID3 TRCK TPOS|TagWeaver"
related_apps: "TagWeaver"
tags: "MP3-Album mit mehreren Discs|MP3-Tracknummer|Discnummer-Tags|ID3 TRCK TPOS"
short_answer: "Trage die Position des Songs auf seiner Disc ins Trackfeld und die Position der Disc im Set ins Discfeld ein. Ergänze Gesamtzahlen nur nach Prüfung, sichere die Originale und teste zunächst wenige Kopien im Editor und in der Zielbibliothek."
canonical_url: "https://onnellab.com/blog/de/number-tracks-multi-disc-mp3-album/"
published_at: "2026-09-04T09:00:00+09:00"
updated_at: "2026-09-04T09:00:00+09:00"
image_specs: "Nummerierung mehrerer Discs mit vorheriger Sicherung|Zuordnung der Felder TRCK und TPOS|Prüfung in der Zielbibliothek"
related_articles: "MP3-Metadaten vor dem Sortieren der Musiksammlung bereinigen => https://onnellab.com/blog/de/clean-up-mp3-metadata-before-organizing-music/|TXT oder EPUB für langes Lesen? => https://onnellab.com/blog/de/txt-vs-epub-for-long-reading/|Große TXT-Dateien ohne Ruckeln lesen => https://onnellab.com/blog/de/read-large-txt-files-without-lag/|Warum das Öffnen großer Textdateien lange dauert => https://onnellab.com/blog/de/large-text-file-slow-to-open/|Lokale Mediendateien privat konvertieren => https://onnellab.com/blog/de/convert-local-media-files-privately/|Audioaufnahmen ohne vollständigen Editor zuschneiden => https://onnellab.com/blog/de/trim-audio-recordings-without-full-editor/"
---

# Tracks in einem MP3-Album mit mehreren Discs nummerieren

Ein Boxset hat zwei Reihenfolgen: Songs innerhalb einer Disc und Discs innerhalb des Sets. Erfasse beide getrennt, lass unsichere Angaben offen und prüfe eine Stichprobe, bevor du das gesamte Album bearbeitest.

## Frage

Wie kann ich Tracks in einem MP3-Album mit mehreren Discs nummerieren?

## Kurzantwort

Das Trackfeld enthält die Songposition auf der jeweiligen Disc, das Discfeld die Discposition im Set. Der vierte Song auf Disc zwei eines Dreiersets kann Track `4`, Disc `2` erhalten. Gesamtzahlen wie `4/11` und `2/3` gehören nur hinein, wenn sie bestätigt sind. Bearbeite Kopien, verwende einheitliche Album- und Albuminterpret-Angaben und prüfe eine gespeicherte Stichprobe im Editor und in der Zielbibliothek.

## Trackposition und Discposition unterscheiden

Die **Trackposition** bezeichnet die Stelle eines Songs innerhalb seiner Disc. In ID3v2 speichert der Frame `TRCK` diesen Wert. ID3v2.4 erlaubt eine numerische Position mit optionalem Schrägstrich und Gesamtzahl, etwa `4/11`. Auch `4` allein ist eine vollständige Positionsangabe.

Die **Discposition** bezeichnet den Teil innerhalb eines Sets. `TPOS` verwendet dasselbe Muster: `2/3` bedeutet Teil zwei von drei. Bei Musik ist der Teil meist eine physische oder logische Disc. Das legt jedoch nicht fest, wie jede Musik-App das Feld benennt.

`TRCK=4/11` und `TPOS=2/3` erhalten „Track vier auf Disc zwei“. Eine durchgehende Nummer wie 15 bewahrt möglicherweise eine Abspielreihenfolge, aber nicht den Beginn der zweiten Disc. Eine persönliche durchgehende Nummerierung ist möglich; sie ist jedoch von den ursprünglichen Trackpositionen pro Disc zu unterscheiden.

## Vor dem Bearbeiten eine Regel festlegen

Nutze eine verlässliche Titelliste der genauen Ausgabe, etwa das Booklet oder die offizielle Liste des Verlags oder Labels. Deluxe-, Regional-, Neu- und Bonus-Disc-Ausgaben können unterschiedliche Titelzahlen haben. Ein ähnlicher Albumname reicht als Beleg nicht.

Notiere vorab:

- den exakten Albumnamen für alle Tracks;
- einen gemeinsamen Albuminterpreten, falls zur Veröffentlichung passend;
- die tatsächlich vorhandenen und eventuell fehlenden Discs;
- die Trackzahl jeder Disc und die Zuordnung von Bonusmaterial;
- welche Gesamtzahlen sicher bekannt sind;
- die gedruckte Tracknummerierung pro Disc oder eine dokumentierte persönliche Regel.

Wenn die Quelle Discs getrennt aufführt, beginne auf jeder Disc wieder mit Track 1 und unterscheide sie durch `TPOS`. Erfinde keine fehlende Disc oder Gesamtzahl, um Felder zu füllen. Eine bekannte Position ist besser als eine präzise wirkende Falschangabe.

## Eine Feldzuordnung für die Stapelbearbeitung erstellen

Für ein Doppelalbum eignen sich folgende Grenzfälle:

| Datei | Track (`TRCK`) | Disc (`TPOS`) | Prüfen |
| --- | --- | --- | --- |
| Erster Song auf Disc 1 | `1/10` | `1/2` | Richtige Ausgabe mit zehn Tracks |
| Letzter Song auf Disc 1 | `10/10` | `1/2` | Keine Lücken oder doppelten Positionen |
| Erster Song auf Disc 2 | `1/12` | `2/2` | Bewusster Neustart bei 1 |
| Letzter Song auf Disc 2 | `12/12` | `2/2` | Track- und Discgesamtzahlen stimmen |

Ohne bestätigte Gesamtzahlen genügen Tracks `1`, `10`, `1`, `12` und Discs `1` oder `2`. Schreibe keine Beschreibung wie „zweite Disc“ in numerische Positionsfelder; halte Unsicherheiten separat fest.

## Originale sichern und nach Disc auswählen

Bewahre eine unveränderte Kopie außerhalb des Arbeitsordners auf. Eine Sicherung, die zusammen mit den Arbeitsdateien überschrieben wird, ist nicht unabhängig. Eine Dateiliste oder Prüfsummen können beim Vergleich helfen.

Gruppiere Arbeitskopien nach der tatsächlichen Disc. Ein Ordner namens `CD2` ist nur ein Hinweis: Vergleiche Titel, Laufzeiten und vorhandene Tags mit der verlässlichen Liste. Nimm unsichere Dateien aus der Stapelauswahl.

Übertrage nur wirklich gemeinsame Werte: Albumdaten im ganzen Set, Discposition innerhalb einer Disc. Titel und Trackpositionen bleiben songspezifisch. Prüfe die Zuordnung auch dann, wenn ein Werkzeug fortlaufende Nummern vergibt.

## Empfohlener Arbeitsablauf

1. **Quelle sichern.** Kopiere das komplette Album an einen Arbeitsort und lass das Original unverändert. Prüfe, ob alle erwarteten Discs und Dateien vorhanden sind.
2. **Ausgabe bestimmen.** Vergleiche Titel, Laufzeiten, Bonusmaterial und gedruckte Discgrenzen mit einer zuverlässigen Liste. Markiere Abweichungen, statt Dateien in die Reihenfolge zu zwingen.
3. **Nummerierung wählen.** Für die ursprüngliche Veröffentlichung nutze Trackpositionen pro Disc und ein separates Discfeld. Dokumentiere eine persönliche durchgehende Folge ausdrücklich.
4. **Felder zuordnen.** Erfasse Titel, `TRCK`, optionale Trackgesamtzahl, `TPOS` und optionale Discgesamtzahl. Suche pro Disc nach Lücken und Doppelungen.
5. **Stichprobe bearbeiten.** Wähle den ersten und letzten Track einer Disc sowie den ersten der nächsten. So erkennst du Fehler an Übergängen und beim Neustart.
6. **Speichern und erneut öffnen.** Schließe den Editor oder hebe die Auswahl auf. Öffne dieselben Dateien erneut und prüfe die gespeicherten Werte. Eine Vorschau beweist keinen Schreibvorgang.
7. **Zielbibliothek testen.** Importiere nur die Stichprobe. Prüfe Albumgruppen, Discgrenzen, Reihenfolge und den ersten Discwechsel. Das Ergebnis gilt für diese App und Version.
8. **Discweise erweitern.** Wende nur die geprüfte Zuordnung an. Öffne je Disc den ersten, einen mittleren und den letzten Track erneut und vergleiche sie mit dem Plan.
9. **Sicherung bis zur zweiten Kontrolle behalten.** Prüfe das gesamte Album nochmals nach der dokumentierten Aktualisierung oder dem erneuten Import der Bibliothek.

![Ablauf der Track- und Discnummerierung](/blog-assets/de/number-tracks-multi-disc-mp3-album/workflow-diagram.svg "Originale sichern, Positionen zuordnen und Discübergänge prüfen")

## Mehr als die sichtbare Reihenfolge prüfen

Eine korrekt aussehende Liste kann fehlerhafte Tags verbergen. Eine Bibliothek kann importierte Daten behalten, alte Werte zwischenspeichern oder eigene Darstellungsregeln anwenden. Öffne zuerst die Dateien im Metadatenleser oder Editor und prüfe `TRCK` und `TPOS`. Aktualisiere oder importiere danach nur die Testgruppe gemäß der Dokumentation der Ziel-App.

Kontrolliere Anfang und Ende jeder Disc, Discwechsel und Bonus-Discs mit abweichender Trackzahl. Suche nach fehlenden oder doppelten Positionen, widersprüchlichen Gesamtzahlen und einer versehentlich auf das gesamte Album angewandten Discnummer. Erfolgreiche Wiedergabe beweist keine korrekte Nummerierung. Tags beschreiben Audio, reparieren aber keine Schäden, bestätigen keine Fakten und garantieren keine lückenlose Wiedergabe.

## Häufige Fehler und sichere Antworten

| Symptom | Mögliche Datenursache | Sichere Reaktion |
| --- | --- | --- |
| Disc 2 erscheint vor Disc 1 | Fehlende oder uneinheitliche Discpositionen | Dateien öffnen und `TPOS` mit dem Plan vergleichen |
| Tracks verschiedener Discs mischen sich | Discwerte fehlen, widersprechen sich oder werden ignoriert | Tags prüfen, dann Zielverhalten nachlesen und testen |
| Doppelte Positionen auf einer Disc | Gemeinsamer Trackwert im Stapel gesetzt | Betroffene Kopien wiederherstellen oder Einzelpositionen zuweisen |
| Album zerfällt in Gruppen | Album oder Albuminterpret unterschiedlich | Exakten Text vor erneutem Nummerieren vergleichen |
| Nur einige Gesamtzahlen sind falsch | Vermischte Ausgaben oder unvollständige Auswahl | Ausgabe prüfen; nur bekannte Gesamtzahlen vereinheitlichen |
| Editor und Player widersprechen sich | Cache oder unterschiedliche Feldunterstützung | Datei prüfen, danach nur die Testgruppe aktualisieren |

## ONNELLAB im Einsatz

[TagWeaver](/apps/tagweaver/) ist ein lokaler MP3-Metadateneditor, mit dem sich eine geprüfte Feldzuordnung auf ausgewählte Dateien anwenden lässt. Die gepflegten Produktangaben beschreiben kostenlose Einzeltrack-Bearbeitung und Stapelbearbeitung als Teil des optionalen Pro-Einmalkaufs. Die offiziellen Store-Einträge nennen Track- und Discwerte als bearbeitbare Metadaten. Prüfe dort die Details für deine Plattform.

Die App bestimmt weder die richtige Ausgabe noch verlässliche Positionswerte. Kläre Liste und Regeln zuerst, halte die Sicherung außerhalb der Auswahl, speichere ausdrücklich und prüfe eine kleine Stichprobe. Laut den Versionshinweisen zu Version 2.5.1 im App Store wird unter iOS beim Speichern die ausgewählte Originaldatei aktualisiert, wenn ihr Speicherort beschreibbar ist; andernfalls fragt TagWeaver nach einem Speicherort für eine Kopie. Erstelle vor dem Bearbeiten eine separate Sicherung und prüfe den Speicherort der gespeicherten Datei.

## Quellen

- [ID3.org: ID3v2.4.0-Frame-Definitionen](https://id3.org/id3v2.4.0-frames): `TRCK`, `TPOS` und optionale Gesamtzahlen nach dem Schrägstrich.
- [ID3.org: ID3v2.4.0-Struktur](https://id3.org/id3v2.4.0-structure): Tag- und Frame-Struktur für Metadaten.
- [ID3.org: ID3v2.3.0-Spezifikation](https://id3.org/id3v2.3.0): frühere Definitionen für Dateien und Werkzeuge dieser Version.
- [TagWeaver im App Store](https://apps.apple.com/app/id6759609875): offizieller iOS-Produkteintrag.
- [TagWeaver bei Google Play](https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2): offizieller Android-Produkteintrag.

## Fazit

Track- und Discposition sind getrennte Fakten. Prüfe die Ausgabe, plane jeden Dateiwert, sichere Originale und teste Übergänge anhand weniger Kopien. Gesamtzahlen, führende Nullen, Dateinamen und Darstellung sind nachgeordnete Konventionen. Korrekte `TRCK`- und `TPOS`-Werte und ein umkehrbarer Ablauf bilden die Grundlage.

## Häufige Fragen

### Beginnt Disc zwei wieder mit Track eins?

Normalerweise ja, wenn du getrennt gedruckte Discfolgen bewahrst. Speichere die Trackposition in `TRCK` und unterscheide die Disc mit `TPOS`. Eine persönliche durchgehende Folge solltest du dokumentieren.

### Sind Gesamtzahlen wie `4/11` und `2/3` Pflicht?

Nein. Ergänze sie nur bei bestätigter Ausgabe und vollständigen Zahlen. Eine richtige Position ist sicherer als eine falsche Gesamtzahl.

### Sortiert danach jeder Player das Album richtig?

Ein einheitliches Verhalten ist nicht garantiert. Jede Ziel-App entscheidet über Lesen, Gruppieren, Zwischenspeichern und Anzeigen. Teste repräsentative Kopien im tatsächlichen Ziel.

### Können Dateinamen die Track- und Disctags ersetzen?

Sie helfen beim Prüfen von Ordnern, belegen aber keine gespeicherten `TRCK`- und `TPOS`-Werte. Halte Umbenennungen getrennt und umkehrbar.

### Verändert die Tagbearbeitung die Klangqualität?

Positionen sind Metadaten, keine Audiosamples. Die Änderung verbessert oder encodiert den Klang grundsätzlich nicht neu. Sichere trotzdem Originale und prüfe die tatsächliche Ausgabe des Editors.
