---
title: "Elegir entre búsqueda literal y búsqueda por patrones"
description: "Elige el modo de búsqueda, prueba la puntuación con un texto ficticio y revisa el alcance antes de confiar en los resultados."
language: "es"
slug: "choose-literal-or-pattern-search-for-text"
category: "reading"
short_answer: "Usa la búsqueda literal para una secuencia conocida de caracteres. Recurre a un patrón solo si necesitas una regla para varias variantes y has comprobado la sintaxis de la aplicación. Prueba coincidencias y exclusiones con texto ficticio; después revisa el documento sin sustituir nada."
primary_keyword: "búsqueda literal o por patrones"
secondary_keywords: "buscar texto literal|búsqueda con expresiones regulares|buscar signos de puntuación"
card_title: "Elegir entre búsqueda literal y búsqueda por patrones"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "búsqueda literal o por patrones"
canonical_url: "https://onnellab.com/blog/es/choose-literal-or-pattern-search-for-text/"
---

# Elegir entre búsqueda literal y búsqueda por patrones

Buscar una etiqueta que contiene un punto puede devolver un pasaje inesperado. Es posible que los caracteres escritos se interpreten como instrucciones y no como texto. Antes de complicar la consulta, revisa el modo de búsqueda.

## Pregunta

¿Cuándo conviene buscar texto literalmente y cuándo usar un patrón?

## Respuesta breve

Usa la búsqueda literal para una secuencia conocida de caracteres. Recurre a un patrón solo si necesitas una regla para varias variantes y has comprobado la sintaxis de la aplicación. Prueba coincidencias y exclusiones con texto ficticio; después revisa el documento sin sustituir nada.

## Dos significados de una consulta

La búsqueda literal busca los caracteres introducidos sin interpretarlos como operadores de un patrón. La búsqueda por patrones interpreta algunos caracteres como reglas. Una expresión regular es un tipo de patrón; los comodines de nombres de archivo no utilizan necesariamente el mismo lenguaje.

Literal no significa obligatoriamente línea completa, palabra completa, distinción entre mayúsculas y minúsculas o igualdad de bytes entre archivos. Son cuestiones distintas. Una coincidencia dentro de una frase más larga también puede ser literal.

| Tarea | Punto de partida | Qué comprobar |
| --- | --- | --- |
| Encontrar la etiqueta `A.7` | Búsqueda literal | Puntuación y opciones de mayúsculas |
| Encontrar varias variantes definidas | Modo de patrones compatible | Sintaxis y coincidencias no deseadas |
| Limitar los archivos examinados | Controles de alcance | Separar filtros de rutas y búsqueda de contenido |

## Una pequeña prueba ficticia

Crea una nota local desechable con estas tres líneas, sin información privada ni fragmentos de documentos reales.

```text
A.7
Ax7
A-7
```

Para «encontrar la etiqueta `A.7`», solo interesa la primera línea. Empieza en modo literal y comprueba los caracteres resaltados, no solo el número de resultados.

En la [sintaxis de RE2](https://github.com/google/re2/wiki/Syntax), el punto es un comodín; escapado, representa el propio punto. Por tanto, los patrones `A.7` y `A\.7` tienen intenciones distintas en este ejemplo. Esto no garantiza que tu lector los admita. No añadas una barra inversa a la consulta literal si no quieres buscar ese carácter.

Superar esta pequeña prueba no convierte el patrón en una regla completa para el documento. Decide por separado si debe contar la aparición dentro de `ZA.70`. Añade ese caso a la prueba si importa.

## Flujo recomendado

1. **Escribe el objetivo con palabras.** ¿Buscas una frase conocida o varias variantes? Anota un resultado deseado y otro parecido que quieras excluir.
2. **Conserva la fuente.** Usa una vista de solo lectura o una copia de trabajo. Guarda el texto de prueba y las observaciones en notas separadas del documento original. No subas contenido privado a un comprobador de patrones en línea.
3. **Comprueba el campo concreto.** Consulta la ayuda sobre modo, escapes y sintaxis admitida. La [ayuda de Google](https://support.google.com/docs/answer/62754?hl=en) documenta su opción de expresiones regulares y el escape con barra inversa. Son instrucciones de ese producto.
4. **Prueba sin sustituir.** Revisa todas las coincidencias y exclusiones esperadas con el ejemplo ficticio. Cambia una sola opción cada vez. Si el comportamiento no está claro, vuelve a una búsqueda literal corta y distintiva.
5. **Revisa y registra el alcance.** Confirma archivo, versión, selección y filtros. Lee el contexto y anota consulta, modo y opciones relevantes fuera del original.

## El alcance puede cambiar la respuesta

La [documentación de VS Code](https://code.visualstudio.com/docs/editing/codebasics) distingue las opciones de búsqueda de contenido de los patrones glob para incluir o excluir archivos. No confundas esos campos.

Cero resultados puede significar que el texto no está, pero también que la selección, el filtro o la consulta son inadecuados. Busca un pasaje que sepas que existe. Si tampoco aparece, aclara el alcance o la diferencia de caracteres antes de ampliar el patrón. Revisa los signos parecidos y los espacios inesperados; no normalices el original solo para facilitar la búsqueda.

## Conclusión

Elige el modo más sencillo que describa la tarea. Una búsqueda satisfactoria localiza texto relevante con límites conocidos. No demuestra que hayas encontrado todo ni justifica una sustitución.

## Preguntas frecuentes

### ¿Debo poner el texto literal entre comillas?

Solo si lo indica la ayuda de la aplicación. En caso contrario, las comillas podrían formar parte del texto buscado.

### ¿La búsqueda avanzada garantiza expresiones regulares?

No. Revisa la documentación de ese campo. Un patrón copiado de otra herramienta puede no ser compatible o tener otro significado.

### ¿Puedo sustituir todo después de una prueba correcta?

La prueba por sí sola no basta. Sustituir es una tarea de edición independiente: requiere una copia de seguridad utilizable, revisión de las coincidencias reales y un plan para verificar los cambios. Este flujo termina en la búsqueda y el registro.

## Guías relacionadas

- [Orientarte en un documento de texto largo](https://onnellab.com/blog/es/make-long-plain-text-easier-to-navigate/)

## Referencias

- [Sintaxis de RE2](https://github.com/google/re2/wiki/Syntax)
- [Búsqueda en los editores de Google](https://support.google.com/docs/answer/62754?hl=en)
- [Edición básica en VS Code](https://code.visualstudio.com/docs/editing/codebasics)
