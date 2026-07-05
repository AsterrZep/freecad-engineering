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

## 5. Carga y Uso de Addons Mecánicos Externos (ej. FCGear)

Para crear componentes mecánicos avanzados como engranajes rectos, helicoidales, cónicos o sinfines, se suelen usar Addons externos como `FCGear`.

### Resolución de Dependencias y Rutas en Headless/Flatpak:
1. **Carga del Namespace `freecad`:** Los Addons externos se registran bajo el namespace `freecad` (ej. `freecad.gears`). Si el addon está instalado en el host (`~/.local/share/FreeCAD/Mod/FCGear`) y se ejecuta bajo un contenedor sandbox como Flatpak, se debe extender manualmente el `__path__` del paquete `freecad` y agregar la ruta a `sys.path`.
2. **Monkey-Patching de Librerías Faltantes (Bypass de `scipy`):** Algunos módulos auxiliares de addons externos importan dependencias grandes como `scipy` que no se encuentran en la instalación base. Si solo se desea generar geometrías de engranajes básicas (que no usan algoritmos de optimización de perfiles complejos de scipy), se puede engañar al importador de Python mockeando los módulos en `sys.modules`.

```python
import sys
import os
import unittest.mock as mock

# 1. Bypassear la dependencia faltante de scipy
sys.modules['scipy'] = mock.MagicMock()
sys.modules['scipy.optimize'] = mock.MagicMock()

# 2. Agregar el directorio base del Addon a sys.path para imports como 'import pygears'
fcgear_base = "/home/aster/.local/share/FreeCAD/Mod/FCGear"
if fcgear_base not in sys.path:
    sys.path.append(fcgear_base)

# 3. Importar freecad and extender su ruta de búsqueda para subpaquetes
import freecad
fcgear_addon = "/home/aster/.local/share/FreeCAD/Mod/FCGear/freecad"
if fcgear_addon not in freecad.__path__:
    freecad.__path__.append(fcgear_addon)

# 4. Importar comandos y crear piezas
from freecad.gears.commands import CreateInvoluteGear
doc = App.newDocument("Gears")
gear = CreateInvoluteGear.create()
```

### Propiedades y Nombres Clave en FCGear:
Al modificar geometrías paramétricas de FCGear vía Python, los nombres clave de las propiedades son:
* `num_teeth` (entero): Número de dientes (reemplaza a `teeth`).
* `module` (longitud/float): Módulo del engranaje (ej. `2.0` o `"2.0 mm"`).
* `height` (longitud/float): Espesor o ancho de cara (ej. `12.0`).
* `helix_angle` (ángulo/float): Ángulo de hélice en grados (reemplaza a `beta`).
* `double_helix` (booleano): Activa engranajes tipo espina de pescado (Herringbone).
* `Placement.Base`: Posición espacial. Para engranar dos piezas con dientes corregidos, la distancia entre centros teórica es:
  $$d = \frac{m \cdot (z_1 + z_2)}{2}$$

---

## 6. Automatización de Elementos de Unión (Addon Fasteners)

El Addon `Fasteners` permite crear tornillos, pernos, tuercas, arandelas y pasadores normalizados bajo estándares internacionales (ISO, DIN, ASME, etc.).

### Inicialización y Creación por Código:
Para instanciar un elemento de unión:
1. Agrega el directorio del Addon a `sys.path` (ej. `/home/aster/.local/share/FreeCAD/Mod/Fasteners`).
2. Obtén el nombre del tipo interno C++ usando `ScrewMaker.Instance.GetTypeName("STANDARD")` (ej. para `"DIN933"` o `"DIN934"`).
3. Añade el objeto al documento con `addObject("Part::FeaturePython", type_name)` y asócialo al envoltorio de Python con `FastenersCmd.FSScrewObject(obj, "STANDARD", None)`.

```python
import sys
sys.path.append("/home/aster/.local/share/FreeCAD/Mod/Fasteners")
import FastenersCmd
import ScrewMaker

doc = App.activeDocument()
# Obtener el tipo de objeto para DIN933 (tornillo hexagonal)
type_name = ScrewMaker.Instance.GetTypeName("DIN933")
screw = doc.addObject("Part::FeaturePython", type_name)
FastenersCmd.FSScrewObject(screw, "DIN933", None)
```

### Regla Crítica de Asignación de Propiedades (Diameter y Length):
Las propiedades de tamaño en Fasteners son enumeraciones dinámicas dependientes.
* **El Error de Restricción (`ValueError`):** Si cambias el diámetro (`Diameter`) y luego cambias inmediatamente la longitud (`Length`) sin actualizar el documento, se lanzará una excepción indicando que la longitud no pertenece al conjunto de valores permitidos. Esto se debe a que la lista de longitudes válidas se restringe y valida dinámicamente según el diámetro actual del tornillo en la base de datos de C++.
* **La Solución:** Debes llamar a `doc.recompute()` inmediatamente después de modificar `Diameter` y antes de asignar `Length`.

```python
# 1. Asignar el diámetro
screw.Diameter = "M8"
# 2. Recomputar el documento para refrescar las restricciones de longitud en C++
doc.recompute()
# 3. Asignar la longitud (ahora '40' es válido para 'M8')
screw.Length = "40"

# Activar la generación física del roscado (genera rosca real 3D)
screw.Thread = True 
doc.recompute()
```

---

## 7. Creación de Animaciones Mecánicas en FreeCAD

Para animar piezas móviles acopladas (como engranajes mesheados) vinculando sus posiciones angulares:

### Configuración del Mapeo de Rotaciones por Expresión:
1. **Configuración de Ejes:** Define el eje de rotación de cada componente en su propiedad `Placement.Rotation.Axis` (usualmente `App.Vector(0, 0, 1)` para el plano XY).
2. **Control por Celda de Spreadsheet:** Crea una celda alias (ej. `angle`) en Spreadsheet con el ángulo de entrada actual.
3. **Expresión del Conductor (Pinión):** Vincula el ángulo de rotación del conductor directamente al Spreadsheet:
   ```python
   conductor.setExpression("Placement.Rotation.Angle", "Spreadsheet.angle")
   ```
4. **Expresión del Conducido (Mating Gear):** El conducido debe rotar en dirección opuesta con la relación de transmisión inversa y, si es necesario, un desfase de medio paso (half-pitch offset) en grados para evitar la colisión visual inicial de los dientes:
   ```python
   conducido.setExpression("Placement.Rotation.Angle", "-Spreadsheet.angle * (teeth_pinion / teeth_gear) + phase_shift")
   ```

### Automatización con Macro GUI (PySide + QTimer):
Para ejecutar la animación de forma interactiva en la interfaz gráfica, se utiliza un script de Macro (`.FCMacro`) con una pequeña ventana Qt que controle el temporizador sin bloquear el hilo principal de FreeCAD:

```python
from PySide import QtCore, QtWidgets
import FreeCAD as App

class GearAnimator(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control de Animación")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        # Configurar botones Play, Pause, Reset y QTimer
        # que incrementan periódicamente doc.Spreadsheet.angle y llaman a doc.recompute()
        ...
```

---

## 8. Parches y Limitaciones de Entorno (Flatpak / Sandboxing)

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
