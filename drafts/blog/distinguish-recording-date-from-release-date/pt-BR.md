---
title: "Data de gravação e de lançamento nos metadados musicais"
description: "Separe a data de gravação, a do lançamento original e a da sua edição. Registre as fontes e não preencha datas desconhecidas por suposição."
language: "pt-BR"
slug: "distinguish-recording-date-from-release-date"
category: "music"
short_answer: "A data de gravação indica quando a interpretação foi gravada; a data de lançamento, quando o áudio foi lançado. Identifique a edição, confira as informações oficiais e o encarte e registre a fonte de cada data. Não deduza o ano da gravação pelo ano do lançamento."
primary_keyword: "data de gravação e data de lançamento"
secondary_keywords: ""
card_title: "Data de gravação e de lançamento nos metadados musicais"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "data de gravação e data de lançamento"
canonical_url: "https://onnellab.com/blog/pt-br/distinguish-recording-date-from-release-date/"
---

# Data de gravação e de lançamento nos metadados musicais

A data de gravação indica quando a interpretação foi gravada; a data de lançamento, quando o áudio foi lançado. Identifique a edição, confira as informações oficiais e o encarte e registre a fonte de cada data. Não deduza o ano da gravação pelo ano do lançamento.

## Comece por uma edição

Uma pasta de álbum pode conter vários anos plausíveis. Antes de editar, identifique sua edição pelo formato, gravadora, número de catálogo e lista de faixas. Uma página sobre outra edição pode não descrever seus arquivos.

A [documentação de lançamentos do MusicBrainz](https://musicbrainz.org/doc/Release) trata a data em que uma edição foi lançada como informação do lançamento. Para investigar sua cópia, consulte as informações oficiais do artista ou da gravadora e o encarte correspondente.

## Separe três perguntas

| Pergunta | Evidência a procurar | O que não presumir |
| --- | --- | --- |
| Quando esta interpretação foi gravada? | Data explícita da sessão no encarte ou nas notas oficiais | Que o ano do lançamento seja o da gravação |
| Quando esta gravação foi lançada pela primeira vez? | Informação oficial que identifique o lançamento original | Que a data de uma reedição seja a original |
| Quando esta edição foi lançada? | Informações da edição e do território correspondentes | Que todas as edições tenham a mesma data |

O ano de remasterização, um aviso de direitos autorais ou a data de modificação do arquivo não responde, por si só, às três perguntas.

## Cinco passos antes de alterar uma data

1. Guarde um backup e examine uma faixa primeiro. Anote os valores existentes sem sobrescrevê-los.
2. Confira a edição. Registre gravadora, número de catálogo, formato e território, quando disponíveis.
3. Leia o encarte e a página oficial do lançamento. Anote o que cada fonte diz que a data representa, além da página ou URL.
4. Mantenha apenas a precisão sustentada pela evidência. Se só o ano for conhecido, não invente mês ou dia. Registre conflitos em uma nota separada.
5. Confira as definições dos campos do editor e a exibição no player antes de salvar uma cópia de teste. Um campo chamado “Ano” pode não preservar todas essas distinções. Reabra a cópia salva e examine-a antes de alterar outros arquivos.

A [especificação ID3v2.4](https://id3.org/id3v2.4.0-frames) distingue os momentos de gravação, lançamento original e lançamento. Isso não comprova que um editor ofereça todos os campos nem que um player os exiba como esperado. Este roteiro não determina um mapeamento de tags.

## Um exemplo fictício

Imagine que o encarte informe explicitamente uma gravação de 1998, as notas oficiais identifiquem o primeiro lançamento em 2000 e sua edição tenha sido lançada em 2024. Guarde as três informações separadamente, com as fontes. A edição de 2024 não transforma a interpretação em uma gravação de 2024.

Se a data da gravação não aparecer, escreva “desconhecida” nas notas de pesquisa. Não copie 2000 ou 2024 para o campo de gravação só para preencher a lacuna.

## Dúvidas frequentes

### Posso alterar todas as faixas de uma vez?
Primeiro, confira se a evidência vale para todas. Um álbum pode reunir sessões diferentes ou faixas bônus.

### Qual data o player deve mostrar?
Depende do seu objetivo de organização e do comportamento do player. Preserve os fatos separadamente e depois teste a leitura de uma cópia. Não descarte as fontes apenas para deixar a exibição mais organizada.

### E se duas fontes discordarem?
Guarde as duas referências e descreva o conflito. Verifique se tratam da mesma edição e do mesmo território. Deixe a informação em aberto em vez de escolher o ano mais conveniente.

## Próximo passo

Escolha um álbum e crie uma nota de fontes antes de editar as tags. Para outra questão, veja [como distinguir arquivos duplicados de gravações diferentes](/blog/pt-br/distinguish-duplicate-music-files-from-different-recordings/). As datas, sozinhas, não comprovam que dois arquivos contenham a mesma gravação.
