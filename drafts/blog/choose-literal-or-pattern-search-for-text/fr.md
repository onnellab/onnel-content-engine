---
title: "Choisir entre recherche littérale et recherche par motif"
description: "Choisissez le mode de recherche, testez la ponctuation sur un texte fictif et vérifiez le périmètre avant de vous fier aux résultats."
language: "fr"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
short_answer: "Utilisez la recherche littérale pour une suite de caractères connue. Choisissez un motif seulement si vous devez trouver plusieurs variantes selon une règle et avez vérifié la syntaxe de l’application. Testez les correspondances et les exclusions sur un texte fictif, puis examinez le document sans rien remplacer."
primary_keyword: "recherche littérale ou par motif"
secondary_keywords: "chercher du texte littéral|recherche par expression régulière|chercher la ponctuation"
card_title: "Choisir entre recherche littérale et recherche par motif"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "recherche littérale ou par motif"
canonical_url: "https://onnellab.com/blog/fr/choose-literal-or-pattern-search-for-text/"
---

# Choisir entre recherche littérale et recherche par motif

La recherche d’un repère contenant un point peut trouver un passage inattendu. Les caractères saisis sont peut-être interprétés comme des instructions plutôt que comme du texte. Avant de compliquer la requête, vérifiez le mode de recherche.

## Question

Quand faut-il chercher du texte littéralement, et quand faut-il utiliser un motif ?

## Réponse courte

Utilisez la recherche littérale pour une suite de caractères connue. Choisissez un motif seulement si vous devez trouver plusieurs variantes selon une règle et avez vérifié la syntaxe de l’application. Testez les correspondances et les exclusions sur un texte fictif, puis examinez le document sans rien remplacer.

## Deux sens possibles pour une requête

La recherche littérale cherche les caractères saisis sans les traiter comme des opérateurs de motif. La recherche par motif interprète certains caractères comme des règles. Une expression régulière est un type de motif ; les caractères génériques des noms de fichiers ne suivent pas nécessairement le même langage.

« Littéral » ne signifie pas forcément ligne entière, mot entier, respect de la casse ou identité des octets de deux fichiers. Ce sont des questions distinctes. Une partie d’une phrase plus longue peut aussi constituer une correspondance littérale.

| Tâche | Point de départ | Vérification nécessaire |
| --- | --- | --- |
| Retrouver le repère `A.7` | Recherche littérale | Ponctuation et casse |
| Trouver plusieurs variantes définies | Mode de motif pris en charge | Syntaxe et résultats indésirables |
| Limiter les fichiers parcourus | Réglages du périmètre | Distinguer filtres de chemins et recherche de contenu |

## Un petit test fictif

Créez une note locale jetable contenant ces trois lignes, sans données privées ni extraits d’un véritable document.

```text
A.7
Ax7
A-7
```

Pour « retrouver le repère `A.7` », seule la première ligne convient. Commencez en mode littéral et examinez les caractères surlignés, pas seulement le nombre de résultats.

Dans la [syntaxe de RE2](https://github.com/google/re2/wiki/Syntax), le point est un caractère générique ; échappé, il représente le point lui-même. Ici, les motifs `A.7` et `A\.7` expriment donc des intentions différentes. Cela ne garantit pas leur prise en charge par votre lecteur. N’ajoutez pas de barre oblique inverse à une requête littérale si vous ne cherchez pas ce caractère.

Réussir ce petit test ne suffit pas à définir une règle complète pour le document. Décidez notamment si une occurrence dans `ZA.70` doit compter. Ajoutez ce cas au test s’il est pertinent.

## Méthode recommandée

1. **Décrivez le but avec des mots.** Cherchez-vous une expression connue ou plusieurs variantes ? Notez un résultat souhaité et un résultat proche à exclure.
2. **Préservez la source.** Utilisez un affichage en lecture seule ou une copie de travail. Séparez le texte de test des observations. N’envoyez pas de contenu privé à un outil de test de motifs en ligne.
3. **Vérifiez le champ utilisé.** Consultez l’aide sur le mode, l’échappement et la syntaxe acceptée. L’[aide Google](https://support.google.com/docs/answer/62754?hl=en) décrit son option d’expressions régulières et l’échappement par barre oblique inverse. Ces indications concernent ce produit.
4. **Testez sans remplacer.** Vérifiez chaque correspondance attendue et chaque exclusion sur l’exemple fictif. Changez une seule option à la fois. Si le comportement reste obscur, revenez à une recherche littérale courte et distinctive.
5. **Vérifiez et notez le périmètre.** Confirmez fichier, version, sélection et filtres. Lisez le contexte et consignez requête, mode et options utiles hors du document original.

## Le périmètre change les résultats

La [documentation de VS Code](https://code.visualstudio.com/docs/editing/codebasics) distingue les options de recherche du contenu des motifs glob d’inclusion et d’exclusion des fichiers. Ne confondez pas ces champs.

L’absence de résultat peut signaler un texte absent, mais aussi une mauvaise sélection, un filtre ou une requête inadaptée. Cherchez un passage dont vous connaissez la présence. S’il reste introuvable, examinez le périmètre et les différences de caractères avant d’élargir le motif. Vérifiez les signes ressemblants et les espaces inattendus, sans normaliser l’original pour faciliter la recherche.

## Conclusion

Choisissez le mode le plus simple adapté au besoin. Une recherche réussie repère du texte pertinent avec des limites comprises. Elle ne prouve pas que tous les passages ont été trouvés et ne justifie pas un remplacement.

## Questions fréquentes

### Faut-il entourer le texte littéral de guillemets ?

Seulement si l’aide de l’application le demande. Sinon, les guillemets peuvent devenir une partie du texte recherché.

### Une recherche avancée garantit-elle les expressions régulières ?

Non. Consultez la documentation du champ concerné. Un motif provenant d’un autre outil peut être refusé ou avoir un autre sens.

### Puis-je tout remplacer après un test réussi ?

Le test seul ne suffit pas. Remplacer est une tâche d’édition distincte, avec sauvegarde utilisable, examen des correspondances réelles et contrôle des modifications. Cette méthode s’arrête à la recherche et à la prise de notes.

## Guides associés

- [Se repérer dans un long document texte](https://onnellab.com/blog/fr/make-long-plain-text-easier-to-navigate/)

## Références

- [Syntaxe de RE2](https://github.com/google/re2/wiki/Syntax)
- [Recherche dans les éditeurs Google](https://support.google.com/docs/answer/62754?hl=en)
- [Édition de base dans VS Code](https://code.visualstudio.com/docs/editing/codebasics)
