---
title: "Quando usar busca literal ou por padrões em textos"
description: "Escolha o modo de busca, teste a pontuação em um texto fictício e confira o escopo antes de confiar nos resultados."
language: "pt-BR"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
short_answer: "Use a busca literal para uma sequência conhecida de caracteres. Use padrões apenas quando precisar de uma regra para várias formas e tiver conferido a sintaxe do aplicativo. Teste o que deve ou não corresponder em um texto fictício; depois examine o documento sem substituir nada."
primary_keyword: "busca literal ou por padrões"
secondary_keywords: "buscar texto literal|busca com expressões regulares|buscar pontuação"
card_title: "Quando usar busca literal ou por padrões em textos"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "busca literal ou por padrões"
canonical_url: "https://onnellab.com/blog/pt-br/choose-literal-or-pattern-search-for-text/"
---

# Quando usar busca literal ou por padrões em textos

Uma busca por um rótulo com ponto pode encontrar um trecho inesperado. Os caracteres digitados talvez estejam sendo interpretados como instruções, e não como texto. Antes de complicar a consulta, confira o modo de busca.

## Pergunta

Quando devo buscar o texto literalmente e quando devo usar um padrão?

## Resposta curta

Use a busca literal para uma sequência conhecida de caracteres. Use padrões apenas quando precisar de uma regra para várias formas e tiver conferido a sintaxe do aplicativo. Teste o que deve ou não corresponder em um texto fictício; depois examine o documento sem substituir nada.

## Dois sentidos para a consulta

A busca literal procura os caracteres digitados sem tratá-los como operadores de um padrão. A busca por padrões interpreta alguns caracteres como regras. Uma expressão regular é um tipo de padrão; curingas de nomes de arquivos não usam necessariamente a mesma linguagem.

Literal não significa obrigatoriamente linha inteira, palavra inteira, distinção entre maiúsculas e minúsculas ou igualdade dos bytes de arquivos. São questões separadas. Uma correspondência dentro de uma frase maior também pode ser literal.

| Tarefa | Ponto de partida | O que conferir |
| --- | --- | --- |
| Encontrar o rótulo `A.7` | Busca literal | Pontuação e opções de maiúsculas |
| Encontrar várias formas definidas | Modo de padrões compatível | Sintaxe e resultados indesejados |
| Limitar os arquivos pesquisados | Controles de escopo | Separação entre filtros de caminhos e conteúdo |

## Um teste fictício pequeno

Crie uma nota local descartável com estas três linhas, sem informações privadas nem trechos de documentos reais:

```text
A.7
Ax7
A-7
```

Para a tarefa “encontrar o rótulo `A.7`”, só a primeira linha interessa. Comece no modo literal e confira os caracteres destacados, não apenas a contagem.

Na [sintaxe do RE2](https://github.com/google/re2/wiki/Syntax), o ponto é um curinga; com escape, representa o próprio ponto. Assim, os padrões `A.7` e `A\.7` têm intenções diferentes neste exemplo. Isso não garante que seu leitor aceite essas expressões. Não acrescente uma barra invertida à consulta literal, a menos que queira procurar esse caractere.

Passar nesse teste não torna o padrão uma regra completa para o documento. Decida, por exemplo, se a ocorrência dentro de `ZA.70` também deve contar. Acrescente esse caso ao teste se ele for relevante.

## Fluxo recomendado

1. **Escreva o objetivo em palavras.** Você procura uma frase conhecida ou uma família de formas? Liste um resultado desejado e outro parecido que deve ficar de fora.
2. **Preserve a fonte.** Use uma visualização somente leitura ou uma cópia de trabalho. Separe o texto de teste das observações. Não envie conteúdo privado a um testador de padrões on-line.
3. **Confira o campo de busca usado.** Consulte a ajuda sobre modo, escapes e sintaxe. A [ajuda do Google](https://support.google.com/docs/answer/62754?hl=en) documenta sua opção de expressões regulares e o uso da barra invertida. São instruções daquele produto.
4. **Teste sem substituir.** Confira todas as correspondências e exclusões esperadas na amostra fictícia. Altere uma opção por vez. Se o comportamento não estiver claro, volte à busca literal com uma frase curta e específica.
5. **Confira e registre o escopo.** Confirme arquivo, versão, seleção e filtros. Leia o contexto e anote consulta, modo e opções relevantes fora do original.

## O escopo pode mudar a resposta

A [documentação do VS Code](https://code.visualstudio.com/docs/editing/codebasics) distingue as opções de busca no conteúdo dos padrões glob para incluir ou excluir arquivos. Não misture esses campos.

Nenhum resultado pode indicar ausência do texto, mas também seleção, filtro ou consulta inadequados. Busque um trecho que você sabe que existe. Se ele também não aparecer, resolva a diferença de escopo ou de caracteres antes de ampliar o padrão. Confira sinais parecidos e espaços inesperados; não normalize o original só para facilitar a busca.

## Conclusão

Escolha o modo mais simples que expresse a tarefa. Uma busca bem-sucedida localiza texto relevante com limites conhecidos. Não prova que tudo foi encontrado nem justifica uma substituição.

## Perguntas frequentes

### Devo colocar aspas no texto literal?

Somente se a ajuda do aplicativo orientar isso. Caso contrário, as aspas podem fazer parte do texto procurado.

### Um botão de busca avançada garante expressões regulares?

Não. Confira a documentação daquele campo. Um padrão de outra ferramenta pode não funcionar ou ter outro significado.

### Posso substituir tudo depois do teste?

O teste sozinho não basta. A substituição é uma tarefa de edição separada: exige backup utilizável, revisão das correspondências reais e um plano de verificação. Este fluxo termina na busca e no registro.

## Guias relacionados

- [Facilitar a navegação em um documento de texto longo](https://onnellab.com/blog/pt-br/make-long-plain-text-easier-to-navigate/)

## Referências

- [Sintaxe do RE2](https://github.com/google/re2/wiki/Syntax)
- [Busca nos editores do Google](https://support.google.com/docs/answer/62754?hl=en)
- [Edição básica no VS Code](https://code.visualstudio.com/docs/editing/codebasics)
