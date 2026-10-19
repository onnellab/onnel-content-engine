---
title: "Cómo numerar las pistas de un álbum MP3 de varios discos"
card_title: "Cómo numerar las pistas de un álbum MP3 de varios discos"
slug: "number-tracks-multi-disc-mp3-album"
category: "music"
language: "es"
description: "Separa el número de pista del número de disco en álbumes MP3. Verifica TRCK, TPOS y los totales, conserva los originales y prueba una muestra en la biblioteca."
status: "published"
topic_id: "TOPIC-0029"
search_intent: "workflow"
primary_keyword: "numerar las pistas de un álbum MP3 de varios discos"
secondary_keywords: "número de pista MP3|etiquetas de número de disco|ID3 TRCK TPOS|TagWeaver"
related_apps: "TagWeaver"
tags: "álbum MP3 de varios discos|número de pista MP3|número de disco|ID3 TRCK TPOS"
short_answer: "Guarda la posición de la canción dentro de su disco en el campo de pista y la posición del disco en el campo de disco. Añade totales solo si están verificados, conserva los originales y comprueba una pequeña selección de copias en el editor y la biblioteca de destino."
canonical_url: "https://onnellab.com/blog/es/number-tracks-multi-disc-mp3-album/"
published_at: "2026-09-04T09:00:00+09:00"
updated_at: "2026-09-04T09:00:00+09:00"
image_specs: "Numeración de varios discos con copia de seguridad previa|Correspondencia de campos TRCK y TPOS|Verificación en la biblioteca de destino"
related_articles: "Cómo limpiar los metadatos MP3 antes de organizar tu música => https://onnellab.com/blog/es/clean-up-mp3-metadata-before-organizing-music/|TXT o EPUB para leer textos largos => https://onnellab.com/blog/es/txt-vs-epub-for-long-reading/|Cómo leer archivos TXT grandes sin ralentizaciones innecesarias => https://onnellab.com/blog/es/read-large-txt-files-without-lag/|Por qué los archivos de texto grandes tardan en abrirse => https://onnellab.com/blog/es/large-text-file-slow-to-open/|Cómo convertir archivos multimedia localmente y con privacidad => https://onnellab.com/blog/es/convert-local-media-files-privately/|Cómo recortar una grabación de audio sin usar un editor completo => https://onnellab.com/blog/es/trim-audio-recordings-without-full-editor/"
---

# Cómo numerar las pistas de un álbum MP3 de varios discos

Una caja de discos tiene dos órdenes: canciones dentro de cada disco y discos dentro del conjunto. Regístralos por separado, deja visibles las dudas y verifica una muestra antes de cambiar todo el álbum.

## Pregunta

¿Cómo numerar las pistas de un álbum MP3 de varios discos?

## Respuesta breve

El campo de pista contiene la posición de la canción en su propio disco; el de disco, la posición del disco en el conjunto. La cuarta canción del segundo disco de tres puede llevar pista `4` y disco `2`. Usa totales como `4/11` y `2/3` solo tras comprobar las cantidades. Edita copias, unifica álbum y artista del álbum, guarda una muestra y revisa las etiquetas escritas y la biblioteca de destino.

## Distingue la posición de pista y de disco

La **posición de pista** es el número de la canción dentro de su disco. El marco `TRCK` de ID3v2 guarda ese valor. ID3v2.4 permite una posición numérica seguida de una barra y un total opcionales, como `4/11`. Escribir solo `4` también expresa la posición.

La **posición de disco** indica qué parte ocupa dentro del conjunto. `TPOS` usa el mismo patrón: `2/3` significa segunda parte de tres. En un lanzamiento musical suele corresponder a un disco físico o lógico, sin determinar cómo lo denomina cada aplicación.

`TRCK=4/11` junto con `TPOS=2/3` conserva «cuarta pista del segundo disco». Un número continuo como 15 puede mantener un orden de escucha, pero no registra dónde comienza el segundo disco. Esa convención personal es posible; distínguela de las posiciones originales por disco.

## Decide la convención antes de editar

Busca una lista fiable de la edición exacta: libreto o catálogo oficial de la editora o discográfica. Las ediciones de lujo, regionales, reediciones y versiones con discos adicionales pueden tener cantidades distintas. Un título parecido no acredita la edición.

Anota previamente:

- nombre exacto del álbum para todas las pistas;
- artista del álbum común, cuando corresponda;
- discos presentes y posibles ausencias;
- cantidad de pistas por disco y ubicación de los extras;
- qué totales están confirmados;
- numeración impresa por disco o convención personal documentada.

Si la fuente distingue los discos, lo habitual es empezar cada uno en la pista 1 y diferenciarlos con `TPOS`. No inventes discos ausentes ni totales para completar campos. Una posición conocida es mejor que un total incorrecto.

## Prepara una tabla antes de la edición por lotes

Esta muestra de un álbum doble permite revisar los límites:

| Archivo | Pista (`TRCK`) | Disco (`TPOS`) | Qué verificar |
| --- | --- | --- | --- |
| Primera canción del disco 1 | `1/10` | `1/2` | Edición correcta y diez pistas |
| Última canción del disco 1 | `10/10` | `1/2` | Sin posiciones omitidas ni duplicadas |
| Primera canción del disco 2 | `1/12` | `2/2` | Reinicio intencionado en 1 |
| Última canción del disco 2 | `12/12` | `2/2` | Totales de pistas y discos contrastados |

Sin totales confirmados, puedes usar pistas `1`, `10`, `1`, `12` y discos `1` o `2`. No pongas descripciones como «segundo disco» en campos numéricos; conserva las dudas en notas separadas.

## Protege el original y selecciona por disco

Guarda una copia intacta fuera de la carpeta de trabajo. Una copia de seguridad sobrescrita junto con los archivos editados no es independiente. Una lista de archivos o sumas de comprobación puede facilitar la comparación.

Agrupa las copias por su disco real. Una carpeta llamada `CD2` solo es una pista: contrasta títulos, duraciones y etiquetas con la lista fiable. Retira los archivos dudosos de la selección por lotes.

Comparte únicamente valores realmente comunes: datos del álbum en todo el conjunto y posición de disco dentro del mismo disco. Títulos y posiciones de pista son individuales; revisa también lo que asigne una herramienta de secuencias.

## Flujo de trabajo recomendado

1. **Conserva la fuente.** Copia el álbum completo a una ubicación de trabajo y deja intacto el original. Comprueba que estén todos los discos y archivos esperados.
2. **Identifica la edición.** Compara títulos, duraciones, extras y límites impresos con una lista fiable. Marca los archivos sin correspondencia en lugar de forzarlos en la secuencia.
3. **Elige la numeración.** Para reproducir el lanzamiento, usa posiciones por disco y un campo de disco separado. Documenta cualquier secuencia personal continua.
4. **Crea la tabla.** Incluye título, posición `TRCK`, total opcional de pistas, posición `TPOS` y total opcional de discos. Busca huecos y duplicados en cada disco.
5. **Edita una muestra.** Incluye primera y última pista de un disco y primera del siguiente: así aparecen errores de límites y reinicio.
6. **Guarda y vuelve a abrir.** Cierra el editor o desmarca la selección y abre los mismos archivos para comprobar los valores almacenados. Una vista previa no demuestra la escritura.
7. **Prueba la biblioteca de destino.** Importa solo la muestra. Revisa agrupación, límites, orden y primera transición entre discos. El resultado corresponde a esa aplicación y versión.
8. **Amplía por discos.** Aplica únicamente la tabla revisada. Vuelve a abrir la primera, una intermedia y la última pista de cada disco terminado y compara sus valores con la tabla.
9. **Conserva la copia hasta la segunda revisión.** Comprueba otra vez el álbum completo tras actualizar o reimportar según la documentación de la biblioteca.

![Diagrama de numeración por discos](/blog-assets/es/number-tracks-multi-disc-mp3-album/workflow-diagram.svg "Conservar originales, asignar posiciones y verificar pistas y discos")

## Comprueba más que el orden visible

Una lista aparentemente correcta puede ocultar etiquetas erróneas. La biblioteca puede conservar datos importados, usar valores antiguos en caché o aplicar sus propias reglas de presentación. Abre primero los archivos en un lector o editor de metadatos y comprueba `TRCK` y `TPOS`. Después actualiza o reimporta solo la muestra según la documentación del destino.

Revisa inicio y final de cada disco, transiciones y discos adicionales con distintas cantidades de pistas. Busca posiciones repetidas o ausentes, totales incoherentes y un mismo valor de disco aplicado por error a todo el álbum. La reproducción correcta no demuestra una numeración correcta: las etiquetas describen el audio, pero no reparan daños, acreditan la veracidad de los datos ni garantizan reproducción sin pausas.

## Errores habituales y respuestas seguras

| Síntoma | Qué investigar | Respuesta segura |
| --- | --- | --- |
| Disco 2 antes del disco 1 | Posiciones de disco ausentes o incoherentes | Reabrir y comparar `TPOS` con la tabla |
| Pistas de distintos discos entremezcladas | Valores ausentes, diferentes o ignorados | Comprobar etiquetas; consultar y probar el destino |
| Posiciones duplicadas en un disco | Mismo valor de pista aplicado por lotes | Restaurar copias afectadas o reasignar posiciones individuales |
| Álbum dividido en grupos | Diferencias en álbum o artista del álbum | Comparar el texto exacto antes de renumerar |
| Total erróneo en algunos archivos | Ediciones mezcladas o selección incompleta | Confirmar la edición; unificar solo totales conocidos |
| Editor y reproductor discrepan | Caché o distinto soporte de campos | Revisar el archivo y actualizar solo la muestra |

## Cómo usar ONNELLAB

[TagWeaver](/apps/tagweaver/) es un editor local de metadatos MP3 que permite aplicar una tabla revisada a los archivos seleccionados. La información mantenida del producto describe edición individual gratuita y edición por lotes incluida en la compra única Pro opcional. Las fichas oficiales incluyen pista y disco entre los campos editables; consulta los detalles de tu plataforma.

La aplicación no identifica la edición correcta ni inventa posiciones fiables. Define primero la lista y las reglas, mantén la copia de seguridad fuera de la selección, guarda expresamente y comprueba una muestra. Según las notas de la versión 2.5.1 en App Store, al guardar en iOS se actualiza el original seleccionado si su ubicación permite la escritura; de lo contrario, TagWeaver pregunta dónde guardar una copia. Haz una copia de seguridad aparte antes de editar y comprueba la ubicación del archivo guardado.

## Referencias

- [ID3.org: marcos de ID3v2.4.0](https://id3.org/id3v2.4.0-frames): definiciones de `TRCK`, `TPOS` y totales opcionales tras la barra.
- [ID3.org: estructura de ID3v2.4.0](https://id3.org/id3v2.4.0-structure): estructura de etiquetas y marcos que contienen metadatos.
- [ID3.org: especificación ID3v2.3.0](https://id3.org/id3v2.3.0): definiciones anteriores para archivos y herramientas de esa versión.
- [TagWeaver en App Store](https://apps.apple.com/app/id6759609875): ficha oficial para iOS.
- [TagWeaver en Google Play](https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2): ficha oficial para Android.

## Conclusión

Trata la posición de pista y la de disco como hechos separados. Confirma la edición, planifica los valores, conserva originales y prueba los límites. Totales, ceros iniciales, nombres de archivo y presentación son convenciones secundarias. La base fiable son `TRCK` y `TPOS` correctos y un proceso reversible.

## Preguntas frecuentes

### ¿El segundo disco debe volver a la pista 1?

Normalmente sí, al conservar secuencias impresas independientes. Guarda la pista en `TRCK` y distingue el disco con `TPOS`. Documenta cualquier secuencia personal continua.

### ¿Son obligatorios los totales `4/11` y `2/3`?

No. Son opcionales y requieren confirmar la edición y las cantidades completas. Una posición correcta es más segura que un total erróneo.

### ¿Todos los reproductores ordenarán bien el álbum?

No hay un comportamiento universal. Cada destino decide cómo leer, agrupar, almacenar en caché y mostrar los datos. Prueba una copia representativa en la aplicación concreta.

### ¿Los nombres de archivo pueden sustituir las etiquetas?

Ayudan a inspeccionar carpetas, pero no demuestran que se hayan escrito `TRCK` y `TPOS`. Mantén los cambios de nombre separados y reversibles.

### ¿Cambiar estas etiquetas afecta a la calidad del audio?

Las posiciones son metadatos, no muestras sonoras. La edición en sí no mejora ni recodifica el sonido, pero conserva los originales y verifica la salida real del editor.
