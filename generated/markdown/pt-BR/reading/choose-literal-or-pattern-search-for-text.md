---
title: "Quando vale usar busca literal ou por padrão em um texto?"
card_title: "Quando vale usar busca literal ou por padrão em um texto?"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
language: "pt-BR"
description: "Use a busca literal quando você souber o que está escrito, inclusive a pontuação. Passe para a busca por padrão quando precisar localizar várias formas parecidas e o leitor oferecer suporte a expressões regulares."
status: "review"
topic_id: "TOPIC-0146"
search_intent: "workflow"
primary_keyword: "busca literal"
secondary_keywords: "busca por padrão|expressões regulares|busca de texto"
related_apps: ""
canonical_url: ""
published_at: ""
updated_at: ""
tags: "busca literal|busca por padrão|expressões regulares|busca de texto"
short_answer: "Use a busca literal quando você souber o que está escrito, inclusive a pontuação. Passe para a busca por padrão quando precisar localizar várias formas parecidas e o leitor oferecer suporte a expressões regulares."
---

# Quando vale usar busca literal ou por padrão em um texto?

## Pergunta

Quando vale usar busca literal ou por padrão em um texto?

## Resposta curta

Use a busca literal quando você souber o que está escrito, inclusive a pontuação. Passe para a busca por padrão quando precisar localizar várias formas parecidas e o leitor oferecer suporte a expressões regulares.

Uma expressão regular é uma regra que descreve quais sequências devem corresponder à busca. Os colchetes de uma classe de caracteres indicam opções para uma posição. Se a ideia for localizar a palavra `[draft]` com os próprios colchetes, comece pela busca literal.

## Fluxo de trabalho recomendado

1. Em um documento de teste, coloque `[draft]`, `draft`, `Ref-03`, `Ref-42` e `Ref-AA` em linhas separadas. Acrescente `Ref-031` para descobrir se a busca vai destacar só uma parte do código.
2. No modo literal, procure `[draft]`. A palavra sem os colchetes não deve aparecer nos resultados. Se a marcação surpreender, confira se a opção de expressão regular está desligada e se a busca abrange o arquivo ou a seleção que você pretendia.
3. Se houver suporte a expressões regulares, busque `Ref-[0-9][0-9]`. O padrão encontra `Ref-03` e `Ref-42`, mas não `Ref-AA`. Na linha `Ref-031`, observe até onde vai o destaque: encontrar o começo não prova que o código inteiro tem só dois algarismos.
4. Decida quais resultados são úteis antes de usar a busca no documento original. Não é preciso usar Substituir para conferir os resultados. O exemplo fictício também evita colar trechos privados em testadores on-line.

![Grafia conhecida: Busca literal; Estrutura comum: Padrão, se houver suporte; Teste a consulta: Inclua um caso negativo; Confira o destaque: Veja o resultado inteiro.](/blog-assets/pt-BR/choose-literal-or-pattern-search-for-text/workflow-diagram.svg)

| Objetivo|Modo indicado |
| --- | --- |
| Localizar uma grafia conhecida com a pontuação|Busca literal |
| Localizar vários códigos com a mesma estrutura|Padrão, se houver suporte |
| Verificar resultados inesperados|Confira os limites do destaque e o contexto |

## Perguntas frequentes

### E se o leitor não tiver opção de expressão regular?

Busque as grafias conhecidas separadamente. Se aparecerem muitos resultados, teste as opções de diferenciar maiúsculas e minúsculas ou de buscar palavras inteiras, se existirem. Essas opções não ativam a busca por padrão.

### Uma busca sem resultados prova que o texto não está lá?

Não. Tente primeiro uma sequência curta que você sabe que existe. Verifique o alcance da busca e as opções de maiúsculas e minúsculas antes de tirar uma conclusão.

## Referências

- [MDN: classes de caracteres em expressões regulares](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Character_class)

## Conclusão

Comece pela busca literal e mude de modo só quando precisar. Teste um caso que deve aparecer e outro que deve ficar de fora.
