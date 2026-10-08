---
title: "Inhaltsverzeichnis und Kapitelreihenfolge einer EPUB prüfen"
card_title: "Inhaltsverzeichnis und Kapitelreihenfolge einer EPUB prüfen"
slug: "check-epub-table-of-contents-and-reading-order"
category: "reading"
language: "de"
description: "Vergleichen Sie die exportierte EPUB mit der geplanten Kapitelliste und prüfen Sie Links und Lesereihenfolge getrennt."
status: "review"
topic_id: "TOPIC-0059"
search_intent: "troubleshoot"
primary_keyword: "Inhaltsverzeichnis einer EPUB prüfen"
secondary_keywords: "EPUB Kapitelreihenfolge|EPUB Navigation prüfen|fehlende EPUB-Kapitel|Papira"
related_apps: "Papira"
tags: "EPUB|Inhaltsverzeichnis|Lesereihenfolge|Navigation|E-Book-Prüfung"
short_answer: "Notieren Sie die erwarteten Kapitel, öffnen Sie die EPUB in einem separaten Leseprogramm und testen Sie jeden Inhaltsverzeichnis-Link. Prüfen Sie Kapitelübergänge, dokumentieren und korrigieren Sie Abweichungen und kontrollieren Sie den neuen Export."
canonical_url: "https://onnellab.com/blog/de/check-epub-table-of-contents-and-reading-order/"
image_specs: "Erwartete Kapitel|Inhaltsverzeichnis-Links|Lesereihenfolge|Korrigieren und erneut exportieren"
---

# Inhaltsverzeichnis und Kapitelreihenfolge einer EPUB prüfen

Die EPUB lässt sich öffnen, das Inhaltsverzeichnis sieht plausibel aus. Führt aber jeder Eintrag zum richtigen Kapitel? Folgen diese Kapitel beim normalen Weiterlesen in derselben Reihenfolge? Wenn Sie das Inhaltsverzeichnis einer EPUB prüfen und die Lesereihenfolge abgleichen möchten, nutzen Sie eine Kapitelliste aus dem Manuskript als Referenz. Testen Sie sowohl die Links als auch die normale Lesefolge.

Dieser Leitfaden beginnt mit der exportierten Datei. Er beschreibt eine wiederholbare Prüfung, ohne Cover, Zeichenkodierung oder Manuskriptvorbereitung neu aufzurollen.

## Frage

Wie prüfe ich, ob Inhaltsverzeichnis-Links und Kapitelreihenfolge einer EPUB zum Manuskript passen?

## Kurzantwort

Notieren Sie die erwarteten Kapitel, öffnen Sie die EPUB in einem separaten Leseprogramm und testen Sie jeden Inhaltsverzeichnis-Link. Prüfen Sie Kapitelübergänge, dokumentieren und korrigieren Sie Abweichungen und kontrollieren Sie den neuen Export. Bewahren Sie Originalmanuskript und bisherigen Export auf, bis die Ersatzdatei geprüft ist.

## Drei Prüfpunkte unterscheiden

Die **Eintragsbezeichnung** ist der auswählbare Text im Inhaltsverzeichnis. Das **Linkziel** ist die dadurch geöffnete Stelle. Die **Lesereihenfolge** bezeichnet die Abfolge beim Weiterlesen, ohne erneut einen Eintrag auszuwählen.

EPUB 3 bildet Navigation und Standardlesereihenfolge getrennt ab: Das Navigationsdokument liefert das Inhaltsverzeichnis, die Spine des Pakets ordnet die Inhaltsdokumente. Auch die Reihenfolge innerhalb jedes Dokuments zählt. Diese Struktur beschreibt [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/). Für die folgenden Prüfungen müssen Sie keine internen Dateien bearbeiten.

| Prüfung | Was sie zeigt | Was offenbleibt |
| --- | --- | --- |
| Inhaltsverzeichnis mit Liste vergleichen | Erwartete Einträge und verständliche Bezeichnungen | Ziele der Links |
| Jeden Eintrag öffnen | Richtige Überschrift und Textanfang | Folgendes Kapitel beim Weiterlesen |
| Kapitelgrenzen überschreiten | Übereinstimmung der Lesefolge mit dem Plan | Richtigkeit aller Inhaltsverzeichnis-Links |
| EPUBCheck ausführen | Erfüllung der geprüften EPUB-Regeln | Übereinstimmung mit der redaktionellen Absicht |

Eine Inhaltsverzeichnisseite im Buch und das Menü des Leseprogramms können getrennt erscheinen. Prüfen Sie das Menü und gegebenenfalls auch die Links der enthaltenen Inhaltsverzeichnisseite.

## Die erwartete Kapitelliste anlegen

Nehmen Sie das Manuskript als Referenz. Notieren Sie die Kapitel in der beabsichtigten Reihenfolge sowie erwartetes Vor- und Nachmaterial, etwa Vorwort oder Nachwort. Legen Sie fest, welche Abschnitte auch im Inhaltsverzeichnis stehen sollen. Nicht jeder Absatz braucht einen Eintrag.

Ergänzen Sie bei wiederholten Überschriften einen kurzen Satzteil aus dem ersten Absatz in Ihrer privaten Prüfliste. So lassen sich beispielsweise zwei Kapitel namens „Notizen“ unterscheiden. Verwenden Sie Überschriften und wiedererkennbaren Text statt Seitenzahlen des Leseprogramms, die sich durch Layouteinstellungen ändern können.

Halten Sie Exportdateiname, Manuskriptstand, Konverterversion sowie Name und Version des Leseprogramms fest. Prüfen Sie nach einem erneuten Export, ob wirklich die neue Datei geöffnet wird und keine früher importierte Kopie. Sichern Sie Anmerkungen, bevor Sie einen älteren Bibliothekseintrag entfernen.

## Beobachtungen in einer Tabelle erfassen

Das folgende Lehrbeispiel ist frei erfunden. Es beschreibt weder einen beobachteten Fehler noch einen Gerätetest. Erwartet wird „Ankunft“, „Der Pfad“, „Rückkehr“. Übernehmen Sie die Spalten und tragen Sie Ihre eigenen Beobachtungen ein.

| Erwartete Überschrift | Verzeichniseintrag | Tatsächliches Ziel | Folgendes Kapitel | Ergebnis | Folgeprüfung an Quelle oder Einstellungen |
| --- | --- | --- | --- | --- | --- |
| 1 Ankunft | 1 Ankunft | 1 Ankunft | 2 Der Pfad | Stimmt überein | Keine |
| 2 Der Pfad | 2 Der Pfad | 3 Rückkehr | Noch ungeprüft | Falsches Ziel | Kapitelgrenze und dokumentierte Exportregeln prüfen |
| 3 Rückkehr | 3 Rückkehr | 3 Rückkehr | Ende des Haupttexts | In dieser Prüfung korrekt | Erwartetes Nachwort separat prüfen |

Die zweite Zeile hält nur die hypothetische Linkprüfung fest. Sie beweist nicht, dass Kapitel 2 fehlt. Suchen Sie dessen Textanfang oder lesen Sie ab Kapitel 1 weiter, bevor Sie zwischen fehlendem Inhalt und falschem Link unterscheiden.

## Empfohlener Ablauf

Verwenden Sie für diese Prüfungen ein separates EPUB-Leseprogramm.

1. **Den richtigen Export öffnen.** Notieren Sie Manuskript- und EPUB-Dateinamen. Verwenden Sie ein kompatibles Leseprogramm und prüfen Sie dessen Import- oder Synchronisationsverhalten, bevor Sie ein vertrauliches Manuskript öffnen.
2. **Das gesamte Inhaltsverzeichnis vergleichen.** Achten Sie auf fehlende Abschnitte, unerwartete Einträge, doppelte Bezeichnungen und eine abweichende Abfolge. Klappen Sie eingeklappte Gruppen auf, sofern vorhanden.
3. **Jeden Link testen.** Vergleichen Sie Überschrift und erste wiedererkennbare Passage mit Ihrer Referenz. Dass ein Link irgendwo im Buch landet, macht sein Ziel noch nicht richtig. Notieren Sie die tatsächlich geöffnete Stelle.
4. **Normales Weiterlesen getrennt prüfen.** Beginnen Sie vor dem ersten Hauptkapitel. Lesen Sie über dessen Ende hinweg, ohne das Inhaltsverzeichnis zu verwenden. Prüfen Sie Vorseiten und Übergänge am Anfang, in der Mitte und am Ende; kontrollieren Sie danach alle übrigen Kapitelgrenzen, bevor das gesamte Buch als geprüft gilt.
5. **Das Buchende prüfen.** Erreicht das letzte Kapitel seinen vorgesehenen Schluss? Bleiben Nachwort oder Anhang erreichbar? Unterscheiden Sie erwartetes Zusatzmaterial von der Hauptkapitelfolge.
6. **Bei entsprechenden Vertriebsanforderungen ein zweites Leseprogramm verwenden.** Öffnen Sie denselben Export. Halten Sie bei Abweichungen Datei- und Programmversionen fest. Ein Unterschied ist ein Untersuchungsbefund, aber noch kein Beweis für die verantwortliche Komponente.

![Schematischer Ablauf von der erwarteten Kapitelliste über Link- und Lesefolgeprüfung zur Quellkorrektur vor dem erneuten Export.](/blog-assets/de/check-epub-table-of-contents-and-reading-order/workflow-diagram.svg "Links und Lesereihenfolge getrennt prüfen")

Das Diagramm zeigt einen vorgeschlagenen Ablauf, keinen Screenshot und keinen Nachweis abgeschlossener Tests.

## Abweichungen vor Änderungen eingrenzen

| Symptom | Benötigter Befund | Nächster Schritt |
| --- | --- | --- |
| Kapitel fehlt im Inhaltsverzeichnis | Ist sein Text beim Weiterlesen vorhanden? | Falls ja: Überschriftenerkennung und vorgesehenen Umfang prüfen; falls nein: Vollständigkeit der Quelle und Exportgrenzen prüfen |
| Richtige Bezeichnung öffnet falsches Kapitel | Geöffnete Überschrift und Text notieren | Quellgrenze und dokumentierte Überschriftenregeln vergleichen; mit kurzem Beispiel reproduzieren |
| Zwei Einträge heißen gleich | Beide Ziele und Quellüberschriften vergleichen | Absichtliche Wiederholung ausschließen, bevor Titel geändert oder Markierungen entfernt werden |
| Links stimmen, Weiterlesen überspringt oder vertauscht Kapitel | Tatsächlichen Übergang und erwartetes Folgekapitel festhalten | Quellreihenfolge und verfügbare Exportoptionen prüfen; bei korrekter Quelle Ergebnis zur Diagnose aufbewahren |
| Nur ein Leseprogramm zeigt den Fehler | Identischen Exportstand bestätigen | Exakten Übergang wiederholen und Versionen vergleichen, bevor eine Ursache zugewiesen wird |

Ändern Sie jeweils nur einen relevanten Punkt. Korrigieren Sie das Arbeitsmanuskript oder eine dokumentierte Konvertierungseinstellung, exportieren Sie unter unterscheidbarem Namen und prüfen Sie betroffenen Eintrag und benachbarte Übergänge erneut. Wiederholen Sie abschließend sämtliche Linkprüfungen: Strukturänderungen können mehrere Ziele betreffen.

Bleibt die Abweichung bei sauberer Quelle bestehen, bewahren Sie das Original auf und erstellen Sie ein kurzes Beispiel mit eigenem oder zur Weitergabe freigegebenem Text. Beschreiben Sie dem Support erwartete und tatsächliche Ziele. Ein unveröffentlichtes Gesamtmanuskript ist zur Demonstration eines einzelnen Navigationsfehlers nicht nötig.

## Validierung und Leseprüfung verbinden

[EPUBCheck](https://www.w3.org/publishing/epubcheck/) prüft Publikationen gegen EPUB-Spezifikationen. Untersuchen Sie Paketfehler und Warnungen und validieren Sie die neu erzeugte Datei erneut. Ein erfolgreicher Bericht entscheidet nicht, ob „Kapitel 2“ den beabsichtigten Inhalt enthält.

Auch erfolgreiches Öffnen in einem Leseprogramm belegt weder vollständige Konformität noch Barrierefreiheit oder universelle Kompatibilität. Halten Sie Validierungsbericht, Navigationsbeobachtungen und ungeprüfte Programme oder Abschnitte getrennt fest. Validieren Sie vertrauliche Texte lokal oder prüfen Sie vor einem Upload den Umgang des Dienstes mit Daten.

## Wo ONNELLAB dazu passt

Wenn Sie aus einem fertigen TXT-Manuskript erneut eine EPUB erstellen müssen, ist Papira eine optionale ONNELLAB-App dafür. Die offiziellen Store-Seiten beschreiben die Offline-Erstellung mit Cover, Buchangaben und Inhaltsverzeichnis. Bearbeiten Sie das Manuskript andernorts und prüfen Sie den Export in einem anderen Leseprogramm: Papira bietet weder die Bearbeitung des Buchtexts noch einen EPUB-Reader.

Die Überschriftenerkennung hängt von der dokumentierten Plattform und Version ab. Aus Oberflächensprachen lassen sich keine unterstützten Überschriftenmuster ableiten; identisches Verhalten unter iOS und Android ist ebenfalls nicht vorauszusetzen. Daher gibt dieser Ablauf keine universelle automatische Erkennungsregel vor. Prüfen Sie die Anleitung Ihrer installierten Version und gleichen Sie das erzeugte Verzeichnis mit Ihrer Liste ab.

Beachten Sie die offiziellen Einträge für [Papira im App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) und [Papira bei Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira) für Ihre Plattform und Region. Die Prüfmethode funktioniert auch mit anderen EPUB-Exportern.

## Weiterführender Leitfaden

Liegt die Ursache in der Manuskriptvorbereitung, hilft [Ein TXT-Manuskript für die EPUB-Konvertierung vorbereiten](/blog/de/prepare-txt-manuscript-for-epub/). Dieser Leitfaden behandelt die Vorbereitung; die vorliegende Prüfliste setzt nach dem Export an.

## Quellen

- [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/): Navigationsdokument und Spine für die Standardlesereihenfolge.
- [W3C EPUBCheck](https://www.w3.org/publishing/epubcheck/): EPUB-Konformitätsprüfung.
- [Papira im App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) und [bei Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira): Funktionsumfang und plattformspezifische Hinweise.

## Fazit

Eine brauchbare Navigationsprüfung vergleicht Absicht und Beobachtung. Führen Sie die erwartete Kapitelliste, testen Sie jeden Link und prüfen Sie die normale Lesefolge. Sichern Sie bei Abweichungen die Befunde, korrigieren Sie Quelle oder unterstützte Exportoptionen und prüfen Sie die neue Datei vor der Weitergabe.

## Häufige Fragen

### Beweist eine sichtbare Kapitelüberschrift, dass der Link stimmt?

Nein. Öffnen Sie den Eintrag und vergleichen Sie Überschrift und Textanfang am Ziel. Bezeichnung und Zielstelle sind getrennte Prüfpunkte.

### Fehlt ein Kapitel auch im Buch, wenn es nicht im Menü steht?

Nicht unbedingt. Sein Text kann in der Lesefolge vorhanden sein. Suchen Sie den Anfang und prüfen Sie den vorgesehenen Verzeichnisumfang, bevor Sie fehlenden Inhalt diagnostizieren.

### Warum können Links stimmen und Kapitel trotzdem falsch angeordnet sein?

Linkauswahl und Weiterlesen nutzen unterschiedliche Wege. Dokumentieren Sie das tatsächlich folgende Kapitel separat und vergleichen Sie es mit Manuskript und Exporteinstellungen.

### Ist das Buch nach bestandenem EPUBCheck vertriebsbereit?

Das ist eine hilfreiche Teilprüfung. Prüfen Sie weiterhin Text, Navigation, Lesefolge sowie Anforderungen von Publikum oder Vertrieb. Der Bericht ersetzt keine redaktionelle oder Barrierefreiheitsprüfung.

### Sollte ich die exportierte EPUB direkt korrigieren?

Korrigieren Sie möglichst Quelle oder dokumentierte Einstellungen, damit der nächste Export die Änderung enthält. Erfordert der Publikationsablauf Paketbearbeitung, dokumentieren Sie diese reproduzierbar und vermeiden Sie widersprüchliche Fassungen.

### Kann ich diese Leseprüfungen in Papira durchführen?

Nein. Papira erstellt EPUBs aus fertigen TXT-Manuskripten und ist kein EPUB-Reader. Öffnen Sie den Export in einem separaten Leseprogramm und ändern Sie das Manuskript in einem Texteditor.
