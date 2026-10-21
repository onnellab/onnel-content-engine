---
title: "Créer une convention cohérente pour nommer ses fichiers"
card_title: "Créer une convention cohérente pour nommer ses fichiers"
slug: "design-consistent-file-naming-system"
category: "productivity"
language: "fr"
description: "Définissez des champs clairs, des dates explicites et des règles de numérotation et de révision pour garder des noms de fichiers compréhensibles."
status: "published"
topic_id: "TOPIC-0084"
search_intent: "workflow"
primary_keyword: "convention de nommage des fichiers"
secondary_keywords: "noms de fichiers cohérents | organisation des fichiers | date dans un nom de fichier | numérotation des révisions"
tags: "convention de nommage des fichiers"
short_answer: "Choisissez quelques champs dans un ordre fixe, chacun avec une signification précise. Utilisez un identifiant stable, une date sans ambiguïté et, si nécessaire, des numéros complétés par des zéros. Distinguez révision et validation, documentez un exemple et testez la règle sur des fichiers représentatifs."
related_apps: "Aligna"
canonical_url: "https://onnellab.com/blog/fr/design-consistent-file-naming-system/"
published_at: "2026-10-21T09:00:00+09:00"
updated_at: "2026-10-21T09:00:00+09:00"
related_articles: "Transformer les textes répétitifs en extraits réutilisables => https://onnellab.com/blog/fr/turn-repeated-text-into-reusable-snippets/|Organiser sa musique sur Android pour une écoute hors ligne => https://onnellab.com/blog/fr/organize-local-music-library-offline-android/|Vérifier la table des matières et l’ordre des chapitres d’un EPUB => https://onnellab.com/blog/fr/check-epub-table-of-contents-and-reading-order/|Tester un fichier multimédia converti avant de remplacer l’original => https://onnellab.com/blog/fr/test-converted-media-before-replacing-original/"
---

# Créer une convention cohérente pour nommer ses fichiers

## Question

Comment créer une convention de nommage des fichiers qui reste utile au quotidien ?

## Réponse courte

Choisissez quelques champs dans un ordre fixe, chacun avec une signification précise. Utilisez un identifiant stable, une date sans ambiguïté et, si nécessaire, des numéros complétés par des zéros. Distinguez révision et validation, documentez un exemple et testez la règle sur des fichiers représentatifs.

## Définir une convention simple

Une convention de nommage est une règle commune pour construire les noms de fichiers. Un champ est une partie du nom qui remplit une fonction : identifier le projet, préciser une date ou indiquer une révision. Chaque champ doit rester compréhensible hors de son contexte d’origine.

Voici un exemple éditorial, à réaliser manuellement : `atlas_2026-10-05_notes_003_v02.txt`. Il ne décrit pas une fonction d’application. Atlas est un projet fictif.

| Champ | Signification dans cet exemple |
| --- | --- |
| `atlas` | Identifiant stable du projet Atlas |
| `2026-10-05` | Date de la réunion : 5 octobre 2026 |
| `notes` | Type de document : notes |
| `003` | Élément 003 parmi les notes de cette réunion |
| `v02` | Révision enregistrée 02 |
| `.txt` | Extension du fichier texte |

## Méthode recommandée

1. **Choisir le principal critère de recherche.** Placez la date en premier pour une recherche chronologique, ou le projet en premier si c’est votre point d’entrée habituel. Dans un tri textuel, le projet en tête classe les dates à l’intérieur de chaque projet. Il ne crée pas un classement chronologique global.

2. **Préciser ce que représente la date.** Adoptez `YYYY-MM-DD`, soit année-mois-jour, avec deux chiffres pour le mois et le jour. Indiquez s’il s’agit de la date de l’événement, de la capture ou de l’émission. Si elle manque, omettez le champ ou utilisez un marqueur documenté. Ne remplacez pas une date inconnue par celle d’aujourd’hui.

3. **Conserver une identité stable.** Préférez un identifiant court de projet ou de document. Évitez le nom d’un responsable temporaire et les mentions comme « urgent », qui deviennent vite obsolètes. Limitez les informations personnelles ou confidentielles : les noms peuvent apparaître dans des pièces jointes, des liens et des notifications, au-delà du dossier d’origine.

4. **Délimiter la numérotation.** Décidez si la séquence concerne un projet, une réunion ou un lot. Adaptez le nombre de chiffres au volume prévu. `001`, `002` et `010` gardent leur ordre numérique dans un tri textuel simple. Certaines applications utilisent déjà un tri naturel. Si la capacité prévue est dépassée, ajustez la séquence concernée de manière cohérente et planifiée.

5. **Séparer révision et validation.** Définissez quand `v01` devient `v02`, par exemple à chaque nouvelle révision enregistrée devant être distinguée. Une révision supplémentaire ne prouve aucune validation. Consignez l’approbation dans le processus prévu. Les noms « final-final » ne démontrent pas davantage qu’une personne a relu ou approuvé le contenu.

6. **Écrire la règle et tester cinq fichiers.** Documentez l’ordre des champs, les champs facultatifs, les séparateurs et les exceptions. Choisissez cinq cas représentatifs, dont une date inconnue et une nouvelle révision. Vérifiez la recherche, le tri et l’affichage dans les applications réellement utilisées, ainsi que dans le système destinataire.

## Les quatre éléments à retenir

![Quatre éléments d’un nom de fichier : identité stable, date au sens défini, séquence complétée par des zéros et révision indiquée.](/blog-assets/fr/design-consistent-file-naming-system/workflow-diagram.svg)

## Garder une règle facile à appliquer

Utilisez les séparateurs de façon constante. Les minuscules sont un choix éditorial, pas une obligation universelle. Vérifiez les caractères autorisés et les limites de longueur des systèmes destinataires. Conservez l’extension : modifier celle-ci ne convertit pas le contenu du fichier.

Une convention ne remplace ni l’historique des versions, ni les droits d’accès, ni les dossiers. Si elle change, ne renommez pas automatiquement toutes les archives. Examinez d’abord les liens, références et habitudes de travail qui dépendent des noms existants.

## Utiliser ONNELLAB

[Aligna](/apps/aligna/) est un outil de renommage par lots disponible sur iOS et Android. Ses fiches de boutique décrivent huit modèles prédéfinis fixes, un aperçu et une gestion des conflits. Choisissez uniquement un modèle adapté au besoin. Examinez le modèle sélectionné et l’aperçu avant d’appliquer les changements. Ces informations ne confirment ni un générateur de règles personnalisées ni la combinaison exacte de champs présentée ici.

## Guides associés

- [Renommer des fichiers avec précaution grâce à l’aperçu](https://onnellab.com/blog/fr/rename-files-safely-preview-workflow/)
- [Organiser les téléchargements avec quelques dossiers](https://onnellab.com/blog/fr/organize-downloads-small-folder-system/)

## Références

Les caractéristiques du produit sont décrites sur l’[App Store](https://apps.apple.com/us/app/aligna-file-renamer/id6783642658) et [Google Play](https://play.google.com/store/apps/details?id=com.onnellab.aligna). Les conseils de nommage sont des recommandations éditoriales, sans résultat mesuré de performance.

## Conclusion

Quelques champs bien définis suffisent pour commencer. Écrivez la règle, vérifiez les exceptions courantes et testez-la avant de l’appliquer à un ensemble important de fichiers.

## Questions fréquentes

### Faut-il toujours inclure une date ?

Non. Ajoutez-la si elle aide à retrouver ou à comprendre le fichier, en précisant ce qu’elle représente.

### Vaut-il mieux commencer par la date ou le projet ?

Choisissez votre principal critère de recherche. La date favorise l’ordre chronologique ; le projet regroupe d’abord les fichiers par projet.

### `v03` signifie-t-il que le fichier est validé ?

Non. Ce champ indique une révision selon votre convention. La validation demande une trace distincte.

### Aligna peut-il reproduire exactement cet exemple ?

Les informations citées ne l’établissent pas. L’application propose des modèles fixes ; vérifiez si l’un d’eux correspond à votre besoin.
