---
title: "Como conferir o sumário e a ordem dos capítulos de um EPUB"
card_title: "Como conferir o sumário e a ordem dos capítulos de um EPUB"
slug: "check-epub-table-of-contents-and-reading-order"
category: "reading"
language: "pt-BR"
description: "Compare o EPUB exportado com a lista de capítulos esperada e confira separadamente os links do sumário e a sequência de leitura."
status: "review"
topic_id: "TOPIC-0058"
search_intent: "troubleshoot"
primary_keyword: "conferir o sumário do EPUB"
secondary_keywords: "ordem dos capítulos no EPUB|links do sumário EPUB|capítulos ausentes no EPUB|Papira"
related_apps: "Papira"
tags: "EPUB|sumário|ordem de leitura|navegação|verificação de ebooks"
short_answer: "Liste os capítulos esperados, abra o EPUB em outro leitor e teste cada link do sumário. Confira as transições, registre diferenças, corrija o original ou os ajustes de exportação, gere um novo arquivo e confira-o."
canonical_url: "https://onnellab.com/blog/pt-br/check-epub-table-of-contents-and-reading-order/"
image_specs: "Capítulos esperados|Links do sumário|Ordem de leitura|Corrigir e gerar novamente"
---

# Como conferir o sumário e a ordem dos capítulos de um EPUB

O EPUB abre e o sumário parece correto. Mas cada entrada leva ao capítulo esperado? A leitura contínua percorre os capítulos na mesma ordem? Para conferir o sumário do EPUB, compare o arquivo exportado com uma lista extraída do manuscrito e teste as duas formas de navegação.

Este guia começa depois da exportação. O objetivo é repetir uma inspeção confiável, sem recomeçar a preparação de capa, codificação ou manuscrito.

## Pergunta

Como verificar se os links do sumário e a ordem dos capítulos do EPUB correspondem ao original?

## Resposta curta

Liste os capítulos esperados, abra o EPUB em outro leitor e teste cada link do sumário. Confira as transições, registre diferenças, corrija o original ou os ajustes de exportação, gere um novo arquivo e confira-o. Preserve o manuscrito original e a exportação anterior até verificar o novo arquivo.

## Separe os três elementos da verificação

O **rótulo do sumário** é o texto selecionado no menu do leitor. O **destino do link** é a posição aberta. A **ordem de leitura** é a sequência encontrada ao continuar lendo, sem selecionar outra entrada.

O EPUB 3 representa navegação e ordem padrão separadamente: o documento de navegação fornece o sumário, enquanto o spine do pacote organiza os documentos de conteúdo. A ordem dentro de cada documento também importa. A especificação [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) define essa estrutura. Não é preciso editar arquivos internos para fazer estas verificações.

| Verificação | O que revela | O que ainda verificar |
| --- | --- | --- |
| Comparar sumário e lista | Entradas esperadas e rótulos compreensíveis | Destino de cada link |
| Abrir cada link | Título e início do capítulo alcançado | Próximo capítulo na leitura contínua |
| Atravessar limites entre capítulos | Sequência correspondente ao plano | Correção de todos os links |
| Executar EPUBCheck | Regras EPUB verificadas pela ferramenta | Correspondência com a intenção editorial |

A página de sumário dentro do livro pode aparecer separada do menu do leitor. Confira o menu e, se a exportação incluir essa página, os links dela também.

## Prepare a lista de capítulos esperados

Use o manuscrito como referência. Liste os capítulos na ordem desejada e os elementos anteriores e posteriores, como prefácio e posfácio. Defina quais devem aparecer no sumário: nem todo parágrafo precisa de uma entrada.

Para títulos repetidos, acrescente à ficha particular uma frase curta do primeiro parágrafo. Isso distingue, por exemplo, dois capítulos chamados “Notas”. Prefira títulos e trechos reconhecíveis aos números de página do leitor, que podem mudar conforme a diagramação.

Registre nome do arquivo exportado, revisão do original, versão do conversor, nome e versão do leitor. Ao gerar novamente, confirme que o leitor abriu o novo arquivo, não uma cópia importada anteriormente. Preserve anotações antes de remover um item antigo da biblioteca.

## Registre observações em uma ficha

Este é um exemplo fictício para explicar o método, não um defeito observado nem um teste em dispositivo. A sequência esperada é “Chegada”, “A trilha”, “Retorno”. Copie as colunas e substitua os dados pelas suas observações.

| Título esperado | Rótulo no sumário | Destino real | Capítulo seguinte | Resultado | Ação no original ou configuração |
| --- | --- | --- | --- | --- | --- |
| 1 Chegada | 1 Chegada | 1 Chegada | 2 A trilha | Coincide | Nenhuma |
| 2 A trilha | 2 A trilha | 3 Retorno | Ainda não verificado | Destino incorreto | Conferir limite no original e regras documentadas de exportação |
| 3 Retorno | 3 Retorno | 3 Retorno | Fim do corpo | Coincide nesta verificação | Verificar separadamente o posfácio previsto |

A segunda linha registra apenas o resultado hipotético do link. Não prova que o capítulo 2 esteja ausente. Procure seu início ou continue a leitura a partir do capítulo 1 antes de distinguir conteúdo ausente de link incorreto.

## Passo a passo recomendado

Faça estas verificações em um leitor de EPUB separado.

1. **Abra a exportação correta.** Anote os nomes do manuscrito e do EPUB. Use um leitor compatível e verifique como ele importa ou sincroniza arquivos antes de abrir um original privado.
2. **Compare o sumário inteiro.** Procure seções ausentes, entradas inesperadas, rótulos repetidos e ordem diferente da referência. Expanda grupos recolhidos, quando houver.
3. **Teste todos os links.** Compare o título e o primeiro trecho reconhecível de cada destino com a referência. Abrir algum ponto do livro não significa chegar ao lugar certo. Registre a posição real.
4. **Teste a leitura contínua separadamente.** Comece antes do primeiro capítulo principal e atravesse seu final sem usar o sumário. Confira elementos pré-textuais e transições no início, meio e fim; depois verifique as transições restantes antes de considerar o livro inteiro verificado.
5. **Confira o final.** O último capítulo deve alcançar o encerramento previsto, e posfácio ou apêndice precisam continuar acessíveis. Distinga material complementar da sequência principal.
6. **Use outro leitor quando a distribuição exigir.** Abra a mesma exportação. Se houver diferenças, registre versões do arquivo e dos leitores. A diferença merece investigação, mas sozinha não identifica o componente responsável.

![Fluxo ilustrativo: lista de capítulos, teste dos links, ordem de leitura e correção do original antes de gerar novamente.](/blog-assets/pt-BR/check-epub-table-of-contents-and-reading-order/workflow-diagram.svg "Verifique links e sequência separadamente")

O diagrama sugere um processo; não é captura de tela nem registro de testes concluídos.

## Diagnostique antes de alterar o original

| Sintoma | Evidência a reunir | Próximo passo |
| --- | --- | --- |
| Capítulo ausente do sumário | O início aparece na leitura contínua? | Se sim, revisar reconhecimento de títulos e escopo do sumário; se não, integridade do original e limites da exportação |
| Rótulo correto abre outro capítulo | Registrar título e texto abertos | Comparar limites do original e regras documentadas de títulos; reproduzir com amostra curta |
| Duas entradas iguais | Comparar destinos e títulos originais | Decidir se a repetição é intencional antes de renomear ou remover um marcador |
| Links corretos, mas leitura pula ou troca capítulos | Registrar transição real e capítulo esperado | Conferir sequência original e ajustes disponíveis; guardar o resultado se o original estiver correto |
| Problema em apenas um leitor | Confirmar a mesma revisão exportada | Repetir a transição exata e comparar versões antes de atribuir a causa |

Altere um elemento relevante por vez. Corrija a cópia de trabalho ou uma configuração documentada, exporte com outro nome e teste a entrada afetada e as transições vizinhas. Depois repita todos os links: uma mudança estrutural pode afetar vários destinos.

Se o problema persistir com um original correto, preserve-o e crie uma amostra curta com texto próprio ou autorizado para compartilhamento. Ao pedir suporte, descreva destinos esperados e observados. Não envie um manuscrito inédito inteiro para demonstrar um único problema de navegação.

## Combine validação e leitura

O [EPUBCheck](https://www.w3.org/publishing/epubcheck/) verifica publicações conforme as especificações EPUB. Investigue erros e avisos do pacote e valide novamente o arquivo regenerado. Um relatório sem erros não determina se o “Capítulo 2” contém o capítulo pretendido.

Abrir o livro em um leitor também não comprova conformidade completa, acessibilidade ou compatibilidade universal. Separe relatório de validação, observações de navegação e leitores ou seções não testados. Para texto confidencial, valide localmente ou examine o tratamento de dados do serviço antes do envio.

## Onde entra a ONNELLAB

Para gerar novamente um EPUB a partir de um TXT finalizado, o Papira é uma opção da ONNELLAB. Suas páginas oficiais descrevem a montagem offline com capa, dados do livro e sumário. Edite o manuscrito em outro aplicativo e confira a exportação em outro leitor: o Papira não oferece edição do corpo do texto nem leitor de EPUB.

O reconhecimento de títulos depende da plataforma e versão documentadas. Idiomas da interface não comprovam quais padrões de títulos são reconhecidos, nem comportamento idêntico entre iOS e Android. Portanto, este processo não prescreve uma regra automática universal. Consulte as instruções da versão instalada e compare o sumário gerado com sua lista.

Confira as páginas oficiais do [Papira na App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) e do [Papira no Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira), conforme plataforma e região. O método também serve para outros exportadores EPUB.

## Guia relacionado

Se a diferença exigir corrigir a preparação do original, veja [Como preparar um manuscrito TXT para conversão em EPUB](/blog/pt-br/prepare-txt-manuscript-for-epub/). Esse guia trata da preparação anterior; esta ficha se aplica depois da exportação.

## Referências

- [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/): documento de navegação e spine que define a ordem padrão.
- [W3C EPUBCheck](https://www.w3.org/publishing/epubcheck/): verificador de conformidade EPUB.
- [Papira na App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) e [no Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira): escopo e orientações por plataforma.

## Conclusão

Compare intenção e resultado: mantenha a lista esperada, abra cada link e confira a leitura contínua. Diante de diferenças, preserve evidências, corrija o original ou ajustes compatíveis e verifique o novo arquivo antes de compartilhar.

## Perguntas frequentes

### Um título visível comprova que o link está correto?

Não. Abra a entrada e compare título e texto inicial do destino. Rótulo e posição precisam de verificações separadas.

### Um capítulo fora do sumário também está ausente do livro?

Não necessariamente. Ele pode permanecer na leitura contínua. Procure seu início e confira o escopo pretendido do sumário antes de diagnosticar perda de conteúdo.

### Por que os links funcionam, mas os capítulos aparecem fora de ordem?

Selecionar links e continuar lendo são caminhos diferentes. Registre o capítulo seguinte real e compare com o manuscrito e a configuração de exportação.

### Passar no EPUBCheck basta para distribuir?

É uma verificação útil. Ainda confira texto, navegação, sequência e exigências dos leitores ou distribuidores. Não substitui revisão editorial nem avaliação de acessibilidade.

### Devo corrigir diretamente o EPUB exportado?

Prefira corrigir o original ou ajustes documentados, para repetir a correção na próxima exportação. Se o fluxo editorial exigir editar o pacote, documente uma etapa reproduzível e evite duas versões conflitantes.

### Posso fazer estes testes de leitura no Papira?

Não. O Papira transforma TXT finalizado em EPUB; não é um leitor. Abra o resultado em outro leitor e corrija o manuscrito em um editor de texto.
