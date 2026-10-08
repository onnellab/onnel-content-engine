---
title: "Vérifier la table des matières et l’ordre des chapitres d’un EPUB"
card_title: "Vérifier la table des matières et l’ordre des chapitres d’un EPUB"
slug: "check-epub-table-of-contents-and-reading-order"
category: "reading"
language: "fr"
description: "Comparez l’EPUB exporté à la liste prévue et vérifiez séparément les liens de la table des matières et l’ordre de lecture."
status: "review"
topic_id: "TOPIC-0060"
search_intent: "troubleshoot"
primary_keyword: "vérifier la table des matières d’un EPUB"
secondary_keywords: "ordre des chapitres EPUB|liens de navigation EPUB|chapitres manquants EPUB|Papira"
related_apps: "Papira"
tags: "EPUB|table des matières|ordre de lecture|navigation|vérification ebook"
short_answer: "Listez les chapitres attendus, ouvrez l’EPUB dans une autre application de lecture et testez chaque lien. Contrôlez les transitions, notez les écarts, corrigez la source ou les réglages, puis régénérez et vérifiez le fichier."
canonical_url: "https://onnellab.com/blog/fr/check-epub-table-of-contents-and-reading-order/"
image_specs: "Chapitres attendus|Liens des chapitres|Ordre de lecture|Corriger et régénérer"
---

# Vérifier la table des matières et l’ordre des chapitres d’un EPUB

L’EPUB s’ouvre et sa table des matières semble correcte. Chaque entrée atteint-elle le chapitre prévu ? La lecture continue suit-elle le même ordre ? Pour vérifier la table des matières d’un EPUB, comparez le fichier exporté à une liste tirée du manuscrit, puis testez ces deux parcours.

Ce guide commence après l’exportation. Il propose une inspection reproductible, sans reprendre la préparation du manuscrit, de la couverture ou de l’encodage.

## Question

Comment vérifier que les liens de la table des matières et l’ordre des chapitres correspondent au manuscrit ?

## Réponse courte

Listez les chapitres attendus, ouvrez l’EPUB dans une autre application de lecture et testez chaque lien. Contrôlez les transitions, notez les écarts, corrigez la source ou les réglages, puis régénérez et vérifiez le fichier. Gardez le manuscrit original et l’export précédent jusqu’à vérification du nouveau.

## Distinguer trois éléments

Le **libellé** est le texte sélectionné dans la table des matières. La **destination** est l’emplacement ouvert par le lien. L’**ordre de lecture** est la séquence rencontrée en continuant sans sélectionner une autre entrée.

EPUB 3 représente séparément navigation et ordre de lecture : le document de navigation fournit la table des matières ; le spine du paquet ordonne les documents de contenu. Leur ordre interne compte aussi. [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) décrit cette structure. Ces vérifications ne nécessitent aucune modification des fichiers internes.

| Vérification | Ce qu’elle établit | Ce qui reste à vérifier |
| --- | --- | --- |
| Comparer table et liste | Entrées attendues, libellés compréhensibles | Destinations |
| Ouvrir chaque lien | Titre et début du chapitre atteint | Suite en lecture continue |
| Franchir les transitions | Séquence conforme au projet | Tous les liens |
| Exécuter EPUBCheck | Respect des règles EPUB contrôlées | Intention éditoriale |

Le menu du lecteur et une page de sommaire dans le livre peuvent être distincts. Inspectez le menu et, si elle existe, les liens de cette page.

## Préparer la liste attendue

Prenez le manuscrit comme référence. Listez les chapitres dans l’ordre voulu, avec les éléments avant et après le texte principal, comme préface et postface. Décidez lesquels doivent figurer dans la table des matières ; chaque paragraphe ne nécessite pas une entrée.

Pour des titres répétés, ajoutez à votre fiche privée quelques mots du premier paragraphe. Vous distinguerez ainsi deux chapitres nommés « Notes ». Utilisez titres et passages reconnaissables plutôt que les numéros de page du lecteur, variables selon la mise en page.

Notez nom du fichier exporté, révision du manuscrit, version du convertisseur, nom et version du lecteur. Après régénération, assurez-vous d’ouvrir le nouveau fichier, pas une copie déjà importée. Sauvegardez les annotations avant de supprimer un ancien exemplaire de la bibliothèque.

## Tenir une fiche de contrôle

Cet exemple pédagogique est fictif. Il ne décrit ni défaut constaté ni test sur appareil. L’ordre prévu est « Arrivée », « Le sentier », « Retour ». Reprenez les colonnes avec vos propres observations.

| Titre attendu | Libellé affiché | Destination réelle | Chapitre suivant | Résultat | Contrôle de la source ou des réglages |
| --- | --- | --- | --- | --- | --- |
| 1 Arrivée | 1 Arrivée | 1 Arrivée | 2 Le sentier | Conforme | Aucun |
| 2 Le sentier | 2 Le sentier | 3 Retour | Non vérifié | Mauvaise destination | Vérifier la séparation des chapitres et les règles d’export documentées |
| 3 Retour | 3 Retour | 3 Retour | Fin du texte principal | Conforme sur ce point | Vérifier séparément la postface prévue |

La deuxième ligne établit seulement le résultat hypothétique du lien. Elle ne prouve pas l’absence du chapitre 2. Cherchez son début ou continuez depuis le chapitre 1 avant de distinguer contenu manquant et lien incorrect.

## Méthode recommandée

Effectuez les contrôles dans une application de lecture EPUB distincte.

1. **Ouvrez le bon export.** Gardez les noms du manuscrit et de l’EPUB dans vos notes. Choisissez un lecteur compatible ; vérifiez importation et synchronisation avant d’ouvrir un texte privé.
2. **Comparez toute la table.** Repérez sections absentes, entrées inattendues, doublons et ordre différent. Dépliez les groupes repliés si le lecteur en propose.
3. **Testez chaque lien.** Comparez titre et première phrase reconnaissable avec votre référence. Atteindre un emplacement quelconque ne suffit pas. Notez la destination réelle.
4. **Testez séparément la lecture continue.** Commencez avant le premier chapitre principal et franchissez sa fin sans utiliser le menu. Vérifiez pages liminaires et transitions au début, au milieu et à la fin ; vérifiez toutes les autres transitions avant de considérer le livre entièrement vérifié.
5. **Contrôlez la fin.** Le dernier chapitre doit atteindre sa conclusion prévue. Postface et annexes doivent rester accessibles. Distinguez ces compléments de la séquence principale.
6. **Essayez un autre lecteur si la diffusion l’exige.** Utilisez le même export. En cas de différence, notez versions du fichier et des lecteurs. Un écart appelle une enquête, sans désigner à lui seul le responsable.

![Parcours illustratif : liste attendue, liens, ordre de lecture, puis correction de la source avant régénération.](/blog-assets/fr/check-epub-table-of-contents-and-reading-order/workflow-diagram.svg "Contrôler séparément les liens et la séquence")

Ce schéma propose une méthode ; ce n’est ni une capture d’écran ni une preuve de tests réalisés.

## Diagnostiquer avant de corriger

| Symptôme | Preuve à recueillir | Étape suivante |
| --- | --- | --- |
| Chapitre absent du menu | Son début existe-t-il en lecture continue ? | Si oui : reconnaissance des titres et périmètre prévu ; sinon : intégralité source et limites d’export |
| Bon libellé, mauvais chapitre | Noter titre et texte ouverts | Comparer les limites des chapitres du manuscrit et les règles documentées de reconnaissance des titres ; reproduire sur un court exemple |
| Deux libellés identiques | Comparer destinations et titres originaux | Déterminer si la répétition est voulue avant de renommer ou supprimer un marqueur |
| Liens corrects, chapitres sautés ou inversés | Noter transition réelle et chapitre attendu | Vérifier ordre source et options disponibles ; conserver le résultat si la source est correcte |
| Un seul lecteur concerné | Confirmer une révision exportée identique | Répéter la transition exacte et comparer les versions avant d’attribuer la cause |

Modifiez un seul élément pertinent à la fois. Corrigez le manuscrit de travail ou un réglage documenté, exportez sous un nom distinct et retestez entrée concernée et transitions voisines. Reprenez ensuite tous les liens : une modification structurelle peut affecter plusieurs destinations.

Si une source correcte produit encore l’écart, gardez l’original et préparez un court exemple avec un texte personnel ou partageable. Indiquez au support destinations attendues et observées. N’envoyez pas un manuscrit inédit entier pour illustrer un seul défaut de navigation.

## Associer validation et lecture

[EPUBCheck](https://www.w3.org/publishing/epubcheck/) vérifie les publications selon les spécifications EPUB. Examinez erreurs et avertissements du paquet, puis validez le fichier régénéré. Un rapport sans erreur ne détermine pas si le « Chapitre 2 » contient le texte voulu.

Une ouverture réussie dans un lecteur ne prouve ni conformité complète, ni accessibilité, ni compatibilité universelle. Séparez rapport, observations et lecteurs ou sections non testés. Pour un texte confidentiel, validez localement ou examinez le traitement des données du service avant tout téléversement.

## La place d’ONNELLAB

Pour recréer un EPUB à partir d’un TXT terminé, Papira est une option proposée par ONNELLAB. Ses fiches officielles décrivent un assemblage hors ligne avec couverture, informations du livre et table des matières. Modifiez le manuscrit ailleurs et examinez l’export dans un autre lecteur : Papira ne propose ni édition du corps du texte ni lecteur EPUB.

La reconnaissance des titres dépend de la plateforme et de la version documentées. Les langues de l’interface ne prouvent pas quels motifs sont reconnus, ni un comportement identique sous iOS et Android. Cette méthode ne prescrit donc aucune règle automatique universelle. Consultez les instructions de votre version et comparez le résultat à votre liste.

Consultez les fiches officielles de [Papira sur l’App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) ou de [Papira sur Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira) selon votre plateforme et région. La méthode convient aussi aux autres exportateurs EPUB.

## Guide associé

Si l’écart provient de la préparation, consultez [Préparer un manuscrit TXT pour la conversion EPUB](/blog/fr/prepare-txt-manuscript-for-epub/). Ce guide concerne l’amont ; la présente fiche intervient après exportation.

## Références

- [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) : navigation et spine définissant l’ordre par défaut.
- [W3C EPUBCheck](https://www.w3.org/publishing/epubcheck/) : vérificateur de conformité EPUB.
- [Papira sur l’App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) et [Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira) : périmètre et indications propres aux plateformes.

## Conclusion

Comparez intention et observations : liste attendue, chaque lien, puis lecture continue. En cas d’écart, conservez les preuves, corrigez source ou réglages pris en charge et vérifiez le nouveau fichier avant de le partager.

## Questions fréquentes

### Un titre visible prouve-t-il que son lien est correct ?

Non. Ouvrez l’entrée et comparez titre et début du texte atteint. Libellé et destination se vérifient séparément.

### Un chapitre absent du menu manque-t-il aussi dans le livre ?

Pas nécessairement. Il peut exister en lecture continue. Cherchez son début et vérifiez le périmètre voulu de la table avant de conclure.

### Pourquoi les liens fonctionnent-ils malgré un ordre incorrect ?

Sélectionner un lien et continuer la lecture empruntent des parcours différents. Notez le chapitre suivant réel, puis comparez avec manuscrit et réglages d’exportation.

### Réussir EPUBCheck suffit-il pour diffuser le livre ?

C’est un contrôle utile. Vérifiez encore texte, navigation, séquence et exigences du public ou du distributeur. Ce résultat ne vaut pas validation éditoriale ou d’accessibilité.

### Faut-il corriger directement l’EPUB exporté ?

Préférez la source ou les réglages documentés pour retrouver la correction au prochain export. Si votre chaîne éditoriale exige une modification du paquet, documentez une étape reproductible et évitez deux versions contradictoires.

### Peut-on faire ces contrôles de lecture dans Papira ?

Non. Papira assemble des TXT terminés en EPUB ; ce n’est pas un lecteur. Ouvrez l’export dans une autre application et corrigez le manuscrit dans un éditeur de texte.
