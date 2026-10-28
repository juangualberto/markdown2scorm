# Inspección de los materiales originales

Se inspeccionaron antes de implementar el conversor los tres originales:
`SR-tarea08-pt.elp`, `SR-tarea08-pt.zip` y el manuscrito completo de 694 líneas.
Los SHA-256 previos se guardan en `dist/original-sha256.json`; pytest comprueba
que todos los originales, incluidas las figuras, permanecen intactos.

## eXeLearning

El ELP es un ZIP con seis entradas: `plantilla.pkt`, `img0.png`, `diagrama.png`,
`content.data`, `contentv3.xml` y `content.xsd`. Se leyó el XML como datos; no se
deserializó `content.data` ni se ejecutó ningún componente del original.

El manifiesto del SCORM de referencia usa:

- Content Packaging: `http://www.imsproject.org/xsd/imscp_rootv1p1p2`.
- ADL: `http://www.adlnet.org/xsd/adlcp_rootv1p2`.
- Metadatos: `ADL SCORM`, versión `1.2`; metadatos adicionales en `imslrm.xml`.
- Una organización jerárquica, `item` anidados y `identifierref` a recursos.
- Recursos `webcontent`, `adlcp:scormtype="sco"`, asociados a páginas HTML.
- Páginas, imágenes, adjunto Packet Tracer, CSS y JavaScript en la raíz del ZIP.
- `imsmanifest.xml` en la raíz, referencias relativas y esquemas XSD locales.

La página `index.html` carga `base.css`, `content.css`, jQuery, `common.js`,
`SCORM_API_wrapper.js`, `SCOFunctions.js` y `_fpd_js.js`. Llama a `loadPage()`
al cargar y `unloadPage()` al salir. El wrapper localiza la API; SCOFunctions
inicia la sesión, consulta el estado, calcula tiempos y guarda/finaliza.
El generador implementa un runtime independiente, sin copiar estos scripts.

`nav.css` contiene un árbol lateral y reglas de menús. El HTML SCORM observado
usa el contenido sin ese árbol. No se incorpora navegación lateral al generador.

## FPD-MEDU y derechos de uso

`config.xml` identifica el estilo FPD-MEDU, versión 2019, compatibilidad eXe 2.4,
por José Ramón Jiménez Reyes para TodoFP, Ministerio de Educación. Declara
**CC BY-SA 3.0**. La licencia CC BY-SA 4.0 de la actividad en `index.html` es
independiente de la licencia del estilo.

Se adaptó únicamente lo necesario de `content.css`: familia Helvetica,
título azul `#0087FF` con subrayado, azules `#044085`, `#C3DCF7` y `#153152`,
bordes de tabla `#D4E0EE`, fondo `#FCFDFE`, citas `#F1D8C8` / `#5E2A0D` y
presentación de figuras/código. La adaptación de estilo y su plantilla se
publican bajo CC BY-SA 3.0 con `NOTICE.txt` incluido en cada exportación.
Se cambian márgenes y tamaños para pantallas pequeñas, se elimina la justificación
forzada y se usan selectores HTML5. Los enlaces se oscurecen para mejorar contraste.
No se copian logotipos, iconos, fuentes, JavaScript ni contenido pedagógico del ejemplo.
No es una réplica exacta de todos los iDevices de eXeLearning.

Los cuatro esquemas originales necesarios conservan sus avisos IMS/ADL. Para
validar se leen en una carpeta temporal desde el ZIP suministrado, sin modificarlos
ni incorporarlos a la distribución Python. Un esquema agregador local importa CP
 y ADL para comprobar también los atributos SCORM. No se valida contra SCORM 2004.

## Manuscrito

Archivo: `test/manuscrito/01-Introduccion-al-analisis-forense.md`.
Título: **Introducción al análisis forense digital**.

- H1: 1; H2: 6; H3: 54; H4–H6: 0. Total: 61 encabezados.
- 60 epígrafes más Introducción: 61 SCO. El primer H2 no tiene texto propio;
  recibe una página con su título y conserva sus hijos en el manifiesto.
- Seis imágenes PNG, referencias `../figuras/figura1.1.png` a `figura1.6.png`;
  todas existen en `test/figuras`. Se autoriza esa carpeta con `--assets-dir`.
- Una tabla de cuatro columnas y seis filas de datos.
- Dos citas, negritas, cursivas, un código en línea y doce enlaces bibliográficos.
- Sin bloques de código, listas Markdown, notas al pie ni fórmulas matemáticas.
  Estas funciones se verifican con pruebas unitarias separadas.
- Portada anterior al H1 con órdenes LaTeX (`\newpage`, `\vspace`, `\begin{center}`,
  etc.): se preservan como texto, con diagnóstico; no se interpreta maquetación TeX.
- Anotación Pandoc `{.unnumbered}` en Referencias: se reconoce como metadato,
  no se muestra como parte del título ni se añade numeración automática.
- No hay enlaces entre apartados en este manuscrito; se verifican aparte.

La prueba integral compara la secuencia completa de tokens de contenido antes
y después de la partición y comprueba la presencia de cada bloque de texto en
su página. La tabla e imágenes también se cuentan en el HTML, y los bytes de
las imágenes empaquetadas se comparan con sus originales.

## Referencias técnicas consultadas

- [Moodle: SCORM FAQ](https://docs.moodle.org/en/SCORM_FAQ).
- [Plugins markdown-it: dollarmath](https://mdit-py-plugins.readthedocs.io/en/latest/_modules/mdit_py_plugins/dollarmath/index.html).
- Esquemas CP/ADL y runtime del ZIP original proporcionado.

La inspección y la validación con esquemas no equivalen a una importación y
una sesión real de alumno en Moodle.
