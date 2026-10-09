---
title: "Konvertierte Mediendateien prüfen, bevor Sie das Original ersetzen"
card_title: "Konvertierte Mediendateien prüfen, bevor Sie das Original ersetzen"
slug: "test-converted-media-before-replacing-original"
category: "media"
language: "de"
description: "Prüfen Sie konvertierte Audio- und Videodateien auf Vollständigkeit, Wiedergabe und benötigte Metadaten. Testen Sie die Datei in der Zielanwendung und sichern Sie das Original."
status: "review"
topic_id: "TOPIC-0067"
search_intent: "workflow"
primary_keyword: "konvertierte Mediendateien prüfen"
secondary_keywords: "konvertierte Audiodatei prüfen|Videowiedergabe testen|Medienmetadaten|Originaldatei sichern"
related_apps: "Quivra"
tags: "konvertierte Mediendateien prüfen|konvertierte Audiodatei prüfen|Videowiedergabe testen|Medienmetadaten|Originaldatei sichern"
short_answer: "Behalten Sie das Original, untersuchen Sie die exportierte Datei, spielen Sie repräsentative Stellen in der Zielanwendung ab und prüfen Sie benötigte Spuren und Metadaten. Klären Sie Unterschiede, bevor Sie das Ergebnis akzeptieren. Eine erfolgreiche Stichprobe rechtfertigt nicht, das einzige Original zu löschen."
canonical_url: "https://onnellab.com/blog/de/test-converted-media-before-replacing-original/"
image_specs: "Original behalten|Änderungen prüfen|Am Ziel testen|Notieren und sichern"
---

# Konvertierte Mediendateien prüfen, bevor Sie das Original ersetzen

Die Konvertierung ist fertig und die neue Datei lässt sich öffnen. Das ist ein guter Anfang. Es zeigt aber noch nicht, ob das Ende vollständig ist, der gewünschte Ton vorhanden ist oder die Zielanwendung die Datei richtig verarbeitet. Prüfen Sie diese Fragen einzeln, bevor Sie eine Arbeitskopie ersetzen, und bewahren Sie eine Möglichkeit zur Wiederherstellung auf.

## Frage

Wie prüfe ich eine konvertierte Mediendatei, bevor ich das Original ersetze?

## Kurzantwort

Behalten Sie das Original, untersuchen Sie die exportierte Datei, spielen Sie repräsentative Stellen in der Zielanwendung ab und prüfen Sie benötigte Spuren und Metadaten. Klären Sie Unterschiede, bevor Sie das Ergebnis akzeptieren. Eine erfolgreiche Stichprobe rechtfertigt nicht, das einzige Original zu löschen.

## Festlegen, was ein gutes Ergebnis erhalten muss

Eine **Abnahmeprüfung** ist ein Vergleich der Ausgabedatei mit den Anforderungen, die Sie für ihren vorgesehenen Einsatz festgehalten haben. Sie ist keine Zusage, dass die neue Datei mit ihrer Quelle identisch ist.

Notieren Sie den Namen der Quelldatei, den Namen der Ausgabedatei, die Zielanwendung oder das Zielgerät und die Inhalte, die erhalten bleiben müssen. Bei einer Audioaufnahme können das die ersten und letzten gesprochenen Wörter, verständliche Sprache und die benötigten Kanäle sein. Bei Videos gehören Bild, Ton und deren Synchronität dazu. Wenn Untertitel, Kapitel, Coverbilder oder Metadaten-Tags wichtig sind, nehmen Sie diese ausdrücklich in die Liste auf, statt ihre Übernahme vorauszusetzen.

Unterscheiden Sie beabsichtigte Änderungen von Fehlern. Wer Ton aus einem Video extrahiert, entfernt das Bild absichtlich. Ein fehlendes Bild ist nur dann ein Problem, wenn das Ergebnis weiterhin ein Video sein sollte. Dieser Leitfaden beginnt nach der Konvertierung. Falls das Zielformat noch offen ist, hilft der unten verlinkte Leitfaden zur Formatwahl.

## Drei Prüfungen beantworten unterschiedliche Fragen

| Prüfung | Hilfreicher Nachweis | Was sie nicht belegen kann |
| --- | --- | --- |
| Dateieigenschaften untersuchen | Dauer, Streams und verfügbare Metadaten entsprechen Ihren Anforderungen | Jede Stelle wird korrekt wiedergegeben |
| Am Ziel abspielen | Die tatsächliche Zielanwendung verarbeitet die geprüften Stellen | Ungeprüfte Stellen oder ein anderes Gerät funktionieren ebenfalls |
| Prüfsumme einer Sicherung überprüfen | Die kopierte Datei stimmt mit dem gespeicherten Byte-Fingerabdruck überein | Die Konvertierung klingt oder sieht richtig aus |

Ein **Stream** ist eine einzelne Medienkomponente, etwa eine Audio- oder Videospur. Ein Werkzeug für Dateiinformationen kann diese Komponenten auflisten. Die [ffprobe-Dokumentation von FFmpeg](https://ffmpeg.org/ffprobe.html) beschreibt die Untersuchung von Containern, Streams und Tags. Nutzen Sie ein separates Analysewerkzeug, wenn Ihr Konverter diese Einzelheiten nicht anzeigt. Ein Analysebericht ersetzt keinen Hör- oder Sichttest.

## Empfohlener Arbeitsablauf

1. **Quelle getrennt aufbewahren.** Verwenden Sie verschiedene Ordner für Quelle und Ausgabe oder eindeutig unterscheidbare Dateinamen. Halten Sie fest, welche Datei Sie konvertiert haben. Überschreiben Sie nicht die einzige Quelle und verhindern Sie, dass sie während der Prüfung beim Aufräumen gelöscht wird.
2. **Die exportierte Datei selbst öffnen.** Suchen Sie sie im Dateimanager und bestätigen Sie Namen und Pfad. Eine Vorschau im Konverter oder ein alter Eintrag in der Mediathek des Players kann auf eine andere Datei verweisen. Notieren Sie die Versionen von Konverter und Player, damit sich die Prüfung sinnvoll wiederholen lässt.
3. **Die wichtigen Eigenschaften vergleichen.** Prüfen Sie die ungefähre Dauer, die erwarteten Audio- und Videospuren, die Kanalinformationen, bei Videos die Bildabmessungen sowie benötigte Tags. Die Dateigröße allein ist kein Qualitätsmaß. Eine große Abweichung bei der Dauer muss untersucht werden. Kleine Unterschiede können auf die Anzeige oder das Verhalten des Formats zurückgehen; vergleichen Sie deshalb auch den tatsächlichen Anfang und das Ende.
4. **Repräsentative Stellen abspielen.** Hören oder sehen Sie sich Anfang, Mitte und Ende an. Beziehen Sie leise Sprache, eine laute Passage, einen Szenenwechsel oder anderes anspruchsvolles Material aus Ihrer Datei ein. Springen Sie vorwärts und rückwärts. Achten Sie bei Videos auf sichtbare Sprechbewegungen oder einen sichtbaren Aufprall, um die zeitliche Zuordnung des Tons zu beurteilen. Achten Sie bei Audiodateien auf fehlende Inhalte, Verzerrungen und unerwartete Stille.
5. **Das tatsächliche Ziel verwenden.** Importieren Sie die Ausgabedatei in den Player, das Schnittprogramm oder das Gerät, das Sie nutzen möchten. Testen Sie dort gegebenenfalls die Auswahl benötigter Spuren und die Untertitel. Wenn das Hochladen dieser Datei angemessen ist und der Dienst hochgeladene Dateien verarbeitet, prüfen Sie auch dessen Verarbeitungsergebnis. Ein bestandener Test im Konverter ersetzt diese Prüfung nicht.
6. **Ergebnis festhalten und Wiederherstellungskopien behalten.** Notieren Sie Ausgabedatei, Ziel, geprüfte Stellen und alle Einschränkungen. Wichtige, nicht wiederholbare Aufnahmen sollten vollständig angehört oder angesehen werden; Stichproben lassen Abschnitte ungeprüft. Bewahren Sie eine getrennt gespeicherte Sicherung des Originals auf. Prüfen Sie, ob Sie darauf zugreifen und sie wiederherstellen können, bevor Sie Ihre Arbeitsdateien neu ordnen.

![Ablauf zur Prüfung konvertierter Mediendateien](/blog-assets/de/test-converted-media-before-replacing-original/workflow-diagram.svg)

## Ein kurzes Prüfprotokoll hilft bei der Fehlersuche

Ein hypothetisches Beispiel, kein App- oder Gerätetest: Ein exportiertes Interview beginnt klar verständlich, aber der letzte Satz fehlt. Notieren Sie die Namen von Quell- und Ausgabedatei, die ungefähre Position und ob dieselbe Stelle in der Quelle abgespielt wird. Behalten Sie beide Dateien während der Untersuchung. „In dieser Ausgabedatei fehlt der letzte Satz“ hilft mehr als „Die Konvertierungsqualität ist schlecht“.

| Beobachtung | Nächste Prüfung |
| --- | --- |
| Die Ausgabedatei endet zu früh | Das Ende der Quelle vergleichen und dann prüfen, ob der neueste Export geöffnet wurde |
| Das Video hat keinen hörbaren Ton | Quellton, Audiospuren der Ausgabe, Stummschaltung des Players und ausgewählte Spur prüfen |
| Ton und Bild laufen auseinander | Ein frühes und ein spätes Ereignis in Quelle und Ziel vergleichen |
| Tags oder Coverbilder fehlen | Die Felder der Ausgabedatei unabhängig von der Anzeige im Player untersuchen |
| Ein Player funktioniert, ein anderer nicht | Das Ziel notieren und vor einer erneuten Konvertierung die dort unterstützten Eingaben prüfen |

Ändern Sie jeweils nur eine relevante Einstellung oder die Konvertierungsmethode, sofern Ihr Werkzeug dies erlaubt. Exportieren Sie erneut aus dem Original. Wiederholen Sie anschließend sowohl die fehlgeschlagene Prüfung als auch die grundlegenden Wiedergabetests. Wiederholtes Konvertieren einer verlustbehafteten Ausgabedatei stellt keine verlorenen Details der Quelle wieder her.

## Was eine Prüfsumme belegt und was nicht

Eine Prüfsumme ist ein Wert, der aus den Bytes einer Datei berechnet wird. Werkzeuge wie die [GNU-Dienstprogramme für SHA-2](https://www.gnu.org/s/coreutils/manual/html_node/sha2-utilities.html) berechnen und überprüfen solche Werte. Vergleichen Sie ein gespeichertes Original mit seiner Sicherung oder eine akzeptierte Ausgabedatei mit einer Kopie genau dieser Ausgabe. Verwenden Sie für beide Dateien denselben Algorithmus, etwa SHA-256. Ein geänderter Wert weist dann auf einen Unterschied auf Byte-Ebene hin, der untersucht werden sollte.

Erwarten Sie nicht, dass das Original und eine daraus konvertierte Datei dieselbe Prüfsumme haben. Ihre Bytes unterscheiden sich normalerweise. Eine übereinstimmende Prüfsumme der Sicherung unterstützt die Prüfung der Kopierintegrität. Sie bewertet weder Ton und Bild noch die Vollständigkeit der ausgewählten Inhalte oder die Eignung für ein Ziel.

## ONNELLAB im Einsatz

Wenn Sie eine der festgelegten Formatumwandlungen benötigen, ist [Quivra](/apps/quivra/) ein optionales Konvertierungswerkzeug. Der [Eintrag für iOS](https://apps.apple.com/us/app/quivra-mp3-media-converter/id6759565093) und der [Eintrag für Android](https://play.google.com/store/apps/details?id=com.onnellab.quivra2) nennen WAV und M4A zu MP3, die Audioextraktion von MP4 zu MP3 sowie MOV zu MP4. Das Eingabeformat bestimmt automatisch das Ausgabeformat.

Führen Sie die in diesem Artikel beschriebenen Dateianalysen und Wiedergabetests am Ziel mit geeigneten separaten Werkzeugen durch. Die aufgeführten Formatumwandlungen belegen nicht, dass sämtliche Spuren und Metadatenfelder erhalten bleiben. Prüfen Sie vor der Verwendung der App, ob die jeweilige Umwandlung zu Ihrer Aufgabe passt.

## Weiterführender Leitfaden

- [Ein Medienausgabeformat vor der Konvertierung wählen](https://onnellab.com/blog/de/choose-media-output-format-before-conversion/)

## Quellen

- [FFmpeg: ffprobe-Dokumentation](https://ffmpeg.org/ffprobe.html)
- [GNU Coreutils: Dienstprogramme für SHA-2](https://www.gnu.org/s/coreutils/manual/html_node/sha2-utilities.html)
- [FFmpeg: Stream-Kopie und Transkodierung](https://ffmpeg.org/ffmpeg.html#Streamcopy)

## Fazit

Um eine konvertierte Mediendatei zu prüfen, vergleichen Sie sie mit einer kurzen Anforderungsliste, untersuchen ihre Eigenschaften und spielen sie am vorgesehenen Ziel ab. Halten Sie fest, was geprüft wurde und was ungeprüft bleibt. Eine Kopie zur Weitergabe zu akzeptieren und über die Archivierung des Originals zu entscheiden, sind getrennte Entscheidungen. Behalten Sie das Original, wenn sein Verlust schwer wiegen würde.

## Häufige Fragen

### Reicht es aus, die Datei zu öffnen?

Nein. Das Öffnen prüft weder das Ende noch alle Spuren oder jede einzelne Stelle. Untersuchen Sie die benötigten Eigenschaften und spielen Sie die wichtigen Inhalte ab.

### Muss die Dauer exakt gleich sein?

Nicht immer. Rundungen in der Anzeige und das Verhalten des Formats können kleine Unterschiede verursachen. Untersuchen Sie fehlende Inhalte oder erhebliche Abweichungen, statt sich auf eine allgemein gültige Zeittoleranz zu verlassen.

### Bedeutet eine kleinere Datei eine schlechtere Konvertierung?

Die Größe allein beantwortet diese Frage nicht. Beurteilen Sie die Datei nach ihrem vorgesehenen Einsatz, den benötigten Inhalten und der tatsächlichen Wiedergabe.

### Kann ich das Original nach einer erfolgreichen Stichprobe löschen?

Eine Stichprobe lässt Lücken. Behalten Sie eine wiederherstellbare Sicherung des Originals, besonders bei unersetzlichen Aufnahmen oder Material, das Sie später noch bearbeiten könnten.
