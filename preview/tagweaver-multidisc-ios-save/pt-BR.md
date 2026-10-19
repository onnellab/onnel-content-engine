---
title: "Como numerar as faixas de um álbum MP3 com vários discos"
card_title: "Como numerar as faixas de um álbum MP3 com vários discos"
slug: "number-tracks-multi-disc-mp3-album"
category: "music"
language: "pt-BR"
description: "Separe número da faixa e número do disco em álbuns MP3, confirme os totais e teste cópias antes de editar tudo. Entenda TRCK, TPOS e a verificação na biblioteca."
status: "published"
topic_id: "TOPIC-0029"
search_intent: "workflow"
primary_keyword: "numerar as faixas de um álbum MP3 com vários discos"
secondary_keywords: "número da faixa MP3|etiquetas de número do disco|ID3 TRCK TPOS|TagWeaver"
related_apps: "TagWeaver"
tags: "álbum MP3 com vários discos|número da faixa MP3|número do disco|ID3 TRCK TPOS"
short_answer: "Registre a posição da música no próprio disco no campo de faixa e a posição do disco no campo de disco. Inclua totais apenas quando confirmados, preserve os originais e teste uma pequena seleção de cópias no editor e na biblioteca de destino."
canonical_url: "https://onnellab.com/blog/pt-br/number-tracks-multi-disc-mp3-album/"
published_at: "2026-09-04T09:00:00+09:00"
updated_at: "2026-09-04T09:00:00+09:00"
image_specs: "Fluxo de numeração com backup prévio|Mapa dos campos TRCK e TPOS|Verificação na biblioteca de destino"
related_articles: "Como organizar os metadados de MP3 antes de arrumar sua biblioteca => https://onnellab.com/blog/pt-br/clean-up-mp3-metadata-before-organizing-music/|TXT ou EPUB: qual formato é melhor para leitura longa? => https://onnellab.com/blog/pt-br/txt-vs-epub-for-long-reading/|Como ler arquivos TXT grandes com menos travamentos => https://onnellab.com/blog/pt-br/read-large-txt-files-without-lag/|Por que arquivos de texto grandes demoram para abrir => https://onnellab.com/blog/pt-br/large-text-file-slow-to-open/|Como converter arquivos de mídia localmente e com mais privacidade => https://onnellab.com/blog/pt-br/convert-local-media-files-privately/|Como recortar gravações de áudio sem usar um editor completo => https://onnellab.com/blog/pt-br/trim-audio-recordings-without-full-editor/"
---

# Como numerar as faixas de um álbum MP3 com vários discos

Uma caixa de discos tem duas ordens: músicas dentro de cada disco e discos dentro do conjunto. Registre essas posições separadamente, preserve as incertezas e confira uma amostra antes de alterar o álbum inteiro.

## Pergunta

Como numerar as faixas de um álbum MP3 com vários discos?

## Resposta curta

Use o campo de faixa para a posição da música naquele disco e o campo de disco para a posição no conjunto. A quarta música do segundo disco de três pode ter faixa `4` e disco `2`. Use totais como `4/11` e `2/3` somente após confirmar as quantidades. Edite cópias, uniformize álbum e artista do álbum, salve uma amostra e confira as etiquetas gravadas e a biblioteca de destino.

## Posição da faixa e posição do disco

A **posição da faixa** é o número da música dentro do disco. O frame `TRCK` do ID3v2 guarda esse valor. A definição ID3v2.4 permite uma posição numérica seguida, opcionalmente, de barra e total: `4/11`. Apenas `4` também é válido.

A **posição do disco** indica qual parte é aquela dentro do conjunto. O frame `TPOS` segue o mesmo padrão: `2/3` significa a segunda de três partes. Em lançamentos musicais, a parte costuma ser um disco físico ou lógico; isso não determina o nome exibido por cada aplicativo.

`TRCK=4/11` com `TPOS=2/3` preserva “quarta faixa do segundo disco”. Apenas uma sequência contínua, como faixa 15, não registra onde começa o segundo disco. Essa convenção pessoal é possível, mas deve ser distinguida da numeração original por disco.

## Defina a convenção antes de editar

Use uma lista confiável da edição exata: encarte ou relação oficial da editora ou gravadora. Edições de luxo, regionais, relançamentos e discos extras podem ter quantidades diferentes. Um título parecido não comprova a edição.

Anote previamente:

- nome exato do álbum em todas as faixas;
- artista do álbum comum, quando aplicável;
- discos realmente presentes e eventuais ausências;
- quantidade de faixas por disco e localização dos extras;
- quais totais estão confirmados;
- numeração original por disco ou convenção pessoal documentada.

Quando a fonte separa os discos, prefira reiniciar as faixas em 1 em cada disco e diferenciá-los com `TPOS`. Não invente discos ausentes ou totais para preencher campos. Uma posição conhecida é melhor que um total incorreto.

## Faça um mapa antes da edição em lote

Esta amostra de um álbum duplo permite conferir as fronteiras:

| Arquivo | Faixa (`TRCK`) | Disco (`TPOS`) | Verificação |
| --- | --- | --- | --- |
| Primeira música do disco 1 | `1/10` | `1/2` | Edição correta e dez faixas |
| Última música do disco 1 | `10/10` | `1/2` | Sem lacunas nem posições repetidas |
| Primeira música do disco 2 | `1/12` | `2/2` | Reinício intencional em 1 |
| Última música do disco 2 | `12/12` | `2/2` | Totais por disco e do conjunto conferidos |

Sem totais confirmados, use faixas `1`, `10`, `1`, `12` e discos `1` ou `2`. Não substitua posições numéricas por descrições como “segundo disco”; guarde dúvidas em notas separadas.

## Proteja os originais e selecione por disco

Mantenha uma cópia intacta fora da pasta de trabalho. Um backup sobrescrito junto com os arquivos editados não oferece proteção independente. Uma lista de arquivos ou somas de verificação pode ajudar na comparação.

Agrupe as cópias pelo disco real. Uma pasta `CD2` é uma pista: compare títulos, durações e etiquetas com a lista confiável. Retire arquivos incertos da seleção.

Compartilhe apenas valores realmente comuns: dados do álbum no conjunto e posição do disco dentro daquele disco. Títulos e posições de faixa são individuais; ferramentas de sequência exigem revisão do resultado.

## Fluxo de trabalho recomendado

1. **Preserve a fonte.** Copie o álbum completo e mantenha o original intacto. Confira se todos os discos e arquivos esperados estão presentes.
2. **Identifique a edição.** Compare títulos, durações, extras e divisões impressas com uma lista confiável. Marque divergências sem forçar arquivos na sequência.
3. **Escolha a numeração.** Para preservar o lançamento, use posições por disco e um campo de disco separado. Documente qualquer sequência contínua pessoal.
4. **Monte o mapa.** Liste título, posição `TRCK`, total opcional de faixas, posição `TPOS` e total opcional de discos. Procure lacunas e duplicatas em cada disco.
5. **Edite uma amostra.** Inclua a primeira e a última faixa de um disco e a primeira do seguinte, expondo erros na fronteira e no reinício.
6. **Salve e reabra.** Feche o editor ou desmarque a seleção, reabra os mesmos arquivos e confira os valores gravados. A prévia não comprova a gravação.
7. **Teste o destino.** Importe somente a amostra. Examine agrupamento, fronteiras, ordem e primeira transição entre discos. O resultado vale para aquele aplicativo e versão.
8. **Amplie por disco.** Aplique apenas o mapa revisado. Reabra a primeira, uma intermediária e a última faixa de cada disco concluído e compare os valores com o mapa.
9. **Guarde o backup até a segunda conferência.** Verifique o álbum inteiro novamente após atualizar ou reimportar conforme a documentação da biblioteca.

![Diagrama de numeração por disco](/blog-assets/pt-BR/number-tracks-multi-disc-mp3-album/workflow-diagram.svg "Backup, atribuição de posições e verificação das faixas e dos discos")

## Confira mais que a ordem visível

Uma lista correta pode esconder etiquetas erradas. A biblioteca pode manter dados importados, armazenar valores antigos em cache ou aplicar regras próprias. Reabra os arquivos em um leitor ou editor de metadados e confira `TRCK` e `TPOS`. Depois atualize ou reimporte apenas o teste conforme a documentação do destino.

Verifique início e fim de cada disco, transições e discos extras com quantidades diferentes. Procure posições repetidas ou ausentes, totais inconsistentes e um único número de disco aplicado ao álbum todo. Reproduzir sem erro não comprova a numeração: etiquetas descrevem o áudio, mas não reparam danos, comprovam os fatos ou garantem reprodução sem intervalos.

## Falhas comuns e respostas seguras

| Sintoma | O que investigar | Resposta segura |
| --- | --- | --- |
| Disco 2 aparece antes do 1 | Posições de disco ausentes ou diferentes | Reabrir e comparar `TPOS` com o mapa |
| Faixas de discos distintos se misturam | Valores ausentes, inconsistentes ou ignorados | Conferir etiquetas; consultar e testar o destino |
| Posições duplicadas no mesmo disco | Um valor de faixa aplicado em lote | Restaurar cópias afetadas ou reaplicar posições individuais |
| Álbum dividido em grupos | Álbum ou artista do álbum divergentes | Comparar o texto exato antes de renumerar |
| Total incorreto em alguns arquivos | Edições misturadas ou seleção incompleta | Confirmar a edição; uniformizar apenas totais conhecidos |
| Editor e player discordam | Cache ou suporte diferente aos campos | Conferir o arquivo e atualizar somente o teste |

## Como usar ONNELLAB

[TagWeaver](/apps/tagweaver/) é um editor local de metadados MP3 que pode aplicar um mapa revisado aos arquivos selecionados. As informações mantidas do produto descrevem edição individual gratuita e edição em lote na compra única opcional Pro. As lojas oficiais incluem faixa e disco entre os campos editáveis; confira os detalhes da plataforma usada.

O aplicativo não identifica a edição correta nem inventa posições confiáveis. Defina a lista e as regras primeiro, deixe o backup fora da seleção, salve explicitamente e valide uma amostra. Segundo as notas da versão 2.5.1 na App Store, ao salvar no iOS, o original selecionado é atualizado quando seu local permite gravação; caso contrário, o TagWeaver pergunta onde salvar uma cópia. Faça um backup separado antes de editar e confira o local do arquivo salvo.

## Referências

- [ID3.org: frames ID3v2.4.0](https://id3.org/id3v2.4.0-frames): definições de `TRCK`, `TPOS` e totais opcionais após a barra.
- [ID3.org: estrutura ID3v2.4.0](https://id3.org/id3v2.4.0-structure): estrutura das etiquetas e frames que transportam metadados.
- [ID3.org: especificação ID3v2.3.0](https://id3.org/id3v2.3.0): definições anteriores para arquivos e ferramentas dessa versão.
- [TagWeaver na App Store](https://apps.apple.com/app/id6759609875): informações oficiais para iOS.
- [TagWeaver no Google Play](https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2): informações oficiais para Android.

## Conclusão

Trate posição da faixa e do disco como fatos distintos. Confirme a edição, mapeie os arquivos, preserve originais e teste as fronteiras. Totais, zeros à esquerda, nomes de arquivo e apresentação são convenções secundárias. A base confiável combina `TRCK` e `TPOS` corretos com um processo reversível.

## Perguntas frequentes

### O segundo disco deve recomeçar na faixa 1?

Geralmente sim, ao preservar sequências impressas independentes. Guarde a faixa em `TRCK` e diferencie o disco com `TPOS`. Documente uma eventual sequência pessoal contínua.

### Preciso incluir totais como `4/11` e `2/3`?

Não. São opcionais e exigem confirmação da edição e das quantidades completas. Uma posição correta é mais segura que um total errado.

### Numerar os discos corrige a ordem em qualquer player?

Não há comportamento universal. Cada destino decide como ler, agrupar, armazenar em cache e exibir os dados. Teste uma cópia representativa.

### Posso usar nomes de arquivo no lugar das etiquetas?

Eles ajudam a inspecionar pastas, mas não comprovam a gravação de `TRCK` e `TPOS`. Faça renomeações separadamente e de forma reversível.

### Alterar essas etiquetas afeta a qualidade do áudio?

As posições são metadados, não amostras sonoras. A edição conceitualmente não melhora nem recodifica o áudio, mas preserve originais e confira a saída real do editor.
