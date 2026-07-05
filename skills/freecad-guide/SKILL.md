---
name: freecad-guide
description: Guía de interacción avanzada y mejores prácticas de modelado paramétrico, FEM y TechDraw en FreeCAD.
---

# Guía de Modelado Avanzado y Buenas Prácticas en FreeCAD

Esta guía consolida las lecciones aprendidas y metodologías optimizadas para programar e interactuar con FreeCAD de manera robusta, con calidad de ingeniería, y compatibilidad total con entornos de automatización / headless (como CI/CD o ejecución desde línea de comandos sin GUI).

---

## 1. Modelado Paramétrico mediante Sketcher

Evita construir geometrías complejas únicamente con primitivas sólidas (CSG). Utiliza el banco de trabajo `Sketcher` para crear bocetos 2D restringidos y luego realiza operaciones de extrusión o revolución.

### Vinculación y Soporte de Bocetos en Python (API de FreeCAD):
* **Propiedad de Soporte:** No utilices `sketch.Support`, ya que genera un `AttributeError` en las versiones modernas de FreeCAD. En su lugar, utiliza `AttachmentSupport` pasándole una tupla del plano/cara y la referencia de mapeo.
* **Modo de Mapeo:** Define siempre `sketch.MapMode = "FlatFace"` (u otro modo aplicable) para alinear el boceto correctamente al plano.

```python
import FreeCAD as App
import Part
import Sketcher
import PartDesign

doc = App.activeDocument()
body = doc.addObject("PartDesign::Body", "Body")
sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
body.addObject(sketch)

# Mapear el boceto al plano XY de forma segura
xy_plane = doc.Origin.OriginFeatures[3] # XY_Plane
sketch.AttachmentSupport = [(xy_plane, "")]
sketch.MapMode = "FlatFace"

# Agregar líneas y restricciones
p1 = App.Vector(0, 0, 0)
p2 = App.Vector(20, 0, 0)
sketch.addGeometry(Part.LineSegment(p1, p2))
sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
doc.recompute()
```

---

## 2. Integración de Tablas de Ingeniería (Spreadsheet)

Asocia parámetros de diseño, propiedades físicas y resultados de simulación a hojas de cálculo nativas para un diseño paramétrico bidireccional.

### Reglas Críticas para Fórmulas y Valores:
1. **Prefijo de Fórmulas:** Toda fórmula en celdas de Spreadsheet debe comenzar estrictamente con el signo `=` (por ejemplo, `=width_alias * 2`). Sin el signo `=`, la expresión se guardará como texto plano (anteponiendo una comilla simple `'`) y no se evaluará.
2. **Evaluación de Celdas:**
   * Para obtener la **fórmula** en sí, utiliza `sheet.getContents("B2")`.
   * Para obtener el **valor evaluado** (número, cadena, etc.), utiliza `sheet.get("B2")` o accede mediante el diccionario de celdas `sheet.cells["B2"]`.
3. **Recomputación:** Llama siempre a `doc.recompute()` después de modificar valores de Spreadsheet para propagar los cambios a las geometrías enlazadas.

```python
import Spreadsheet
sheet = doc.addObject("Spreadsheet::Sheet", "Datos_Ingenieria")
sheet.set("B1", "30.0")
sheet.setAlias("B1", "width_alias")

# Correcto: Fórmula con '=' al inicio
sheet.set("B2", "=width_alias * 2") 
doc.recompute()

# Obtención del valor evaluado (retorna 60 de tipo int/float)
valor_evaluado = float(sheet.get("B2"))
```

---

## 3. Acotación y Dibujo Técnico Inteligente (TechDraw)

TechDraw permite proyectar geometrías 3D en planos 2D normalizados.

### Configuración Correcta de Vistas en Python:
* **Asociación de Plantilla Obligatoria:** Antes de añadir cualquier vista a la página con `page.addView(view)`, la página debe tener cargada una plantilla (`page.Template = template`). De lo contrario, se lanzará una excepción.
* **Orientación de la Vista:** La clase `TechDraw::DrawViewPart` no tiene la propiedad `UpDirection`. En su lugar, utiliza:
  * `Direction`: El vector de dirección de proyección normal a la hoja (ej. `App.Vector(0, -1, 0)`).
  * `XDirection`: El vector de dirección horizontal de la vista en la página (ej. `App.Vector(1, 0, 0)`).
* **Filtros y Métodos Geométricos:** Utiliza `view.getVisibleEdges()` y `view.getHiddenEdges()` para interactuar programáticamente con las aristas proyectadas (evita el atributo inexistente `GeometryLines`).

```python
import TechDraw

page = doc.addObject("TechDraw::DrawPage", "Page")
# Cargar plantilla estándar A4 Landscape
template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
template.Template = "/usr/share/freecad/Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg" # O ruta Flatpak /app/share/Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg
page.Template = template

view = doc.addObject("TechDraw::DrawViewPart", "View")
view.Source = [box]
view.Direction = App.Vector(0, -1, 0)
view.XDirection = App.Vector(1, 0, 0) # Eje horizontal de la vista en la hoja
page.addView(view)
doc.recompute()
```

---

## 4. Ejecución FEM en Modo Headless (Línea de Comandos / CI)

El banco de trabajo FEM interactúa con solvers (CalculiX) y generadores de malla (Netgen/Gmsh) mediante subprocesos (`QProcess`).

### Sincronización y Ciclo de Vida del Subproceso:
* **Falta de Event Loop en Consola:** Cuando ejecutas FreeCAD mediante `-c` (sin interfaz Qt), los métodos asíncronos y los bucles basados en `QProcess.state()` no reciben eventos del loop de Qt. El objeto de malla o resolvedor puede ser destruido por el recolector de basura antes de completar la ejecución en disco.
* **Solución Síncrona:** Espera activamente la ejecución del proceso invocando `waitForStarted(5000)` y `waitForFinished(-1)` sobre el objeto `process` del resolvedor/mesher.

```python
from femmesh import netgentools

nt = netgentools.NetgenTools(mesh_obj)
nt.prepare()
nt.compute()

# Espera síncrona obligatoria en modo consola (headless)
nt.process.waitForStarted(5000)
nt.process.waitForFinished(60000) # Tiempo máximo de espera (60s)

if nt.process.exitCode() == 0:
    nt.update_properties()
    doc.recompute()
```

### Configuración Crítica del Objeto de Malla (Netgen):
1. **Asociación de Geometría:** Utiliza `mesh_obj.Shape = box` para indicar la geometría base de la malla (la propiedad `Source` no existe en `makeMeshNetgen`).
2. **Pasos de Mallado (StartStep/EndStep):** Por defecto, un objeto `MeshNetgen` recién creado inicializa su propiedad `EndStep` en `"AnalyzeGeometry"`. Esto hace que el proceso de mallado se detenga inmediatamente tras analizar el sólido sin generar ningún elemento. Debes redefinir explícitamente el final del paso:
   ```python
   mesh_obj.StartStep = "AnalyzeGeometry"
   mesh_obj.EndStep = "OptimizeVolume" # Obligatorio para generar malla 3D de volumen
   ```
3. **Gluer de OpenCASCADE:** El algoritmo de pegado de caras/sólidos (`Glue`) puede generar errores del constructor de geometría de Netgen ("builder has errors") en piezas sólidas individuales. Desactívalo de forma segura:
   ```python
   mesh_obj.Glue = False
   mesh_obj.HealShape = False
   ```
4. **Propiedades de Resultados:** Para contar los elementos generados en el objeto de malla cargado, accede a:
   * `mesh_obj.FemMesh.NodeCount` o `len(mesh_obj.FemMesh.Nodes)`
   * `mesh_obj.FemMesh.VolumeCount`
   * `mesh_obj.FemMesh.FaceCount`

---

## 5. Parches y Limitaciones de Entorno (Flatpak / Sandboxing)

En entornos Flatpak, el backend de Netgen puede fallar al convertir parámetros booleanos o flotantes en la capa C++ de `pybind11` (`MeshingParameters`).

### Solución: Monkey-Patch de Parámetros Incompatibles
Aplica este parche al inicio del módulo de mallado en Python para limpiar los argumentos problemáticos de forma segura:

```python
from femmesh import netgentools
original_get_params = netgentools.NetgenTools.get_meshing_parameters

def patched_get_meshing_parameters(self):
    params = original_get_params(self)
    bad_keys = ["optimize3d", "optimize2d", "giveuptol2d", "giveuptol", "giveuptolopenquads"]
    for key in bad_keys:
        params.pop(key, None)
    return params

netgentools.NetgenTools.get_meshing_parameters = patched_get_meshing_parameters
```

---

## 6. Modelado Arquitectónico y BIM (Building Information Modeling)

Para diseñar planos arquitectónicos y modelos 3D coordinados en FreeCAD de forma programática (Headless / Python API), se deben seguir las siguientes directrices y resolver los bugs conocidos de la API:

### Estructura de Contenedores Espaciales (IFC):
Organiza el modelo usando la jerarquía nativa de IFC: `Site -> Building -> Floor (Storey)`.
```python
import Arch
site = Arch.makeSite(name="ProjectSite")
building = Arch.makeBuilding(name="ProjectBuilding")
floor = Arch.makeFloor(name="GroundFloor")

site.addObject(building)
building.addObject(floor)
```

### Losas de Piso (Slab/Structure):
* **Alineación Perimetral:** La losa de cimentación debe cubrir todo el contorno exterior de los muros para evitar que estos "cuelguen" o queden vacíos debajo.
* Si el muro perimetral es de $8000 \times 6000\text{ mm}$ con espesor de $200\text{ mm}$ (centrado en la línea base), las caras exteriores del muro estarán en $8200 \times 6200\text{ mm}$. La losa de piso debe coincidir con estas dimensiones exactas:
```python
slab = Arch.makeStructure(length=8200, width=6200, height=200, name="FloorSlab")
slab.Placement = App.Placement(App.Vector(-4100, 0, -100), App.Rotation())
floor.addObject(slab)
```

### Muros (Wall) y Esquinas Limpias (Metodología de Croquis Paramétricos/Sketcher):
* **El Enfoque Correcto:** Para que el plano 2D sea paramétrico y editable en el árbol del documento de FreeCAD, utiliza objetos `Sketcher::SketchObject` (croquis) en lugar de trazos de Draft.
* **Construcción de Croquis:** Agrega líneas (`Part.LineSegment`) y asocia restricciones de coincidencia, horizontalidad, verticalidad y distancias. Esto permite que el usuario edite las dimensiones directamente haciendo doble clic en el croquis en la interfaz gráfica.
* **Extrusión de Muros:** Pasa el objeto `Sketch` como `baseobj` al crear los muros. `Arch.makeWall` extruirá automáticamente la sección a lo largo del perfil 2D.

```python
# Crear un sketch paramétrico acotado y con restricciones
sketch_ext = doc.addObject("Sketcher::SketchObject", "ExteriorWallSketch")
# (Añadir segmentos de línea y aplicar restricciones de coincidencia y dimensión)
# ...
doc.recompute()

# Extruir el muro compuesto desde el Sketch
wall_outer = Arch.makeWall(sketch_ext, width=200, height=3000, name="WallOuter")
```

### Puertas y Ventanas (WindowPresets):
* **Llamado Seguro:** Usa `Arch.makeWindowPreset` con tipos como `"Simple door"` o `"Open 1-pane"`.
* **Parámetros sin Cero:** Los parámetros `width, height, h1, h2, w1, w2` deben ser estrictamente distintos de cero (`> 0`) para evitar excepciones de aborto.
* **Bug Crítico de Placement:** La función `makeWindowPreset` de FreeCAD resetea el placement al origen internamente. **Solución:** Establece la propiedad `.Placement` del objeto *después* de crearlo.
* **Orientación e Inversión de Giro:** Las puertas/ventanas se crean horizontales (plano XY). Debes rotarlas para alinearlas a la vertical del muro. 
  * Para cambiar el sentido de apertura (ej. que abra hacia adentro en la dirección de las Y negativas), **NO** uses una rotación de $-90^\circ$ en X, ya que esto volcará la puerta hacia abajo (cota Z negativa).
  * **Solución Correcta:** Rota la puerta $90^\circ$ en X, multiplica por una rotación de $180^\circ$ en Z, y ajusta la posición de su placement (offset de bisagra) para encajarla en el vano correspondiente.

```python
door = Arch.makeWindowPreset("Simple door", width=800, height=2100, h1=50, h2=50, h3=0, w1=100, w2=40, o1=0, o2=40)
# Rotación combinada de 90° en X y 180° en Z para abrir hacia el interior del baño (Y negativo)
door_rot = App.Rotation(App.Vector(0, 0, 1), 180) * App.Rotation(App.Vector(1, 0, 0), 90)
door.Placement = App.Placement(App.Vector(3400, 0, 0), door_rot)
doc.recompute()
Arch.addComponents(door, wall_partition)
```

### Generación Headless de Planos 2D (DXF / SVG):
1. **SectionPlane:** Inserta un plano de corte horizontal (`Arch.makeSectionPlane`) a una altura de $1.5$ metros (`Z = 1500`) sobre el nivel del suelo.
2. **Draft Shape2DView:** Genera las proyecciones 2D (líneas vistas y caras cortadas `"Cutfaces"`).
3. **Exportación SVG:** Usa `importSVG.export` directamente sobre las vistas 2D.
4. **Exportación DXF:** Usa una plantilla SVG vacía en un `TechDraw::DrawPage` y expórtala de forma 100% headless con `TechDraw.writeDXFPage`.

```python
# 1. Crear el plano de corte
section = Arch.makeSectionPlane(floor, name="FloorPlanCut")
section.Placement = App.Placement(App.Vector(0, 0, 1500), App.Rotation())
doc.recompute()

# 2. Generar vistas 2D
visible_view = Draft.make_shape2dview(section)
cut_view = Draft.make_shape2dview(section)
cut_view.ProjectionMode = "Cutfaces"
doc.recompute()

# 3. Exportar SVG directamente
import importSVG
importSVG.export([visible_view, cut_view], "/path/to/floor_plan.svg")

# 4. Exportar DXF vía TechDraw
page = doc.addObject("TechDraw::DrawPage", "Page")
template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
template.Template = "/app/share/Mod/TechDraw/Templates/ISO/A3_Landscape_blank.svg"
page.Template = template

td_visible = doc.addObject("TechDraw::DrawViewDraft", "TD_VisibleView")
td_visible.Source = visible_view
page.addView(td_visible)
td_visible.Scale = 0.02 # Escala 1:50

doc.recompute()
import TechDraw
TechDraw.writeDXFPage(page, "/path/to/floor_plan.dxf")
```

### Simbología de Planta 2D (Arcos de Giro de Puertas):
* **Proyección de Símbolos:** Las puertas verticales tienen su arco de giro (swing) en el plano vertical local, por lo que una proyección horizontal (`SectionPlane` mirando hacia abajo) proyectará el arco "de canto" como una simple línea recta.
* **Solución Profesional:** Dibuja el arco de giro plano en el suelo ($Z = 0$) usando `Draft.make_circle` y especificando `startangle` y `endangle`. Asegúrate de desactivar `OnlySolids` en el `SectionPlane` (`section.OnlySolids = False`) para que las curvas y líneas 2D se proyecten en el plano final.

```python
# Crear un arco de 90° de radio 900 con centro en las bisagras (hinge)
hinge_pos = App.Vector(-2450, -3000, 0)
arc = Draft.make_circle(radius=900, face=False, startangle=0, endangle=90, placement=App.Placement(hinge_pos, App.Rotation()))
floor.addObject(arc)

# Habilitar proyección de curvas 2D en el plano de corte
section.OnlySolids = False
```

### Bocetos Base (Sketch) y Visibilidad Headless:
* **¿Por qué aparecen planos en el suelo?** Al crear una ventana/puerta con `makeWindowPreset`, FreeCAD genera un `Sketch` base en el plano local XY que contiene el contorno 2D parametrizado. La extrusión 3D se genera y luego se posiciona verticalmente mediante el `.Placement` de la ventana, pero el croquis base original permanece tumbado en el origen XY. Esto es correcto y normal en el modelado paramétrico.
* **Control de Visibilidad Headless:** Para ocultar estos croquis base en la vista 3D y evitar ruido visual, se debe desactivar su visibilidad. Sin embargo, en modo consola (headless), el objeto `ViewObject` (que controla la GUI) no existe (`None`), por lo que intentar acceder a él directamente causará un error. Utiliza siempre esta función de seguridad:

```python
def set_visibility_safe(obj, visible=False):
    if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
        obj.ViewObject.Visibility = visible

# Ocultar el croquis base de forma segura
set_visibility_safe(door.Base, False)
```

### Inyección de GuiDocument.xml en Modo Headless (Fijar Visibilidades para la GUI):
* **El Problema:** Al guardar un archivo `.FCStd` desde consola (`FreeCADCmd`), FreeCAD omite la creación del archivo `GuiDocument.xml` dentro del archivo ZIP. Al abrir el archivo en la aplicación de escritorio (GUI), FreeCAD regenera los valores predeterminados, lo que causa que contenedores (como `BuildingPart`) se inicialicen como **ocultos** (grayed out) y los bocetos base de ventanas/puertas como **visibles** (mostrándose como molestos cuadros planos en el viewport).
* **La Solución:** Escribe un inyector programático de metadatos ZIP al final de tus scripts de automatización para generar un `GuiDocument.xml` correcto y empaquetarlo en el `.FCStd`.

```python
import zipfile
import re
import os

def inject_gui_document(fcstd_path):
    with zipfile.ZipFile(fcstd_path, 'r') as archive:
        doc_xml = archive.read("Document.xml").decode("utf-8")
    object_names = re.findall(r'<Object\s+name="([^"]+)"', doc_xml)
    
    visible_list = [n for n in object_names if not any(x in n for x in ["Sketch", "ExteriorWall", "InteriorWall"])]
    hidden_list = [n for n in object_names if any(x in n for x in ["Sketch", "ExteriorWall", "InteriorWall"])]
    
    xml_content = f"""<?xml version='1.0' encoding='utf-8'?>
<Document SchemaVersion="1" HasExpansion="1">
    <Expand />
    <ViewProviderData Count="{len(object_names)}">
"""
    for name in visible_list:
        xml_content += f'        <ViewProvider name="{name}"><Properties Count="1"><Property name="Visibility" type="App::PropertyBool"><Bool value="true"/></Property></Properties></ViewProvider>\n'
    for name in hidden_list:
        xml_content += f'        <ViewProvider name="{name}"><Properties Count="1"><Property name="Visibility" type="App::PropertyBool"><Bool value="false"/></Property></Properties></ViewProvider>\n'
    xml_content += "    </ViewProviderData>\n</Document>\n"
    
    temp_zip = fcstd_path + ".tmp"
    with zipfile.ZipFile(fcstd_path, 'r') as zin, zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename != "GuiDocument.xml":
                zout.writestr(item, zin.read(item.filename))
        zout.writestr("GuiDocument.xml", xml_content)
    os.replace(temp_zip, fcstd_path)
```



