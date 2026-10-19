---
title: "Comment numéroter les pistes d’un album MP3 multidisque"
card_title: "Comment numéroter les pistes d’un album MP3 multidisque"
slug: "number-tracks-multi-disc-mp3-album"
category: "music"
language: "fr"
description: "Séparez numéro de piste et numéro de disque dans un album MP3. Vérifiez TRCK, TPOS et les totaux, conservez les originaux et testez un échantillon dans la bibliothèque."
status: "published"
topic_id: "TOPIC-0029"
search_intent: "workflow"
primary_keyword: "numéroter les pistes d’un album MP3 multidisque"
secondary_keywords: "numéro de piste MP3|étiquettes de numéro de disque|ID3 TRCK TPOS|TagWeaver"
related_apps: "TagWeaver"
tags: "album MP3 multidisque|numéro de piste MP3|numéro de disque|ID3 TRCK TPOS"
short_answer: "Inscrivez la position du morceau sur son disque dans le champ piste, et celle du disque dans le champ disque. Ajoutez uniquement des totaux vérifiés, conservez les originaux et contrôlez quelques copies enregistrées dans l’éditeur et la bibliothèque cible."
canonical_url: "https://onnellab.com/blog/fr/number-tracks-multi-disc-mp3-album/"
published_at: "2026-09-04T09:00:00+09:00"
updated_at: "2026-09-04T09:00:00+09:00"
image_specs: "Numérotation multidisque avec sauvegarde préalable|Correspondance des champs TRCK et TPOS|Contrôle dans la bibliothèque cible"
related_articles: "Nettoyer les métadonnées MP3 avant d’organiser sa musique => https://onnellab.com/blog/fr/clean-up-mp3-metadata-before-organizing-music/|TXT ou EPUB pour lire de longs textes ? => https://onnellab.com/blog/fr/txt-vs-epub-for-long-reading/|Lire de gros fichiers TXT sans ralentissements inutiles => https://onnellab.com/blog/fr/read-large-txt-files-without-lag/|Pourquoi les gros fichiers texte sont parfois lents à ouvrir => https://onnellab.com/blog/fr/large-text-file-slow-to-open/|Convertir des fichiers multimédias localement et en toute confidentialité => https://onnellab.com/blog/fr/convert-local-media-files-privately/|Découper un enregistrement audio sans utiliser un éditeur complet => https://onnellab.com/blog/fr/trim-audio-recordings-without-full-editor/"
---

# Comment numéroter les pistes d’un album MP3 multidisque

Un coffret possède deux ordres : celui des morceaux sur chaque disque et celui des disques dans l’ensemble. Enregistrez-les séparément, laissez les incertitudes visibles et testez quelques copies avant de modifier tout l’album.

## Question

Comment numéroter les pistes d’un album MP3 multidisque ?

## Réponse courte

Le champ piste contient la position du morceau sur son disque ; le champ disque contient la position du disque dans le coffret. Le quatrième morceau du deuxième disque d’un ensemble de trois peut porter piste `4`, disque `2`. Utilisez `4/11` et `2/3` uniquement si les totaux sont vérifiés. Travaillez sur des copies, harmonisez album et artiste de l’album, puis contrôlez un échantillon enregistré et importé.

## Distinguer piste et disque

La **position de piste** est le rang du morceau sur son disque. La trame `TRCK` d’ID3v2 porte cette valeur. ID3v2.4 autorise une position numérique suivie, facultativement, d’une barre oblique et d’un total, comme `4/11`. La valeur `4` seule suffit aussi.

La **position de disque** désigne le rang d’une partie dans l’ensemble. `TPOS` suit le même principe : `2/3` signifie deuxième partie sur trois. Pour un album, cette partie correspond généralement à un disque physique ou logique, sans imposer son libellé dans toutes les applications.

`TRCK=4/11` et `TPOS=2/3` conservent « quatrième piste du deuxième disque ». Une simple numérotation continue, comme piste 15, ne conserve pas le début du deuxième disque. Elle peut servir de convention personnelle, à distinguer de la numérotation originale par disque.

## Choisir une convention avant l’édition

Partez d’une liste fiable identifiant l’édition exacte : livret, catalogue officiel de l’éditeur ou du label. Éditions de luxe, régionales, rééditions et disques bonus peuvent différer. Un titre semblable ne suffit pas.

Notez au préalable :

- le nom exact de l’album pour toutes les pistes ;
- l’artiste de l’album commun, si pertinent ;
- les disques réellement présents et les éventuels manquants ;
- le nombre de pistes par disque et l’emplacement des bonus ;
- les totaux confirmés ;
- la numérotation imprimée par disque ou une convention personnelle documentée.

Si la source distingue les disques, recommencez à la piste 1 sur chacun et différenciez-les avec `TPOS`. N’inventez pas de disque manquant ni de total pour remplir les champs. Une position connue vaut mieux qu’un total faux.

## Préparer une table de correspondance

Pour un album double, cet échantillon vérifie les limites :

| Fichier | Piste (`TRCK`) | Disque (`TPOS`) | À vérifier |
| --- | --- | --- | --- |
| Premier morceau du disque 1 | `1/10` | `1/2` | Bonne édition, dix pistes |
| Dernier morceau du disque 1 | `10/10` | `1/2` | Aucun numéro absent ou doublonné |
| Premier morceau du disque 2 | `1/12` | `2/2` | Reprise volontaire à 1 |
| Dernier morceau du disque 2 | `12/12` | `2/2` | Totaux conformes à la source |

Sans totaux certains, utilisez les pistes `1`, `10`, `1`, `12` et les disques `1` ou `2`. N’inscrivez pas « deuxième disque » dans un champ numérique ; gardez les explications incertaines dans une note séparée.

## Protéger l’original et sélectionner par disque

Gardez une copie intacte hors du dossier de travail. Une sauvegarde écrasée avec les fichiers modifiés n’est pas indépendante. Une liste de fichiers ou des sommes de contrôle peuvent faciliter la comparaison.

Regroupez les copies selon leur véritable disque. Le nom de dossier `CD2` est un indice : comparez titres, durées et étiquettes à la liste fiable. Excluez les fichiers incertains de la sélection.

Partagez uniquement les valeurs communes : données d’album dans tout le coffret, position du disque au sein du même disque. Titres et positions de piste restent individuels ; vérifiez aussi les valeurs attribuées par un outil de séquence.

## Méthode recommandée

1. **Préservez la source.** Copiez l’album complet pour travailler et laissez l’original intact. Vérifiez la présence de tous les disques et fichiers attendus.
2. **Identifiez l’édition.** Comparez titres, durées, bonus et séparations imprimées à une liste fiable. Signalez les fichiers sans correspondance sans les forcer dans la séquence.
3. **Choisissez la numérotation.** Pour reproduire l’édition, privilégiez les positions par disque et un champ disque séparé. Documentez toute séquence personnelle continue.
4. **Établissez la correspondance.** Listez titre, position `TRCK`, total facultatif de pistes, position `TPOS` et total facultatif de disques. Cherchez doublons et lacunes par disque.
5. **Modifiez un échantillon.** Incluez première et dernière piste d’un disque, puis première du suivant : les erreurs de transition et de reprise apparaîtront.
6. **Enregistrez et rouvrez.** Fermez l’éditeur ou désélectionnez les fichiers, puis rouvrez-les et vérifiez les valeurs enregistrées. Une valeur visible avant enregistrement ne prouve pas son écriture.
7. **Testez la bibliothèque cible.** Importez seulement l’échantillon. Contrôlez regroupement, limites, ordre et première transition entre disques. Le résultat concerne cette application et cette version.
8. **Étendez disque par disque.** Appliquez seulement la table vérifiée. Rouvrez la première, une piste intermédiaire et la dernière de chaque disque terminé, puis comparez leurs valeurs à la table.
9. **Gardez la sauvegarde jusqu’au second contrôle.** Revérifiez l’album complet après l’actualisation ou la réimportation prévue par la documentation de la bibliothèque.

![Schéma de numérotation multidisque](/blog-assets/fr/number-tracks-multi-disc-mp3-album/workflow-diagram.svg "Sauvegarder, attribuer les positions et contrôler les transitions entre disques")

## Vérifier au-delà de l’ordre affiché

Une liste correcte peut cacher de mauvaises étiquettes. La bibliothèque peut conserver les données importées, utiliser un cache ancien ou ses propres règles d’affichage. Rouvrez d’abord les fichiers dans un lecteur de métadonnées ou un éditeur pour vérifier `TRCK` et `TPOS`. Actualisez ou réimportez ensuite le seul échantillon selon la documentation du logiciel cible.

Contrôlez le début et la fin de chaque disque, les transitions et les disques bonus dont le nombre de pistes diffère. Repérez positions absentes ou répétées, totaux contradictoires et même numéro de disque appliqué à tout l’album. Une lecture réussie ne valide pas la numérotation : les étiquettes décrivent l’audio, sans réparer ses dommages, établir la véracité des données ni garantir une lecture sans intervalle.

## Erreurs courantes et corrections prudentes

| Symptôme | Cause à examiner | Réponse sûre |
| --- | --- | --- |
| Disque 2 avant le disque 1 | Positions de disque absentes ou incohérentes | Rouvrir et comparer `TPOS` à la table |
| Pistes des disques entremêlées | Valeurs absentes, incohérentes ou ignorées | Vérifier les étiquettes, puis la documentation et le comportement cible |
| Numéros répétés sur un disque | Même valeur de piste appliquée en lot | Restaurer les copies ou réappliquer les positions individuelles |
| Album divisé en groupes | Album ou artiste de l’album différents | Comparer le texte exact avant de renuméroter |
| Total faux sur certains fichiers | Éditions mélangées ou sélection partielle | Confirmer l’édition ; harmoniser seulement les totaux connus |
| Désaccord entre éditeur et lecteur | Cache ou prise en charge différente | Vérifier le fichier, puis actualiser uniquement le test |

## Utiliser ONNELLAB

[TagWeaver](/apps/tagweaver/) est un éditeur local de métadonnées MP3 permettant d’appliquer une correspondance vérifiée aux fichiers sélectionnés. Les informations produit maintenues décrivent l’édition individuelle gratuite et l’édition par lot incluse dans l’achat unique Pro facultatif. Les fiches officielles mentionnent piste et disque parmi les champs modifiables ; consultez les détails de votre plateforme.

L’application ne détermine pas l’édition correcte ni des positions fiables à votre place. Fixez d’abord liste et règles, laissez la sauvegarde hors sélection, enregistrez explicitement et vérifiez quelques résultats. Selon les notes de la version 2.5.1 sur l’App Store, l’enregistrement sous iOS met à jour l’original sélectionné si son emplacement autorise l’écriture ; sinon, TagWeaver demande où enregistrer une copie. Créez une sauvegarde séparée avant toute modification et vérifiez l’emplacement du fichier enregistré.

## Références

- [ID3.org : trames ID3v2.4.0](https://id3.org/id3v2.4.0-frames) : `TRCK`, `TPOS` et totaux facultatifs après la barre oblique.
- [ID3.org : structure ID3v2.4.0](https://id3.org/id3v2.4.0-structure) : structure des étiquettes et trames de métadonnées.
- [ID3.org : spécification ID3v2.3.0](https://id3.org/id3v2.3.0) : définitions antérieures pour les fichiers et outils utilisant cette version.
- [TagWeaver sur l’App Store](https://apps.apple.com/app/id6759609875) : fiche officielle iOS.
- [TagWeaver sur Google Play](https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2) : fiche officielle Android.

## Conclusion

Traitez piste et disque comme deux faits distincts. Vérifiez l’édition, préparez chaque valeur, préservez les originaux et testez les transitions. Totaux, zéros initiaux, noms de fichiers et présentation sont secondaires. Des valeurs `TRCK` et `TPOS` exactes et une méthode réversible forment la base fiable.

## Questions fréquentes

### Le deuxième disque doit-il recommencer à la piste 1 ?

Généralement oui, pour conserver des séquences imprimées distinctes. Placez la piste dans `TRCK`, le disque dans `TPOS`. Documentez toute séquence personnelle continue.

### Les totaux `4/11` et `2/3` sont-ils obligatoires ?

Non. Ajoutez-les uniquement après vérification de l’édition et des quantités complètes. Une position juste est préférable à un total faux.

### Tous les lecteurs classeront-ils correctement l’album ?

Aucun comportement universel n’est garanti. Chaque logiciel choisit comment lire, regrouper, mettre en cache et afficher les données. Testez une copie représentative dans votre destination.

### Les noms de fichiers peuvent-ils remplacer les étiquettes ?

Ils facilitent l’inspection des dossiers, mais ne prouvent pas l’écriture de `TRCK` et `TPOS`. Gardez les renommages séparés et réversibles.

### Ces modifications changent-elles la qualité sonore ?

Les positions sont des métadonnées, pas des échantillons audio. Cette modification n’améliore ni ne réencode le son en elle-même ; préservez néanmoins les originaux et vérifiez la sortie réelle de l’éditeur.
