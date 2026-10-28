# Markdown a SCORM 1.2

`markdown2scorm` convierte documentos Markdown en paquetes SCORM 1.2 autónomos,
con un SCO por apartado, un árbol jerárquico para Moodle, imágenes y adjuntos
locales, resaltado de código y matemáticas sin CDN. Ofrece las plantillas
`default` y `fpd-medu` y una API Python separada de la CLI.

El ejemplo real está en
[`dist/01-Introduccion-al-analisis-forense-scorm12.zip`](dist/01-Introduccion-al-analisis-forense-scorm12.zip).
El [informe de entrega](dist/validation-report.md) recoge las comprobaciones
realmente ejecutadas. **No se ha probado la importación en una instancia real
de Moodle.** La validación automatizada, incluido XSD y API simulada, no la sustituye.

## Requisitos e instalación en Linux

- Python 3.11 o superior con `venv` y `pip`.
- Node.js 18 o superior para las pruebas del runtime; no es necesario para convertir.
- Un navegador moderno con MathML nativo para las fórmulas (por ejemplo, Chromium,
  Firefox o Safari actuales). La exportación no necesita un navegador ni LaTeX.
- Playwright y Chromium son opcionales para las pruebas visuales.

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m markdown2scorm --help
markdown2scorm --help
```

Para uso sin herramientas de desarrollo: `python -m pip install .`.
Las dependencias se declaran en `pyproject.toml`; no es necesario mantener otro
`requirements.txt`. `dist/installed-versions.txt` registra el entorno de la entrega.

Para distribuir un wheel:

```bash
python -m build
python -m pip install dist/markdown2scorm-1.0.0-py3-none-any.whl
```

Las plantillas y el runtime se incluyen como datos del paquete Python bajo
`src/markdown2scorm/`; funcionan también fuera de la carpeta del repositorio.

## Exportación del manuscrito real

```bash
python -m markdown2scorm \
  ./test/manuscrito/01-Introduccion-al-analisis-forense.md \
  --assets-dir ./test/figuras \
  --template fpd-medu \
  --output ./dist/tema01.zip \
  --validate
```

Para conservar los HTML y ver cada recurso resuelto:

```bash
markdown2scorm test/manuscrito/01-Introduccion-al-analisis-forense.md \
  --assets-dir test/figuras --template fpd-medu \
  --output dist/01-Introduccion-al-analisis-forense-scorm12.zip \
  --validate --verbose --keep-build
```

Cada conversión crea un informe `NOMBRE-report.md` al lado del ZIP. El directorio
intermedio tiene un nombre único `NOMBRE.build-*`, que se muestra en el registro.
El ZIP contiene `imsmanifest.xml` en su raíz, `pages/`, `assets/`, `theme/` y
`runtime/`. Los nombres y el orden del ZIP son deterministas: con las mismas
entradas y versiones de dependencias, se obtienen los mismos bytes.

La exportación se prepara en una carpeta temporal y sustituye el ZIP de destino
solo después de validarlo. Si falla, conserva el ZIP anterior. No modifica las
fuentes Markdown ni las figuras.

| Argumento | Uso |
|---|---|
| `input` | Uno o varios Markdown, en el orden indicado |
| `--output` | ZIP de salida; por defecto `salida.zip` |
| `--template` | `default`, `fpd-medu` o plantilla instalada |
| `--assets-dir` | Directorio adicional autorizado; repetible |
| `--title` | Cambia el título de la organización, manteniendo los epígrafes |
| `--verbose` | Diagnósticos de conversión y recursos |
| `--validate` | Muestra las comprobaciones; la integridad se valida siempre |
| `--keep-build` | Conserva páginas, CSS y runtime intermedios |
| `--allow-missing-assets` | Sustituye ausencias por texto y emite advertencias |
| `--check` | Valida un ZIP existente sin exportar |
| `--schema` | XSD local adicional para validar el manifiesto |

Código de salida: `0` si termina correctamente, `1` ante errores de conversión o
validación, `2` ante argumentos incorrectos. Los diagnósticos van a stderr.

Varios documentos:

```bash
markdown2scorm parte1.md parte2.md --title 'Curso completo' --output curso.zip
```

Cada documento conserva su propio H1 y se agrupa bajo un nodo de capítulo. Los
enlaces `parte2.md#apartado` se resuelven si ese archivo se incluyó como entrada.
Un Markdown enlazado que no figure entre las entradas se trata como adjunto.

## Encabezados y asignación de contenido

El parser `markdown-it-py` analiza una única vez cada documento. No se buscan
encabezados con expresiones regulares. Las definiciones de enlaces y notas al
pie se conservan al separar las páginas.

| Markdown | Organización SCORM |
|---|---|
| Primer H1 `#` | Título general |
| H2 `##` | Nodo de primer nivel |
| H3 `###` | Segundo nivel |
| H4, H5 y H6 | Tercero, cuarto y quinto nivel |

El contenido previo al primer H2, incluida una posible portada anterior al H1,
forma la página **Introducción**. Cada epígrafe recibe su propia página y recurso
SCO; un padre conserva su contenido propio y sus hijos. Un epígrafe vacío tiene
una página con su título. No se copia el contenido de los hijos al padre.

Los saltos de nivel se normalizan colgando el nodo del antecesor existente más
próximo de nivel inferior; se registra una advertencia sin inventar nodos. Los
H1 múltiples son un error con números de línea. Sin H1 se usa el nombre del
archivo y se advierte. Los encabezados dentro de código no forman nodos. Los
encabezados contenidos en citas/listas permanecen dentro de su bloque, sin romperlo.

No se añade numeración. Los títulos repetidos tienen anclas únicas (`sección`,
`sección-1`, etc.); los identificadores SCORM son ASCII y derivan de esas anclas.
Los anclajes conservan Unicode; se reconocen también encabezados Setext.
`{.unnumbered}` se interpreta como metadato Pandoc de un encabezado.

## Markdown técnico, código y matemáticas

Se admiten párrafos, énfasis, tachado, listas anidadas, tablas, citas, enlaces,
imágenes, líneas horizontales, Unicode, código en línea y bloques cercados o
sangrados. Pygments resalta el código con CSS local. El contenido, tabs, espacios
y líneas vacías del código se conservan tras la normalización estándar de
saltos de línea de CommonMark.

Las notas `[^nota]` se resuelven globalmente: sus definiciones se sitúan al final
del documento, en la última página; los enlaces y retornos se ajustan al dividir
el contenido. Las URL bibliográficas sin delimitadores se convierten en enlaces.

`$...$`, `$$...$$`, `\(...\)` y `\[...\]` se convierten previamente con
`latex2mathml` a MathML nativo. No se carga MathJax, KaTeX ni fuentes remotas.
Una fórmula que no se pueda interpretar se muestra literalmente y produce una
advertencia. No se ejecuta TeX ni se permite que una fórmula cree enlaces activos.
No se implementan documentos LaTeX completos, macros de usuario, TikZ ni entornos
arbitrarios: las órdenes de maquetación de la portada real se conservan como texto.

## Imágenes, adjuntos y permisos de lectura

Para una referencia local, se intenta primero la ruta respecto al Markdown y
después cada `--assets-dir`, usando la ruta indicada o su nombre base. La búsqueda
alternativa no es recursiva. Si varias carpetas ofrecen candidatos distintos,
se produce un error de ambigüedad. La ruta original tiene prioridad.

Los directorios autorizados son los de los Markdown de entrada y los indicados
explícitamente con `--assets-dir`. Para imágenes en una carpeta hermana como
`../figuras`, hay que autorizar esa carpeta. No se autoriza automáticamente todo
el directorio padre. Las rutas absolutas, escapes fuera de esos directorios y
symlinks que salgan de ellos se rechazan, incluso con `--allow-missing-assets`.

Se conservan los bytes y extensiones de PNG, JPEG, GIF, SVG estático y WebP.
Los nombres con espacios o Unicode se admiten mediante la sintaxis Markdown
`![Texto](<figura con espacios.png>)`. Se copian también PDF, ZIP, `.pkt` y otros
adjuntos pasivos. Un nombre derivado de SHA-256 evita colisiones y reutiliza
archivos idénticos con la misma extensión. El HTML conserva el texto alternativo;
las imágenes solas se presentan como figuras con pie basado en ese texto.

Las ausencias provocan error por defecto. La excepción explícita muestra un
marcador de imagen ausente o un enlace sin destino, sin crear rutas rotas. Los
recursos remotos no se descargan: las imágenes remotas se muestran como referencia
textual con advertencia. Los enlaces web siguen disponibles cuando haya conexión,
pero no son necesarios para presentar el contenido del paquete.

## Seguridad

El HTML embebido se muestra escapado. No hay opción para habilitar HTML arbitrario.
Se filtran protocolos activos mediante el parser y el resolver, y la plantilla
usa autoescape Jinja2 y una política CSP. Los SVG con scripts, manejadores, estilos
activos o dependencias externas se rechazan sin modificarlos. No se empaquetan
adjuntos ejecutables, HTML, JavaScript ni CSS suministrados por el manuscrito.

El validador inspecciona el ZIP sin extraerlo y rechaza traversal, rutas absolutas,
symlinks, duplicados, archivos de desarrollo, JavaScript inesperado, DTD y entidades
XML. Limita la inspección a 20000 archivos y 512 MiB descomprimidos. No es un
antivirus para documentos PDF o ZIP adjuntos: el autor debe conocer sus materiales.
Las plantillas instaladas son código de confianza administrado por el mantenedor.

## Plantillas y adaptación FPD-MEDU

```text
src/markdown2scorm/templates/
├── default/
│   ├── page.html
│   ├── base.css
│   └── style.css
└── fpd-medu/
    ├── page.html
    ├── style.css
    └── NOTICE.txt
```

`base.css` proporciona diseño adaptable, tablas desplazables, imágenes fluidas,
código y estilos comunes. La capa `style.css` aplica la identidad visual.
FPD-MEDU adapta los colores, fuentes de sistema, encabezados subrayados y tablas
del original suministrado, conservando atribución y CC BY-SA 3.0 en el paquete.
El [análisis de referencia](docs/reference-analysis.md) documenta decisiones y
licencias. No se reutiliza el JavaScript de eXeLearning ni su árbol lateral.

Para modificar FPD-MEDU, edite únicamente `templates/fpd-medu/style.css` y, si hace
falta, `page.html`. Mantenga el enlace a `NOTICE.txt`, la variable `content`,
los CSS locales y `../runtime/scorm12.js`. No cambie el parser ni el manifiesto.

Para crear un estilo, copie una carpeta, adapte `page.html` y `style.css`, y
selecciónela por nombre con `--template`. Jinja2 recibe `course`, `node`, `content`
y `template`; `content` es el HTML seguro producido por el renderer. Añada un
`NOTICE.txt` si corresponde. Este sistema mínimo utiliza CSS y fuentes del sistema;
para agregar imágenes de plantilla hay que ampliar expresamente la copia de
recursos en `exporter.py` y su validación. No se copian carpetas arbitrarias.

## SCORM y navegación

El manifiesto utiliza los namespaces CP 1.1.2 y ADL SCORM 1.2, con metadatos
`ADL SCORM / 1.2`, una organización y recursos independientes. Todos los archivos
se declaran; los recursos comunes se comparten mediante `dependency`.

El runtime busca `window.API` en padres y opener con protección ante frames de
otro origen. Inicializa una sola vez, consulta estado y modo, marca `completed`
tras la carga si las imágenes están disponibles, guarda tiempo de sesión en
`HHHH:MM:SS.SS` y hace commit/finish una sola vez al salir. Conserva `completed`,
`passed` y `failed`; no cambia estados en modo review/browse ni genera notas.
Guarda al ocultar la página. `beforeunload` solo guarda porque puede cancelarse;
`pagehide`/`unload` finalizan, salvo entrada en caché bfcache. Los errores del LMS
se registran sin impedir la lectura. Sin API se presenta HTML normal.

La navegación principal corresponde a Moodle. No hay un segundo árbol dentro
de los SCO. Un enlace hacia otro SCO abre una pestaña de consulta con
`?preview=1`, `noopener` y seguimiento desactivado. Para registrar progreso de
ese apartado, el alumno debe seleccionarlo en el árbol de Moodle. Esto evita
atribuir el apartado de destino a la sesión SCORM del apartado de origen.
Los enlaces dentro de la misma página siguen siendo anclas normales.

## Importar y verificar en Moodle

1. Active la edición del curso y añada una actividad **Paquete SCORM**.
2. Suba el ZIP completo, sin descomprimirlo ni volver a empaquetarlo.
3. Permita mostrar la estructura del paquete y guarde la actividad.
4. Entre con un usuario alumno: revise el árbol, abra varios padres e hijos,
   salga y vuelva a entrar. Compruebe que el contenido y las figuras cargan.
5. Revise los informes SCORM: estado de cada SCO y tiempo registrado. Compruebe
   que un SCO completado sigue completado y que no aparecen calificaciones ficticias.
6. Pruebe los enlaces de consulta, cierre de pestaña y reanudación del intento.

Moodle documenta soporte de SCORM 1.2 en su
[FAQ oficial](https://docs.moodle.org/en/SCORM_FAQ). La configuración de finalización
agregada y los informes depende de la versión y ajustes del curso. El proyecto
no declara una prueba real de importación ya realizada.

## Pruebas y validación

```bash
python -m pytest -q --junitxml=dist/pytest-results.xml
markdown2scorm dist/tema01.zip --check
```

La suite comprueba jerarquía H1–H6, introducción, duplicados, saltos, padres con
contenido, código, tablas, listas, notas, matemáticas, enlaces entre páginas y
archivos, seguridad, recursos ambiguos, formatos, ZIP corruptos, manifiesto y
20 escenarios del runtime con API simulada ejecutada por Node.js. La prueba
integral usa obligatoriamente el manuscrito real, compara todos sus tokens de
contenido, sus textos por página y los bytes de sus imágenes.

Para validar además contra los esquemas originales CP y ADL suministrados:

```bash
python scripts/validate_reference.py dist/tema01.zip --reference SR-tarea08-pt.zip
```

El script lee cuatro XSD originales en una carpeta temporal y no los modifica ni
redistribuye. También puede proporcionar un esquema local con `--schema ruta.xsd`.
Sin XSD se señala expresamente que solo se ejecutaron comprobaciones estructurales.

Prueba visual opcional, usando el directorio mostrado por `--keep-build`:

```bash
python -m playwright install chromium
python scripts/visual_check.py dist/tema01.build-XXXXXXXX --output dist/screenshots
```

Se sirven los HTML por HTTP local y se abre cada página a 1280 y 390 píxeles.
Se bloquea la red externa, se comprueban imágenes, desbordamiento global,
ausencia de árbol lateral y errores JavaScript, y se guardan capturas de la
introducción, un apartado con figura y otro con tabla. En el manuscrito real,
la figura y la tabla están en apartados distintos.

## Arquitectura y API

- `models.py`: curso, documentos y árbol de nodos.
- `parser.py`: sintaxis Markdown, contenido por nodo e identificadores.
- `assets.py`: resolución, autorización y copia de recursos.
- `renderer.py`: HTML seguro, Pygments, MathML y plantillas Jinja2.
- `manifest.py`: organización jerárquica y recursos SCORM 1.2.
- `runtime/scorm12.js`: comunicación con el LMS.
- `exporter.py`: construcción temporal y publicación atómica del ZIP.
- `validator.py`: inspección estructural, rutas y XSD opcional.
- `report.py`: evidencia de cada exportación.
- `cli.py`: argumentos y diagnósticos.

```python
from pathlib import Path
from markdown2scorm.exporter import export

resultado = export(
    [Path('test/manuscrito/01-Introduccion-al-analisis-forense.md')],
    Path('dist/tema01.zip'),
    template='fpd-medu',
    assets_dirs=[Path('test/figuras')],
)
assert resultado.validation.valid
```

## Limitaciones y ampliaciones

- No reproduce todos los iDevices ni la maquetación TeX; el estilo es una
  adaptación fiel a los elementos necesarios, no una exportación de eXeLearning.
- No hay evaluación, calificaciones, SCORM 2004 ni interfaz gráfica.
- El estado completed representa acceso y carga, no comprensión ni lectura completa.
- La nota al pie global queda en la última página; enlaces entre SCO son consultas.
- MathML requiere navegador con soporte; LaTeX no reconocido se conserva y advierte.
- La validación HTML comprueba estructura y enlaces, no certifica todo HTML5 con Nu.
- La validación XSD no sustituye las pruebas del LMS ni certificación ADL.
- Futuro: actividades opcionales, plantillas externas con recursos declarados,
  notas por página, más metadatos, GUI y ensayos de interoperabilidad con Moodle.

Código Python, runtime y plantilla default: MIT. Adaptación FPD-MEDU: CC BY-SA 3.0.
El manuscrito y sus figuras mantienen sus propios derechos.
