---
title: "Cómo probar un archivo multimedia convertido antes de sustituir el original"
card_title: "Cómo probar un archivo multimedia convertido antes de sustituir el original"
slug: "test-converted-media-before-replacing-original"
category: "media"
language: "es"
description: "Comprueba que el audio y el vídeo convertidos estén completos, se reproduzcan bien y conserven los metadatos necesarios. Pruébalo en la aplicación prevista y verifica la copia del original."
status: "review"
topic_id: "TOPIC-0069"
search_intent: "workflow"
primary_keyword: "probar un archivo multimedia convertido"
secondary_keywords: "comprobar audio convertido|prueba de reproducción de vídeo|metadatos multimedia|copia de seguridad del original"
related_apps: "Quivra"
tags: "probar un archivo multimedia convertido|comprobar audio convertido|prueba de reproducción de vídeo|metadatos multimedia|copia de seguridad del original"
short_answer: "Conserva el original, inspecciona el archivo exportado, reproduce fragmentos representativos en la aplicación de destino y comprueba las pistas y los metadatos necesarios. Investiga las diferencias antes de aceptar el resultado. Una prueba por muestreo satisfactoria no justifica borrar el único original."
canonical_url: "https://onnellab.com/blog/es/test-converted-media-before-replacing-original/"
image_specs: "Guarda el original|Comprueba los cambios|Reproduce en el destino|Anota y haz una copia de seguridad"
---

# Cómo probar un archivo multimedia convertido antes de sustituir el original

La conversión termina y el archivo nuevo se abre. Es un buen comienzo, pero no demuestra que el final esté intacto, que el audio previsto siga presente o que la aplicación de destino maneje el archivo correctamente. Antes de sustituir una copia de trabajo, comprueba esas cuestiones por separado y conserva una forma de recuperar el original.

## Pregunta

¿Cómo debo probar un archivo multimedia convertido antes de sustituir el original?

## Respuesta breve

Conserva el original, inspecciona el archivo exportado, reproduce fragmentos representativos en la aplicación de destino y comprueba las pistas y los metadatos necesarios. Investiga las diferencias antes de aceptar el resultado. Una prueba por muestreo satisfactoria no justifica borrar el único original.

## Define qué debe conservar un buen resultado

Una **comprobación de aceptación** es una comparación entre el archivo de salida y los requisitos que has anotado para su uso previsto. No garantiza que el archivo nuevo sea idéntico al de origen.

Anota el nombre del archivo de origen, el nombre del archivo de salida, la aplicación o el dispositivo de destino y el contenido que debe conservarse. En una grabación de audio, eso puede incluir las primeras y las últimas palabras, una voz inteligible y los canales necesarios. En un vídeo, incluye imagen, sonido y su sincronización. Si importan los subtítulos, los capítulos, las carátulas o las etiquetas de metadatos, añádelos a la lista en lugar de dar por hecho que se transferirán.

Distingue los cambios intencionados de los fallos. Extraer audio de un vídeo elimina la imagen de forma deliberada. La falta de imagen solo es un problema cuando el resultado previsto seguía siendo un vídeo. Esta guía empieza después de la conversión; si todavía no has elegido el formato de destino, consulta la guía relacionada que aparece más abajo.

## Tres comprobaciones responden a preguntas distintas

| Comprobación | Evidencia útil | Lo que no permite demostrar |
| --- | --- | --- |
| Inspeccionar las propiedades del archivo | La duración, los flujos y los metadatos disponibles cumplen tus requisitos | Todos los fragmentos se reproducen correctamente |
| Reproducir en el destino | La aplicación que realmente recibirá el archivo maneja los fragmentos probados | Los fragmentos no probados u otro dispositivo funcionarán |
| Verificar la suma de comprobación de una copia de seguridad | El archivo copiado coincide con la huella de sus bytes registrada | La conversión tiene el sonido o la imagen adecuados |

Un **flujo** es un componente multimedia individual, como una pista de audio o vídeo. Una herramienta de información de archivos puede identificar esos componentes. La [documentación de ffprobe de FFmpeg](https://ffmpeg.org/ffprobe.html) describe la inspección de contenedores, flujos y etiquetas. Utiliza una herramienta de inspección independiente si tu conversor no muestra esos detalles; un informe de inspección no sustituye a una prueba de escucha o visualización.

## Flujo de trabajo recomendado

1. **Mantén el archivo de origen separado.** Usa carpetas distintas para el original y el resultado, o nombres de archivo inequívocos. Registra qué archivo has convertido. No sobrescribas el único original ni permitas que una limpieza lo elimine durante la comprobación.
2. **Abre el propio archivo exportado.** Localízalo en el gestor de archivos y confirma su nombre y ruta. Una vista previa del conversor o una entrada antigua de la biblioteca del reproductor podría apuntar a un archivo distinto. Anota las versiones del conversor y del reproductor para que la comprobación pueda repetirse de forma útil.
3. **Compara las propiedades importantes.** Comprueba la duración aproximada, las pistas de audio y vídeo previstas, la información de los canales, las dimensiones de imagen en los vídeos y las etiquetas necesarias. El tamaño del archivo, por sí solo, no mide la calidad. Una diferencia grande de duración requiere investigación; una pequeña puede deberse a cómo se informa de la duración o al comportamiento del formato. Por eso, compara también el principio y el final reales.
4. **Reproduce fragmentos representativos.** Escucha o mira el principio, la parte central y el final. Incluye una voz tenue, un fragmento de volumen alto, un cambio de escena u otro contenido exigente de tu archivo. Avanza y retrocede en la reproducción. En un vídeo, observa a alguien hablando o un impacto visible para evaluar la sincronización del sonido; en audio, presta atención a contenido ausente, distorsión y silencios inesperados.
5. **Usa el destino real.** Importa el archivo de salida en el reproductor, editor o dispositivo que piensas utilizar. Prueba allí la selección de las pistas necesarias y los subtítulos, cuando corresponda. Si es apropiado subir ese archivo al servicio y este procesa los archivos recibidos, inspecciona también el resultado de ese procesamiento. Superar una prueba en el conversor no sustituye esta comprobación.
6. **Registra el resultado y conserva copias de recuperación.** Anota el archivo de salida, el destino, los fragmentos comprobados y cualquier limitación. Las grabaciones importantes de ocasiones irrepetibles merecen una escucha o visualización completa; el muestreo deja intervalos sin probar. Mantén una copia de seguridad del original almacenada por separado y verifica que puedes recuperarla antes de reorganizar los archivos de trabajo.

![Pasos para comprobar un archivo multimedia convertido](/blog-assets/es/test-converted-media-before-replacing-original/workflow-diagram.svg)

## Una pequeña hoja de control facilita la investigación de los fallos

Este es un ejemplo hipotético, no una prueba de una aplicación o un dispositivo: una entrevista exportada empieza con claridad, pero pierde la última frase. Registra los nombres del archivo de origen y del archivo de salida, la posición aproximada y si ese mismo fragmento se reproduce en el original. Conserva ambos archivos mientras investigas. «La última frase falta en este archivo de salida» resulta más útil que «la calidad de la conversión es mala».

| Observación | Siguiente comprobación |
| --- | --- |
| El archivo de salida termina demasiado pronto | Comparar el final del original y confirmar después que se ha abierto la exportación más reciente |
| El vídeo no tiene sonido audible | Comprobar el audio original, las pistas de audio del resultado, si el reproductor está silenciado y la pista seleccionada |
| El sonido se desfasa respecto a la imagen | Comparar un evento al principio y otro hacia el final en el original y en el destino |
| Faltan etiquetas o carátulas | Inspeccionar los campos del archivo de salida por separado de lo que muestra el reproductor |
| Un reproductor funciona y otro falla | Anotar el destino y revisar las entradas que admite antes de volver a convertir |

Cambia un solo ajuste relevante o el método de conversión cada vez, si tu herramienta lo permite. Vuelve a exportar desde el original y repite la comprobación que falló y las pruebas básicas de reproducción. Convertir repetidamente un resultado con pérdidas no es una forma de recuperar los detalles ausentes del original.

## Qué demuestra una suma de comprobación y qué no

Una suma de comprobación es un valor calculado a partir de los bytes de un archivo. Herramientas como las [utilidades SHA-2 de GNU](https://www.gnu.org/s/coreutils/manual/html_node/sha2-utilities.html) calculan y verifican esos valores. Compara un original guardado con su copia de seguridad, o un archivo de salida aceptado con una copia de ese mismo archivo. Utiliza el mismo algoritmo para ambos archivos, por ejemplo SHA-256. En esas condiciones, un valor distinto señala una diferencia en los bytes que debe investigarse.

No esperes que el original y un archivo derivado mediante conversión tengan la misma suma de comprobación. Normalmente, sus bytes son distintos. Una suma de comprobación coincidente de la copia de seguridad ayuda a verificar la integridad de la copia; no evalúa el sonido, la imagen, si está todo el contenido elegido ni la idoneidad para un destino.

## Cómo usar ONNELLAB

Si necesitas una de sus conversiones predefinidas, [Quivra](/apps/quivra/) es una herramienta de conversión opcional. Su [ficha para iOS](https://apps.apple.com/us/app/quivra-mp3-media-converter/id6759565093) y su [ficha para Android](https://play.google.com/store/apps/details?id=com.onnellab.quivra2) indican la conversión de WAV y M4A a MP3, la extracción de audio de MP4 a MP3 y la conversión de MOV a MP4. El formato de entrada determina automáticamente el formato de salida.

Realiza las inspecciones y las pruebas de reproducción en el destino que describe este artículo con herramientas independientes y adecuadas. Las conversiones indicadas no demuestran que se conserven todas las pistas o todos los campos de metadatos. Confirma que la conversión se ajusta a tu tarea antes de usar la aplicación.

## Guía relacionada

- [Elegir un formato de salida multimedia antes de convertir](https://onnellab.com/blog/es/choose-media-output-format-before-conversion/)

## Referencias

- [FFmpeg: documentación de ffprobe](https://ffmpeg.org/ffprobe.html)
- [GNU Coreutils: utilidades SHA-2](https://www.gnu.org/s/coreutils/manual/html_node/sha2-utilities.html)
- [FFmpeg: copia de flujos y transcodificación](https://ffmpeg.org/ffmpeg.html#Streamcopy)

## Conclusión

Para probar un archivo multimedia convertido, compáralo con una lista breve de requisitos, inspecciónalo y reprodúcelo en el destino previsto. Registra lo que has comprobado y lo que queda sin probar. Aceptar una copia para entregar y decidir cómo archivar el original son decisiones distintas; conserva el original cuando perderlo suponga un coste importante.

## Preguntas frecuentes

### ¿Basta con abrir el archivo?

No. Abrirlo no comprueba el final, todas las pistas ni cada fragmento. Inspecciona las propiedades necesarias y reproduce el contenido importante.

### ¿La duración tiene que ser exactamente igual?

No siempre. El redondeo mostrado y el comportamiento del formato pueden producir pequeñas diferencias. Investiga el contenido ausente o una discrepancia considerable en vez de confiar en una tolerancia de tiempo universal.

### ¿Un archivo más pequeño significa una conversión peor?

El tamaño por sí solo no responde a esa pregunta. Evalúa el archivo según el uso previsto, el contenido necesario y la reproducción real.

### ¿Puedo borrar el original después de una prueba por muestreo satisfactoria?

El muestreo deja partes sin comprobar. Conserva una copia de seguridad recuperable del original, sobre todo para grabaciones irreemplazables o material que quizá edites más adelante.
