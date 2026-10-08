---
title: "Cómo comprobar el índice y el orden de los capítulos de un EPUB"
card_title: "Cómo comprobar el índice y el orden de los capítulos de un EPUB"
slug: "check-epub-table-of-contents-and-reading-order"
category: "reading"
language: "es"
description: "Compara el EPUB exportado con la lista prevista de capítulos y revisa por separado los enlaces del índice y el orden de lectura."
status: "review"
topic_id: "TOPIC-0061"
search_intent: "troubleshoot"
primary_keyword: "comprobar el índice de un EPUB"
secondary_keywords: "orden de capítulos EPUB|enlaces del índice EPUB|capítulos ausentes EPUB|Papira"
related_apps: "Papira"
tags: "EPUB|índice|orden de lectura|navegación|revisión de ebooks"
short_answer: "Anota los capítulos previstos, abre el EPUB en otro lector y prueba cada enlace del índice. Revisa las transiciones, registra diferencias, corrige el original o los ajustes y vuelve a generar y comprobar el archivo."
canonical_url: "https://onnellab.com/blog/es/check-epub-table-of-contents-and-reading-order/"
image_specs: "Capítulos previstos|Enlaces del índice|Orden de lectura|Corregir y generar de nuevo"
---

# Cómo comprobar el índice y el orden de los capítulos de un EPUB

El EPUB se abre y el índice parece correcto. ¿Cada entrada llega al capítulo previsto? ¿La lectura continua recorre esos capítulos en el mismo orden? Para comprobar el índice de un EPUB, compara el archivo con una lista del manuscrito y prueba ambas formas de navegar. Aquí, «índice» significa la lista de capítulos, no un índice alfabético de términos.

Esta guía empieza después de exportar. Propone una inspección repetible, sin reiniciar la preparación de portada, codificación o manuscrito.

## Pregunta

¿Cómo comprobar que los enlaces del índice y el orden de los capítulos del EPUB coinciden con el original?

## Respuesta breve

Anota los capítulos previstos, abre el EPUB en otro lector y prueba cada enlace del índice. Revisa las transiciones, registra diferencias, corrige el original o los ajustes y vuelve a generar y comprobar el archivo. Conserva manuscrito original y exportación anterior hasta revisar el nuevo archivo.

## Distingue tres elementos

El **rótulo del índice** es el texto que seleccionas en el menú del lector. El **destino del enlace** es la posición que abre. El **orden de lectura** es la secuencia que encuentras al seguir leyendo sin seleccionar otra entrada.

EPUB 3 representa navegación y orden predeterminado por separado: el documento de navegación aporta el índice y el spine del paquete ordena los documentos de contenido. También importa el orden dentro de cada documento. [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) define esta estructura. No necesitas modificar los archivos internos para hacer estas comprobaciones.

| Comprobación | Qué permite saber | Qué queda por revisar |
| --- | --- | --- |
| Comparar índice y lista | Entradas previstas y rótulos comprensibles | Destino de cada enlace |
| Abrir cada enlace | Título y comienzo del capítulo alcanzado | Qué sigue en lectura continua |
| Cruzar límites entre capítulos | Secuencia acorde con el plan | Corrección de todos los enlaces |
| Ejecutar EPUBCheck | Cumplimiento de las reglas EPUB comprobadas | Correspondencia con la intención editorial |

La página de índice dentro del libro y el menú del lector pueden aparecer por separado. Revisa el menú y, si existe esa página, también sus enlaces.

## Prepara la lista de capítulos previstos

Usa el manuscrito como referencia. Anota capítulos en el orden previsto y materiales anteriores y posteriores, como prólogo y epílogo. Decide cuáles deben figurar en el índice. No hace falta una entrada por párrafo.

Si se repiten títulos, añade a tu ficha privada una frase breve del primer párrafo. Así distinguirás, por ejemplo, dos capítulos llamados «Notas». Usa títulos y pasajes reconocibles en lugar de números de página, que pueden cambiar con la presentación del lector.

Registra nombre del archivo exportado, revisión del manuscrito, versión del conversor, nombre y versión del lector. Tras generar de nuevo, confirma que abres el archivo nuevo, no una copia importada anteriormente. Guarda las anotaciones antes de eliminar un ejemplar antiguo de la biblioteca.

## Lleva una ficha de comprobación

Este ejemplo didáctico es ficticio. No describe un fallo observado ni una prueba en dispositivos. La secuencia prevista es «Llegada», «El sendero», «Regreso». Copia las columnas y sustituye los datos por tus observaciones.

| Título previsto | Rótulo del índice | Destino real | Capítulo siguiente | Resultado | Revisión del original o los ajustes |
| --- | --- | --- | --- | --- | --- |
| 1 Llegada | 1 Llegada | 1 Llegada | 2 El sendero | Coincide | Ninguna |
| 2 El sendero | 2 El sendero | 3 Regreso | Sin comprobar | Destino incorrecto | Revisar límite del original y reglas documentadas de exportación |
| 3 Regreso | 3 Regreso | 3 Regreso | Fin del texto principal | Coincide en esta prueba | Revisar por separado el epílogo previsto |

La segunda fila solo registra el resultado hipotético del enlace. No demuestra que falte el capítulo 2. Busca su comienzo o sigue leyendo desde el capítulo 1 antes de distinguir entre contenido ausente y enlace incorrecto.

## Procedimiento recomendado

Realiza estas comprobaciones en un lector EPUB independiente.

1. **Abre la exportación correcta.** Anota los nombres del manuscrito y del EPUB. Usa un lector compatible y revisa cómo importa o sincroniza archivos antes de abrir un manuscrito privado.
2. **Compara el índice completo.** Busca secciones ausentes, entradas inesperadas, rótulos repetidos y una secuencia distinta. Despliega grupos contraídos si el lector los ofrece.
3. **Prueba todos los enlaces.** Compara título y primer pasaje reconocible de cada destino con la referencia. Que se abra algún lugar del libro no significa que sea el correcto. Registra dónde aterriza.
4. **Comprueba la lectura continua por separado.** Empieza antes del primer capítulo principal y cruza su final sin usar el menú. Revisa páginas preliminares y transiciones al principio, en medio y al final; revisa después las transiciones restantes antes de dar todo el libro por comprobado.
5. **Revisa el final.** Confirma que el último capítulo alcanza su cierre previsto y que epílogo o apéndices siguen accesibles. Distingue el material complementario de la secuencia principal.
6. **Usa otro lector si la distribución lo exige.** Abre la misma exportación. Si hay diferencias, registra versiones del archivo y de los lectores. La diferencia merece investigación, pero no identifica por sí sola al componente responsable.

![Proceso ilustrativo: lista prevista, enlaces del índice, orden de lectura y corrección del original antes de generar de nuevo.](/blog-assets/es/check-epub-table-of-contents-and-reading-order/workflow-diagram.svg "Comprueba enlaces y secuencia por separado")

El diagrama propone un método; no es una captura de pantalla ni un registro de pruebas realizadas.

## Diagnostica antes de cambiar el original

| Síntoma | Evidencia necesaria | Siguiente paso |
| --- | --- | --- |
| Falta un capítulo en el índice | ¿Aparece su comienzo en lectura continua? | Si aparece, revisar reconocimiento de títulos y alcance del índice; si no, integridad del original y límites de exportación |
| Rótulo correcto abre otro capítulo | Registrar título y texto abiertos | Comparar límite del original y reglas documentadas de títulos; reproducir con una muestra breve |
| Dos entradas iguales | Comparar destinos y títulos originales | Determinar si la repetición es intencional antes de renombrar o quitar un marcador |
| Enlaces correctos, lectura salta o cambia capítulos | Anotar transición real y capítulo previsto | Revisar secuencia original y opciones disponibles; conservar el resultado si el original está bien |
| Problema en un solo lector | Confirmar la misma revisión exportada | Repetir la transición exacta y comparar versiones antes de atribuir la causa |

Cambia un elemento relevante cada vez. Corrige el manuscrito de trabajo o un ajuste documentado, exporta con un nombre distinto y repite la entrada afectada y las transiciones vecinas. Al terminar, revisa todos los enlaces: un cambio estructural puede afectar a varios destinos.

Si un original correcto sigue produciendo diferencias, consérvalo y crea una muestra breve con texto propio o autorizado para compartir. Describe al soporte los destinos previstos y observados. No envíes un manuscrito inédito completo para demostrar un único problema de navegación.

## Combina validación y lectura

[EPUBCheck](https://www.w3.org/publishing/epubcheck/) verifica publicaciones conforme a las especificaciones EPUB. Investiga errores y advertencias del paquete y valida de nuevo el archivo regenerado. Un informe satisfactorio no decide si el «Capítulo 2» contiene el texto previsto.

Abrir el libro en un lector tampoco demuestra conformidad completa, accesibilidad ni compatibilidad universal. Separa informe, observaciones de navegación y lectores o secciones sin probar. Para textos confidenciales, valida localmente o revisa el tratamiento de datos del servicio antes de subir el libro.

## Dónde encaja ONNELLAB

Si necesitas regenerar un EPUB desde un TXT terminado, Papira es una opción de ONNELLAB. Sus fichas oficiales describen el montaje sin conexión con portada, datos del libro e índice. Edita el manuscrito en otra aplicación y revisa la exportación en otro lector: Papira no ofrece edición del cuerpo del texto ni lector EPUB.

El reconocimiento de títulos depende de la plataforma y versión documentadas. Los idiomas de la interfaz no demuestran qué patrones reconoce, ni un comportamiento idéntico en iOS y Android. Por eso este método no prescribe una regla automática universal. Consulta las instrucciones de tu versión y compara el índice resultante con tu lista.

Revisa las fichas oficiales de [Papira en App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) o [Papira en Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira) para tu plataforma y región. El método también sirve con otros exportadores EPUB.

## Guía relacionada

Si la diferencia obliga a volver a la preparación, consulta [Cómo preparar un manuscrito TXT para convertirlo en EPUB](/blog/es/prepare-txt-manuscript-for-epub/). Esa guía aborda la etapa anterior; esta ficha se utiliza después de exportar.

## Referencias

- [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/): documento de navegación y spine que define el orden predeterminado.
- [W3C EPUBCheck](https://www.w3.org/publishing/epubcheck/): verificador de conformidad EPUB.
- [Papira en App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) y [Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira): alcance y orientación por plataforma.

## Conclusión

Compara intención y observaciones: conserva la lista prevista, prueba cada enlace y revisa la lectura continua. Si difieren, guarda evidencias, corrige el original o los ajustes compatibles y comprueba el nuevo archivo antes de compartirlo.

## Preguntas frecuentes

### ¿Un título visible demuestra que su enlace es correcto?

No. Abre la entrada y compara título y comienzo del destino. El rótulo y la posición enlazada necesitan comprobaciones separadas.

### ¿Un capítulo fuera del índice también falta en el libro?

No necesariamente. Puede seguir en la secuencia de lectura. Busca su comienzo y comprueba el alcance previsto del índice antes de diagnosticar contenido ausente.

### ¿Por qué funcionan los enlaces si el orden es incorrecto?

Al seleccionar enlaces y al continuar leyendo, sigues caminos distintos. Anota el siguiente capítulo real y compáralo con el manuscrito y los ajustes de exportación.

### ¿Superar EPUBCheck basta para distribuir el libro?

Es una comprobación útil. Aún debes verificar texto, navegación, secuencia y requisitos del público o distribuidor. No sustituye la revisión editorial ni la de accesibilidad.

### ¿Debo corregir directamente el EPUB exportado?

Prefiere el original o los ajustes documentados, para mantener la corrección al exportar otra vez. Si tu proceso editorial exige editar el paquete, documenta ese paso de forma reproducible y evita versiones contradictorias.

### ¿Puedo realizar estas pruebas de lectura dentro de Papira?

No. Papira convierte TXT terminados en EPUB; no es un lector. Abre el resultado en otro lector y corrige el manuscrito con un editor de texto.
