---
title: "Dates d’enregistrement et de sortie dans les métadonnées musicales"
description: "Distinguez la date d’enregistrement, celle de la première sortie et celle de votre édition. Conservez les sources et ne devinez pas les dates inconnues."
language: "fr"
slug: "distinguish-recording-date-from-release-date"
category: "music"
short_answer: "La date d’enregistrement indique quand l’interprétation a été enregistrée ; la date de sortie indique quand l’enregistrement a été publié. Identifiez l’édition précise, comparez les informations officielles et le livret, puis associez chaque date à sa source. Ne déduisez pas l’année d’enregistrement de l’année de sortie."
primary_keyword: "date d’enregistrement et date de sortie"
secondary_keywords: ""
card_title: "Dates d’enregistrement et de sortie dans les métadonnées musicales"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "date d’enregistrement et date de sortie"
canonical_url: "https://onnellab.com/blog/fr/distinguish-recording-date-from-release-date/"
---

# Dates d’enregistrement et de sortie dans les métadonnées musicales

La date d’enregistrement indique quand l’interprétation a été enregistrée ; la date de sortie indique quand l’enregistrement a été publié. Identifiez l’édition précise, comparez les informations officielles et le livret, puis associez chaque date à sa source. Ne déduisez pas l’année d’enregistrement de l’année de sortie.

## Commencez par une édition précise

Un dossier d’album peut contenir plusieurs années plausibles. Avant toute modification, identifiez votre édition à l’aide du format, du label, de la référence catalogue et de la liste des pistes. Une page consacrée à une autre édition ne décrit pas forcément vos fichiers.

La [documentation de MusicBrainz sur les éditions](https://musicbrainz.org/doc/Release) traite la date de parution d’une édition comme une information de sortie. Pour étudier votre exemplaire, consultez les informations officielles de l’artiste ou du label et le livret correspondant.

## Séparez trois questions

| Question | Preuve à rechercher | Hypothèse à éviter |
| --- | --- | --- |
| Quand cette interprétation a-t-elle été enregistrée ? | Date de séance explicite dans le livret ou les notes officielles | L’année de sortie serait celle de l’enregistrement |
| Quand cet enregistrement est-il sorti pour la première fois ? | Information officielle identifiant la première publication | La date d’une réédition serait la date d’origine |
| Quand cette édition est-elle sortie ? | Informations sur l’édition et le territoire correspondants | Toutes les éditions auraient la même date |

Une année de remastérisation, une mention de droits d’auteur ou la date de modification d’un fichier ne suffit pas à répondre à ces trois questions.

## Cinq étapes avant de modifier une date

1. Conservez une sauvegarde et examinez d’abord une piste. Notez les dates existantes sans les écraser.
2. Vérifiez l’édition. Relevez le label, la référence catalogue, le format et le territoire, lorsqu’ils sont connus.
3. Lisez le livret et la page officielle de sortie. Notez ce que chaque source dit de la date, avec le numéro de page ou l’URL.
4. Gardez uniquement la précision étayée par les sources. Si seule l’année est connue, n’inventez ni mois ni jour. Consignez les contradictions dans une note distincte.
5. Vérifiez la définition des champs de l’éditeur et l’affichage du lecteur avant d’enregistrer une copie de test. Un champ « Année » ne conserve pas nécessairement toutes ces distinctions. Rouvrez la copie enregistrée et examinez-la avant d’étendre les modifications.

La [spécification ID3v2.4](https://id3.org/id3v2.4.0-frames) distingue les horodatages d’enregistrement, de première sortie et de sortie. Cela ne prouve pas qu’un éditeur expose tous les champs ni qu’un lecteur les affiche comme prévu. Ce guide ne prescrit pas de correspondance avec des champs de tags précis.

## Un exemple fictif

Supposons que le livret indique explicitement un enregistrement en 1998, que les notes officielles identifient une première sortie en 2000 et que votre édition soit sortie en 2024. Conservez ces trois faits séparément avec leurs sources. L’édition de 2024 ne transforme pas l’interprétation en enregistrement de 2024.

Si la date d’enregistrement manque, écrivez « inconnue » dans vos notes de recherche. Ne copiez pas 2000 ou 2024 dans le champ d’enregistrement pour combler le vide.

## Questions fréquentes

### Puis-je modifier toutes les pistes ensemble ?
Vérifiez d’abord que les preuves concernent toutes les pistes. Un album peut réunir plusieurs séances ou des titres bonus.

### Quelle date mon lecteur doit-il afficher ?
Cela dépend de votre objectif de classement et du lecteur. Conservez d’abord les différentes dates avec leurs sources, puis vérifiez leur affichage dans le lecteur à partir d’une copie. Ne perdez pas les sources pour obtenir un affichage plus uniforme.

### Que faire si deux sources se contredisent ?
Gardez les deux références et décrivez le conflit. Vérifiez qu’elles concernent la même édition et le même territoire. Laissez la valeur en suspens plutôt que de retenir l’année la plus pratique.

## Prochaine étape

Choisissez un album et préparez une note de sources avant de modifier ses tags. Pour une autre question, consultez le guide pour [distinguer les fichiers en double des enregistrements différents](/blog/fr/distinguish-duplicate-music-files-from-different-recordings/). Les dates seules ne prouvent pas que deux fichiers contiennent le même enregistrement.
