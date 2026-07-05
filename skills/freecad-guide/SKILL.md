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
Usa `Arch.makeStructure` sin baseobj para definir una losa rectangular especificando dimensiones directas:
```python
slab = Arch.makeStructure(length=5000, width=4000, height=200, name="FloorSlab")
slab.Placement = App.Placement(App.Vector(0, 0, -200), App.Rotation())
floor.addObject(slab)
```

### Muros (Wall) y Esquinas Limpias:
* Define muros con `Arch.makeWall()`.
* **Esquinas sin Solapamiento:** Para que las uniones de muros no generen geometría duplicada (solapes), resta los espesores de los muros perpendiculares en las longitudes de los muros secundarios (ej. un muro de longitud $L - 2\cdot w$ para encajar entre dos paralelos).

### Puertas y Ventanas (WindowPresets):
* **Llamado Seguro:** Usa `Arch.makeWindowPreset` con tipos como `"Simple door"` o `"Open 1-pane"`.
* **Parámetros sin Cero:** Los parámetros `width, height, h1, h2, w1, w2` deben ser estrictamente distintos de cero (`> 0`) para evitar excepciones de aborto.
* **Bug Crítico de Placement:** La función `makeWindowPreset` de FreeCAD resetea el placement al origen internamente. **Solución:** Establece la propiedad `.Placement` del objeto *después* de crearlo.
* **Orientación y Corte de Muro:** Las puertas/ventanas se crean horizontales (plano XY). Debes rotarlas para alinearlas a la vertical del muro y agregarlas al muro mediante `Arch.addComponents`.

```python
door = Arch.makeWindowPreset("Simple door", width=900, height=2100, h1=50, h2=50, h3=0, w1=100, w2=40, o1=0, o2=40)
# Rotación de 90° en X para verticalidad en muro Bottom (eje X)
door.Placement = App.Placement(App.Vector(-1000, -1900, 0), App.Rotation(App.Vector(1, 0, 0), 90))
doc.recompute()
Arch.addComponents(door, wall_bottom)
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

