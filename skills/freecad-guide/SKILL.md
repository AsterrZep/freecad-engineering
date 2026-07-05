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

Guía completa y validada para crear planos arquitectónicos 2D + modelos 3D en FreeCAD desde script Python (headless / `FreeCADCmd`). Cada regla ha sido **probada** y documentada a partir de errores reales encontrados durante el desarrollo.

> [!IMPORTANT]
> **Flujo de trabajo correcto (resumen ejecutivo):**
> `Draft.makeWire` → `Arch.makeWall` → `Arch.makeSectionPlane` → `Draft.make_shape2dview` ×2 → `Part::Compound` → `TechDraw::DrawViewPart`

---

### 6.1 Jerarquía Espacial IFC (Site → Building → Floor)

```python
import Arch

site     = Arch.makeSite(name="ProjectSite")
building = Arch.makeBuilding(name="ProjectBuilding")
floor    = Arch.makeFloor(name="GroundFloor")

site.addObject(building)
building.addObject(floor)
```

---

### 6.2 Losa de Piso (Structure / Slab)

La losa debe **coincidir exactamente** con la huella exterior de los muros para que no queden huecos debajo de las paredes.

| Muro perimetral | Espesor | Cara exterior | Losa necesaria |
|---|---|---|---|
| 8000 × 6000 mm | 200 mm centrado | ±4100, ±3100 | 8200 × 6200 mm |

```python
slab = Arch.makeStructure(length=8200, width=6200, height=200, name="FloorSlab")
# Centrar la losa: XMin=-4100, Y centrado, Z de -100 a 0
slab.Placement = App.Placement(App.Vector(-4100, 0, -100), App.Rotation())
floor.addObject(slab)
doc.recompute()
```

---

### 6.3 Muros — `Draft.makeWire` (NO Sketcher en headless)

> [!WARNING]
> **NUNCA uses `Sketcher::SketchObject` como perfil base de muros en modo headless.**
> El solver de Sketcher emite `Both points are equal` con restricciones de coincidencia en vértices compartidos de una polilínea cerrada, generando **geometría degenerada**. La bounding box del Shape2DView resultante se extiende a valores absurdos (p.ej., X=12100 en lugar de 4100), produciendo el "descuadre" visible en TechDraw.

**✅ Correcto — `Draft.makeWire`** (sin solver, sin errores):

```python
import Draft

# Perímetro exterior: 8000×6000 mm centrado en el origen
pts_ext = [
    App.Vector(-4000, -3000, 0),
    App.Vector( 4000, -3000, 0),
    App.Vector( 4000,  3000, 0),
    App.Vector(-4000,  3000, 0),
]
wire_ext = Draft.makeWire(pts_ext, closed=True, face=False)
doc.recompute()

wall_outer = Arch.makeWall(wire_ext, width=200, height=3000, name="WallOuter")
wall_outer.Align = "Center"   # centra el muro sobre la línea base
doc.recompute()

# Partición interior: segmento simple
wire_vert = Draft.makeWire([App.Vector(0, -3000, 0), App.Vector(0, 3000, 0)])
doc.recompute()
wall_vert = Arch.makeWall(wire_vert, width=100, height=3000, name="WallVert")
wall_vert.Align = "Center"
doc.recompute()
```

---

### 6.4 Puertas y Ventanas (`Arch.makeWindowPreset`)

* **Parámetros:** Todos deben ser `> 0` (`h1`, `h2`, `w1`, `w2`, etc.). Un valor 0 lanza una excepción.
* **Bug de placement:** `makeWindowPreset` resetea el placement internamente. **Siempre asigna `.Placement` DESPUÉS de crearlo.**
* **Rotación estándar** (puerta en pared horizontal, plano XY → vertical en muro):

```python
door = Arch.makeWindowPreset("Simple door", width=900, height=2100,
                              h1=50, h2=50, h3=0, w1=100, w2=40, o1=0, o2=40)
# Rotar 90° en X para poner la puerta vertical
door.Placement = App.Placement(
    App.Vector(-2000, -3000, 0),
    App.Rotation(App.Vector(1, 0, 0), 90)
)
door.SymbolPlan = True   # muestra símbolo en planta
door.Opening   = 90      # ángulo de apertura del arco
doc.recompute()
Arch.addComponents(door, wall_outer)
doc.recompute()

# Puerta invertida (sentido opuesto): combinar rotaciones
rot_inv = App.Rotation(App.Vector(0, 0, 1), 180) * App.Rotation(App.Vector(1, 0, 0), 90)
door2.Placement = App.Placement(App.Vector(3400, 0, 0), rot_inv)
```

---

### 6.5 Organizar en Contenedores (addObject uno a uno)

> [!WARNING]
> `floor.addObjects([obj1, obj2, ...])` puede lanzar excepciones silenciosas en el manejador `onChanged` de Python en algunas versiones de FreeCAD.

**✅ Siempre agrega objetos de uno en uno:**

```python
floor.addObject(slab)
floor.addObject(wall_outer)
floor.addObject(wall_vert)
floor.addObject(arc_main)   # arcos de giro
doc.recompute()
```

---

### 6.6 Simbología de Planta — Arcos de Giro de Puertas

Las puertas están orientadas verticalmente (extruidas en Z). Una proyección top-down proyectaría el arco "de canto" como una línea recta. La solución: **dibujar el arco en Z=0 con `Draft.make_circle`**.

```python
# Arco de 90° (cuarto de círculo) en el plano del suelo
arc = Draft.make_circle(
    radius=900, face=False, startangle=0, endangle=90,
    placement=App.Placement(App.Vector(-2450, -3000, 0), App.Rotation())
)
arc.Label = "SwingArc_Main"
floor.addObject(arc)
doc.recompute()
```

Y en el `SectionPlane`, habilitar la proyección de curvas 2D:
```python
section.OnlySolids = False  # incluye curvas Draft, no solo sólidos
```

---

### 6.7 Plano de Corte y Proyecciones 2D

#### Modos disponibles en `Shape2DView.ProjectionMode`:
| Modo | Descripción |
|---|---|
| `"Solid"` | Líneas visibles de los sólidos desde la dirección de proyección |
| `"Cutlines"` | Solo las líneas donde el plano de corte intersecta los sólidos |
| `"Cutfaces"` | Caras rellenas donde el plano de corte intersecta (hachuras) |
| `"Individual Faces"` | Cada cara proyectada individualmente |
| `"Solid faces"` | Caras visibles de los sólidos |

> [!NOTE]
> No existe un modo `"All"`. Para un plano completo se usan **dos vistas**: `"Solid"` (contornos) + `"Cutfaces"` (relleno de muros).

```python
section = Arch.makeSectionPlane(floor, name="FloorPlanCut")
section.Placement = App.Placement(App.Vector(0, 0, 1500), App.Rotation())
section.OnlySolids = False
doc.recompute()

view_solid = Draft.make_shape2dview(section)
view_solid.Label         = "VisibleLinesView"
view_solid.InPlace       = True        # CRÍTICO: mantiene coordenadas del mundo real
view_solid.ProjectionMode = "Solid"
doc.recompute()

view_cutfaces = Draft.make_shape2dview(section)
view_cutfaces.Label         = "CutFacesView"
view_cutfaces.InPlace       = True     # CRÍTICO: mismas coordenadas que view_solid
view_cutfaces.ProjectionMode = "Cutfaces"
doc.recompute()
```

> [!CAUTION]
> **`InPlace = True` es obligatorio en AMBAS vistas.** Si `InPlace = False` en alguna, FreeCAD traslada esa vista al origen (0,0,0), mientras la otra permanece en las coordenadas reales del modelo. El resultado es un "descuadre" masivo entre contornos y relleno.

---

### 6.8 TechDraw sin Descuadre — `Part::Compound` + `DrawViewPart`

Este es el patrón más importante y más costoso de descubrir.

#### ¿Por qué desalinean dos `DrawViewDraft` separados?

`TechDraw::DrawViewDraft` **centra** cada vista en la página según el centroide de su propia bounding box. Como `view_solid` (Z=0) y `view_cutfaces` (Z=1500) tienen bboxes con centroides distintos en Y (el solid incluye los arcos de giro que extienden Y hacia negativo), los dos `DrawViewDraft` se colocan en posiciones diferentes de la página → **descuadre**.

#### ¿Por qué `Part::Feature.Shape` no funciona?

```python
# ❌ INCORRECTO - la forma se pierde en el siguiente recompute
feat = doc.addObject("Part::Feature", "Compound")
feat.Shape = Part.makeCompound([view_solid.Shape, view_cutfaces.Shape])
doc.recompute()  # ← borra feat.Shape (no tiene DAG de dependencias)
```

#### ✅ Solución correcta — `Part::Compound` con `Links` (paramétrico)

```python
# Fusionar ambas vistas en un único objeto paramétrico
compound = doc.addObject("Part::Compound", "FloorPlanCompound")
compound.Links = [view_solid, view_cutfaces]
doc.recompute()

# Verificar que la bbox tenga las dimensiones correctas del edificio:
bb = compound.Shape.BoundBox
print(f"Compound X width: {bb.XLength:.0f} mm")   # debe ≈ ancho del edificio
print(f"Compound Y height: {bb.YLength:.0f} mm")  # debe ≈ largo + swing arcs

# Una sola DrawViewPart → un solo centroide → sin descuadre
page     = doc.addObject("TechDraw::DrawPage", "Page")
template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
template.Template = "/app/share/Mod/TechDraw/Templates/ISO/A3_Landscape_blank.svg"
page.Template = template

td_view            = doc.addObject("TechDraw::DrawViewPart", "TD_FloorPlan")
td_view.Source     = [compound]
td_view.Direction  = App.Vector(0, 0, -1)   # vista desde arriba (top view)
td_view.XDirection = App.Vector(1, 0, 0)    # X hacia la derecha
td_view.Scale      = 0.02                   # escala 1:50
page.addView(td_view)
doc.recompute()
```

---

### 6.9 Exportación de Planos (SVG y DXF)

```python
import importSVG, TechDraw

# SVG: exportar las vistas 2D directamente (coordenadas alineadas)
importSVG.export([view_solid, view_cutfaces], "/ruta/floor_plan.svg")

# DXF: exportar via TechDraw (headless, sin abrir GUI)
TechDraw.writeDXFPage(page, "/ruta/floor_plan.dxf")
```

---

### 6.10 Visibilidad Headless (Croquis Base de Puertas/Ventanas)

`makeWindowPreset` genera un `Sketch` base en el plano XY. En modo headless el `ViewObject` es `None` — acceder directamente lanza `AttributeError`. Usa siempre este helper:

```python
def set_visibility_safe(obj, visible=False):
    if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
        obj.ViewObject.Visibility = visible

# Ejemplo: ocultar el sketch base de una puerta
set_visibility_safe(door.Base, False)
```

> [!NOTE]
> **No inyectes `GuiDocument.xml` manualmente en el ZIP del `.FCStd`.** El lector C++ de FreeCAD es estricto con el esquema XML y fallará silenciosamente con el error `Reading failed from embedded file: GuiDocument.xml`, corrompiendo la carga del viewport (los ViewProviders quedan como enteros en lugar de objetos Python, generando `AttributeError: 'int' object has no attribute 'restoreConstraints'`). El archivo sigue siendo funcional al abrirse en FreeCAD GUI — simplemente la GUI recalcula los valores por defecto de visibilidad.

