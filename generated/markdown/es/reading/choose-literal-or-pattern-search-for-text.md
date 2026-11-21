---
title: "¿Cuándo conviene usar una búsqueda literal o por patrón?"
card_title: "¿Cuándo conviene usar una búsqueda literal o por patrón?"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
language: "es"
description: "Usa la búsqueda literal cuando conozcas el texto exacto, con sus signos de puntuación. Pasa a una búsqueda por patrón cuando quieras encontrar varias formas parecidas y la herramienta admita expresiones regulares."
status: "review"
topic_id: "TOPIC-0149"
search_intent: "workflow"
primary_keyword: "búsqueda literal"
secondary_keywords: "búsqueda por patrón|expresiones regulares|coincidencia parcial"
related_apps: ""
canonical_url: ""
published_at: ""
updated_at: ""
tags: "búsqueda literal|búsqueda por patrón|expresiones regulares|coincidencia parcial"
short_answer: "Usa la búsqueda literal cuando conozcas el texto exacto, con sus signos de puntuación. Pasa a una búsqueda por patrón cuando quieras encontrar varias formas parecidas y la herramienta admita expresiones regulares."
---

# ¿Cuándo conviene usar una búsqueda literal o por patrón?

## Pregunta

¿Cuándo conviene usar una búsqueda literal o por patrón?

## Respuesta breve

Usa la búsqueda literal cuando conozcas el texto exacto, con sus signos de puntuación. Pasa a una búsqueda por patrón cuando quieras encontrar varias formas parecidas y la herramienta admita expresiones regulares.

Una expresión regular es una regla que describe qué cadenas coinciden con la búsqueda. En una clase de caracteres, los corchetes agrupan las opciones para una posición. Si los propios corchetes de `[draft]` forman parte de lo que buscas, empieza con la búsqueda literal.

## Flujo de trabajo recomendado

1. En un documento de prueba, escribe `[draft]`, `draft`, `Ref-03`, `Ref-42` y `Ref-AA` en líneas separadas. Añade `Ref-031` en la sexta línea para ver si la búsqueda resalta solo una parte del código.
2. Busca `[draft]` en modo literal. La palabra sin corchetes no debería aparecer como resultado. Si el resaltado no es el esperado, comprueba que el modo de expresión regular está desactivado y que buscas en el archivo o en la selección que quieres revisar.
3. Si la herramienta lo permite, activa las expresiones regulares y prueba `Ref-[0-9][0-9]`. El patrón encuentra `Ref-03` y `Ref-42`, pero no `Ref-AA`. En `Ref-031`, fíjate en dónde termina el resaltado. Encontrar el principio no demuestra que el código completo tenga dos cifras.
4. Decide qué resultados te interesan antes de buscar en el documento original. Para comprobarlos no necesitas pulsar Reemplazar. Tampoco hace falta pegar texto privado en un probador en línea: basta con el ejemplo inventado.

![Texto conocido: Modo literal; Forma común: Patrón, si es compatible; Prueba el patrón: Incluye un caso negativo; Mira el resaltado: Comprueba todo el resultado.](/blog-assets/es/choose-literal-or-pattern-search-for-text/workflow-diagram.svg)

| Objetivo|Modo recomendado |
| --- | --- |
| Encontrar un texto conocido, con sus signos|Búsqueda literal |
| Encontrar varios códigos de estructura común|Patrón, si es compatible |
| Revisar una coincidencia inesperada|Comprueba el resaltado y el texto cercano |

## Preguntas frecuentes

### ¿Qué hago si no hay una opción de expresiones regulares?

Busca por separado las formas que conozcas. Si salen demasiados resultados, prueba las opciones de distinguir mayúsculas y minúsculas o buscar palabras completas, si están disponibles. Esas opciones no activan la búsqueda por patrón.

### ¿Si no hay resultados, el texto no está en el documento?

No necesariamente. Prueba con un fragmento corto que sepas que existe. Comprueba el ámbito de búsqueda y la opción de mayúsculas y minúsculas antes de sacar una conclusión.

## Referencias

- [MDN: clases de caracteres en expresiones regulares](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Character_class)

## Conclusión

Empieza en modo literal y cambia solo cuando lo necesites. Prueba un caso que deba aparecer y otro que deba quedar fuera.
