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

El banco de trabajo FEM interactúa con solvers (CalculiX) y generadores de malla (Netgen/Gmsh) mediante subprocesos (`QProcess` o `subprocess`).

### Mallado Síncrono (Netgen):
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

---

## 5. Automatización del Solver FEM CalculiX (ccx)

CalculiX es el resolvedor estructural y térmico integrado por defecto en FreeCAD.

### Definición Completa del Modelo Estructural:
1. **Solver CalculiX:** Se instancia mediante la API `ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiXCcxTools")` (de tipo `Fem::FemSolverObjectPython`).
2. **Material Sólido:** Carga un material con constantes mecánicas:
   ```python
   material = ObjectsFem.makeMaterialSolid(doc, "Steel")
   mat = material.Material
   mat["Name"] = "Steel"
   mat["YoungsModulus"] = "210000 MPa"  # Requerido con unidades
   mat["PoissonRatio"] = "0.30"
   material.Material = mat
   analysis.addObject(material)
   ```
3. **Restricción de Soporte Fijo (Fixed Constraint):** Asocia una restricción rígida sobre una cara o borde del sólido:
   ```python
   fixed = ObjectsFem.makeConstraintFixed(doc, "Fixed")
   fixed.References = [(geometry, "Face1")]  # Tupla objeto - cara
   analysis.addObject(fixed)
   ```
4. **Restricción de Fuerza / Carga:** Aplica una carga direccionada sobre otra cara:
   ```python
   force = ObjectsFem.makeConstraintForce(doc, "Force")
   force.References = [(geometry, "Face6")]
   force.Force = "1000.0 N"
   force.Direction = (geometry, ["Face6"]) # Dirección normal a la cara
   force.Reversed = True  # Invierte dirección si es necesario
   analysis.addObject(force)
   ```

### Ejecución Síncrona del Resolvedor:
Usa el envoltorio `FemToolsCcx` del módulo `femtools.ccxtools`. La llamada al método `.run()` es síncrona en scripts, bloqueando la consola hasta que CalculiX termina de calcular y carga los resultados de vuelta en el árbol de FreeCAD:

```python
from femtools import ccxtools
# Inicializar herramienta ccx pasándole la estructura del análisis y el solver
fea = ccxtools.FemToolsCcx(analysis, solver)
fea.update_objects()
success = fea.run() # Escribe .inp, ejecuta ccx y carga los resultados .frd/.dat

if success:
    doc.recompute()
    print("CalculiX ha resuelto la física correctamente.")
```

### Extracción de Resultados (Desplazamiento y Tensión):
Una vez resuelto el análisis, CalculiX crea un objeto en el documento con el nombre `CCX_Results` (de tipo `Fem::FemResultObjectPython`). Puedes consultar sus métricas de dos maneras:
1. **Acceso Directo (Velocidad):** Las propiedades contienen listas ordenadas por nodo:
   * Desplazamiento de nodos en mm: `max(res_obj.DisplacementLengths)`
   * Tensiones de Von Mises en MPa: `max(res_obj.vonMises)`
2. **Uso de resulttools (Modular):** Usando `from femresult import resulttools`:
   * `resulttools.get_stats(res_obj, "Uabs")` (retorna tupla `(min, max)` de desplazamientos).
   * `resulttools.get_stats(res_obj, "Sabs")` (retorna tupla `(min, max)` de tensiones de Von Mises).

---

## 6. Automatización de Ensamblajes (Addon A2plus)

El Addon `A2plus` permite restringir el movimiento relativo de piezas (ej. coaxialidad, contacto plano, distancia) para definir ensamblajes mecánicos.

### Reglas Críticas para la Ejecución Headless:
Al ser A2plus una herramienta altamente orientada a la interfaz gráfica, se requieren tres monkey-patches al inicio del script para evitar fallos de PySide y FreeCADGui en consola:
1. **Mocks de FreeCADGui:** El solver de A2plus llama a métodos de registro de comandos y de limpieza de selecciones en la GUI.
2. **Mock de QMessageBox:** El solver abre diálogos emergentes informativos si existen piezas flotantes. Deben simularse con `mock.MagicMock()` para evitar el error `Must construct a QApplication before a QWidget`.
3. **No-op para setupProxies:** Las restricciones crean representaciones visuales (ViewProviders) en la GUI que fallan en consola porque `ViewObject` es `None`. Se desactiva anulando `setupProxies`.

```python
import sys
import unittest.mock as mock
import FreeCADGui

# 1. Mockear la interfaz gráfica
FreeCADGui.addCommand = mock.MagicMock()
FreeCADGui.Selection = mock.MagicMock()

# 2. Mockear diálogos emergentes de PySide
from PySide import QtGui
QtGui.QMessageBox.information = mock.MagicMock()
QtGui.QMessageBox.critical = mock.MagicMock()

# 3. Cargar A2plus y anular creación de ViewProviders de restricciones
a2p_path = "/home/aster/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/A2plus"
sys.path.append(a2p_path)
import a2p_constraints
import a2p_solversystem
a2p_constraints.BasicConstraint.setupProxies = lambda self: None
```

### Regla del Anclaje Estático (fixedPosition):
Por defecto, el resolvedor de A2plus requiere que **al menos una pieza esté fija** en el espacio para servir de origen al sistema de ecuaciones. Si no hay piezas fijas (o todas están declaradas como flotantes), el solver de A2plus terminará exitosamente pero **no moverá ninguna pieza**.
* Debes inyectar la propiedad booleana `fixedPosition` a todos los sólidos involucrados.
* Define `fixedPosition = True` para la base o eje estático.
* Define `fixedPosition = False` para las piezas móviles.

```python
# Declarar eje estático
shaft.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
shaft.fixedPosition = True

# Declarar pieza móvil
bracket.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
bracket.fixedPosition = False
```

### Selección por Código y Resolución:
Dado que no existe selección por clic en modo headless, debes simular las selecciones de caras/bordes que interactúan usando una clase mock que exponga los atributos requeridos por A2plus:

```python
class MockSelection:
    def __init__(self, obj, sub_element):
        self.ObjectName = obj.Name
        self.Object = obj
        self.SubElementNames = [sub_element]  # Ej. ["Face1"]

# Enlazar cara cilíndrica del eje con la cara interior del soporte
s1 = MockSelection(shaft, "Face1")
s2 = MockSelection(bracket, "Face5")

# Crear la restricción axial (coaxialidad)
constraint = a2p_constraints.AxialConstraint([s1, s2])

# Resolver el ensamblaje síncronamente
a2p_solversystem.solveConstraints(doc)
doc.recompute()
```

---

## 7. Carga y Uso de Addons Mecánicos Externos (FCGear)

Para crear engranajes helicoidales, rectos, espina de pescado o cíclicos, usa el Addon `FCGear`.

### Rutas Correctas en Flatpak (Verificado):
En la instalación Flatpak oficial, los Addons de usuario se instalan en:
```
~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/FCGear/
```

### Importación Verificada en Headless:
```python
import sys

# Ruta al addon instalado por el usuario (Flatpak)
FCGEAR_PATH = "/home/aster/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/FCGear"
if FCGEAR_PATH not in sys.path:
    sys.path.insert(0, FCGEAR_PATH)

# Importar directamente el módulo de engranajes involutos
from freecad.gears.involutegear import InvoluteGear
```

> ⚠️ **No** uses `import FCGear` (no existe como módulo raíz).  
> ⚠️ **No** uses `from freecad.gears.commands import CreateInvoluteGear` (falla por dependencia de `scipy` en `timinggear_t.py`).

### Creación de Engranaje InvoluteGear:
```python
import FreeCAD as App
doc = App.newDocument("Gears")

pinion = doc.addObject("Part::FeaturePython", "Pinon")
InvoluteGear(pinion)  # Inicializa el proxy Python del engranaje
# Configurar propiedades ANTES del primer recompute
pinion.num_teeth   = 14        # ✅ Correcto (no 'teeth')
pinion.module      = 2.0
pinion.helix_angle = 30.0      # ✅ Correcto (no 'beta')
pinion.double_helix = True     # Activa perfil espina de pescado (Herringbone)
pinion.height      = 20.0
doc.recompute()
```

### Propiedades y Nombres Clave en FCGear (API verificada):
| Propiedad | Tipo | Descripción |
|---|---|---|
| `num_teeth` | int | Número de dientes (**no** `teeth`) |
| `module` | float | Módulo del engranaje [mm] |
| `height` | float | Ancho de cara [mm] |
| `helix_angle` | float | Ángulo helicoidal en grados (**no** `beta`) |
| `double_helix` | bool | Perfil Herringbone/espina de pescado (**no** `HerringboneGear()`) |

### Distancia entre Centros:
Para dos engranajes conjugados que engranan correctamente, la distancia entre ejes es:
```python
center_dist = module * (z_pinion + z_wheel) / 2.0
```

---

## 8. Automatización de Elementos de Unión (Addon Fasteners)

El Addon `Fasteners` permite crear tornillos, pernos, tuercas, arandelas y pasadores normalizados bajo estándares internacionales (ISO, DIN, ASME, etc.).

### Inicialización y Creación por Código:
Para instanciar un elemento de unión:
1. Agrega el directorio del Addon a `sys.path` (ej. `/home/aster/.local/share/FreeCAD/Mod/Fasteners`).
2. Obtén el nombre del tipo interno C++ usando `ScrewMaker.Instance.GetTypeName("STANDARD")` (ej. para `"DIN933"` o `"DIN934"`).
3. Añade el objeto al documento con `addObject("Part::FeaturePython", type_name)` y asócialo al envoltorio de Python con `FastenersCmd.FSScrewObject(obj, "STANDARD", None)`.

```python
import sys
# Ruta addon Fasteners (Flatpak)
FASTENERS_PATH = "/home/aster/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/Fasteners"
if FASTENERS_PATH not in sys.path:
    sys.path.insert(0, FASTENERS_PATH)
import FastenersCmd
import ScrewMaker
# ✅ ScrewMaker.Instance es auto-inicializado en la importación — NO llamar ScrewMaker.FastenerBase()

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

## 9. Creación de Animaciones Mecánicas en FreeCAD

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

## 10. Exportación y Validación de Calidad Geométrica (STEP / STL)

La exportación correcta y validación topológica son fundamentales para flujos de manufactura asistida (CAM, Impresión 3D).

### Exportación STEP / IGES (CAD Neutral):
Utiliza el módulo `Import` nativo para exportar sólidos con sus metadatos intactos:
```python
import Import
# Exporta una lista de objetos a un archivo STEP
Import.export([box, pinion], "/path/to/project_assembly.step")
```

### Conversión a Malla Poligonal (Mesh) y Exportación STL:
Usa el módulo `MeshPart` para convertir sólidos geométricos exactos (B-Rep) en mallas de triángulos trianguladas (facets) con tolerancias específicas:
```python
import MeshPart
# Parámetros: Sólido, Max Longitud de Borde, Desviación de Superficie
mesh_data = MeshPart.meshFromShape(box.Shape, MaxLength=2.0, SurfaceDeviation=0.01)

# Guardar malla en formato STL
mesh_data.write("/path/to/output_mesh.stl")
```

### Validación Topológica Automática:
Antes de la exportación a STL para impresión 3D, puedes validar programáticamente la calidad de la malla resultante para evitar fallos de impresión:
* **Malla Sólida Cerrada (Water-tight/Manifold):** `mesh_data.isSolid()` (Retorna `True` si es un volumen cerrado sin agujeros).
* **Ausencia de Aristas No-Manifold:** `mesh_data.hasNonManifolds()` (Retorna `True` si hay aristas compartidas por más de dos facetas).
* **Ausencia de Auto-intersecciones:** `mesh_data.hasSelfIntersections()` (Retorna `True` si las facetas se intersecan entre sí).

---

## 11. Telemetría y Diagnóstico Automático (FreeCAD.log)

El análisis automatizado de los logs internos del motor de FreeCAD es crucial para capturar advertencias y errores silenciosos en la ejecución de scripts (headless).

### Activación del Registro de Logs en Consola:
Para forzar a FreeCAD a escribir logs durante la ejecución de scripts CLI, inicia el contenedor con la opción `-l` o `--write-log`:
```bash
flatpak run org.freecad.FreeCAD -l -c /path/to/script.py
```
Esto creará el archivo de log en la ruta de datos del usuario Flatpak:
`~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/FreeCAD.log`

### Script de Diagnóstico de Logs (Parser de Patrones):
Puedes automatizar la inspección analizando las ocurrencias en el archivo de log utilizando expresiones regulares en Python:

```python
import re
import os

LOG_PATH = os.path.expanduser("~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/FreeCAD.log")

# Buscar patrones de Warning y Error
warn_pattern = re.compile(r'^(Wrn|Warning|Warn):\s*(.*)', re.IGNORECASE)
err_pattern = re.compile(r'^(Err|Error):\s*(.*)', re.IGNORECASE)

with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
    for line_num, line in enumerate(f, 1):
        if err_pattern.match(line) or "blocked import" in line.lower() or "exception" in line.lower():
            print(f"🟥 Error en Línea {line_num}: {line.strip()}")
        elif warn_pattern.match(line) or "warning:" in line.lower():
            print(f"🟨 Advertencia en Línea {line_num}: {line.strip()}")
```

---

## 12. Parches y Limitaciones de Entorno (Flatpak / Sandboxing)

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

## 13. Simulación FEM con CalculiX en Subproceso Aislado

El crash fatal del kernel de C++ (`std::vector::operator[] out of range`) ocurre cuando FreeCAD intenta guardar o cerrar un documento que contiene objetos de malla SMESH (generados por Netgen). La única solución robusta es aislar la simulación FEM en un **subproceso independiente** de FreeCAD que, al terminar, muere con el crash sin afectar el proceso principal.

### Arquitectura de Doble Proceso

**Proceso Principal** (crea CAD, guarda `.FCStd` limpio, llama al subproceso):
```python
import subprocess
import os

fem_script = "/path/to/run_fem_simulation.py"
cmd = ["/app/freecad/bin/FreeCAD", "-c", fem_script]

# CRÍTICO: PYTHONUNBUFFERED=1 para capturar stdout antes del crash de C++
env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
env["PYTHONDONTWRITEBYTECODE"] = "1"
res = subprocess.run(cmd, env=env, capture_output=True, text=True)

# Parsear las líneas marcadas en el stdout del subproceso
for line in res.stdout.splitlines():
    if line.startswith("FEM_MAX_DISPLACEMENT:"):
        max_disp = float(line.split(":")[1])
    elif line.startswith("FEM_MAX_STRESS:"):
        max_stress = float(line.split(":")[1])
```

**Subproceso FEM** (`run_fem_simulation.py`):

#### 1. Métodos correctos de `FemToolsCcx`
> ⚠️ La API ha cambiado en distintas versiones. En FreeCAD flatpak:
> - **✅ Correcto:** `fea.ccx_run()` — ejecuta el solver CalculiX
> - **❌ Incorrecto:** `fea.run_ccx()` — no existe, lanza `AttributeError`
> - **✅ Correcto:** `os.path.splitext(fea.inp_file_name)[0] + ".frd"` — ruta al archivo de resultados
> - **❌ Incorrecto:** `fea.frd_file` — no existe, lanza `AttributeError`

```python
from femtools import ccxtools

fea = ccxtools.FemToolsCcx(analysis, solver_fem)
fea.update_objects()
fea.write_inp_file()
fea.ccx_run()  # ✅ nombre correcto del método
frd_file = os.path.splitext(fea.inp_file_name)[0] + ".frd"  # ✅ ruta correcta
```

#### 2. Parser de Resultados FRD en Python Puro

Evita importar `femresult.frdreader` (no existe en flatpak) ni `feminout.importCcxFrdResults` (lanza el crash de SMESH al importar resultados en C++). En su lugar, parsea el archivo `.frd` directamente usando anchos de columna fijos:

```python
import math

def parse_frd_results(filepath):
    """Parse CalculiX .frd results file using pure Python column-based parsing.
    Returns (max_displacement_mm, max_von_mises_stress_MPa).
    """
    max_disp = 0.0
    max_stress = 0.0
    mode = None
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(" -4  DISP"):
                mode = "DISP"
                continue
            elif line.startswith(" -4  STRESS"):
                mode = "STRESS"
                continue
            elif line.startswith(" -3"):
                mode = None
                continue
            
            if mode and line.startswith(" -1 "):
                try:
                    # Formato fijo: 10 chars para node_id, 12 chars por cada componente float
                    if mode == "DISP":
                        dx = float(line[13:25])
                        dy = float(line[25:37])
                        dz = float(line[37:49])
                        disp_len = math.sqrt(dx**2 + dy**2 + dz**2)
                        if disp_len > max_disp:
                            max_disp = disp_len
                    elif mode == "STRESS":
                        sxx = float(line[13:25])
                        syy = float(line[25:37])
                        szz = float(line[37:49])
                        sxy = float(line[49:61])
                        syz = float(line[61:73])
                        sxz = float(line[73:85])
                        vm = math.sqrt(0.5 * ((sxx-syy)**2 + (syy-szz)**2 + (szz-sxx)**2 + 6*(sxy**2 + syz**2 + sxz**2)))
                        if vm > max_stress:
                            max_stress = vm
                except:
                    pass
    return max_disp, max_stress

# Parsear y emitir líneas marcadas para el proceso padre
if os.path.exists(frd_file):
    max_disp, max_stress = parse_frd_results(frd_file)
    print(f"FEM_MAX_DISPLACEMENT:{max_disp:.6f}", flush=True)
    print(f"FEM_MAX_STRESS:{max_stress:.2f}", flush=True)
```

### Resultados Verificados en Eje Escalonado (Acero, 500 N axial)
| Métrica | Valor |
|---|---|
| Deflexión Máxima | 0.000364 mm |
| Tensión Von Mises Máxima | 3.48 MPa |
| Nodos de malla (VeryCoarse) | 366 |

---

## 14. Modelado Arquitectónico y BIM (Building Information Modeling)

Guía completa y validada para crear planos arquitectónicos 2D + modelos 3D en FreeCAD desde script Python (headless / `FreeCADCmd`). Cada regla ha sido **probada** y documentada a partir de errores reales encontrados durante el desarrollo.

> [!IMPORTANT]
> **Flujo de trabajo correcto (resumen ejecutivo):**
> `Draft.makeWire` → `Arch.makeWall` → `Arch.makeSectionPlane` → `Draft.make_shape2dview` ×2 → `Part::Compound` → `TechDraw::DrawViewPart`

---

### 14.1 Jerarquía Espacial IFC (Site → Building → Floor)

```python
import Arch

site     = Arch.makeSite(name="ProjectSite")
building = Arch.makeBuilding(name="ProjectBuilding")
floor    = Arch.makeFloor(name="GroundFloor")

site.addObject(building)
building.addObject(floor)
```

---

### 14.2 Losa de Piso (Structure / Slab)

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

### 14.3 Muros — `Draft.makeWire` (NO Sketcher en headless)

> [!WARNING]
> **NUNCA uses `Sketcher::SketchObject` como perfil base de muros en modo headless.**
> El solver de Sketcher emite `Both points are equal` con restricciones de coincidencia en vértices compartidos de una polilínea cerrada, generando **geometría degenerada**. La bounding box del Shape2DView resultante se extiende a valores absurdos (p.ej., X=12100 en lugar de 4100), produciendo el "descuadre" visible en TechDraw.

**✅ Correcto — `Draft.makeWire`** (sin solver, sin errores):

```python
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

### 14.4 Puertas y Ventanas (`Arch.makeWindowPreset`)

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

### 14.5 Organizar en Contenedores (addObject uno a uno)

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

### 14.6 Simbología de Planta — Arcos de Giro de Puertas

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

### 14.7 Plano de Corte y Proyecciones 2D

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

### 14.8 TechDraw sin Descuadre — `Part::Compound` + `DrawViewPart`

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

### 14.9 Exportación de Planos (SVG y DXF)

```python
import importSVG, TechDraw

# SVG: exportar las vistas 2D directamente (coordenadas alineadas)
importSVG.export([view_solid, view_cutfaces], "/ruta/floor_plan.svg")

# DXF: exportar via TechDraw (headless, sin abrir GUI)
TechDraw.writeDXFPage(page, "/ruta/floor_plan.dxf")
```

---

### 14.10 Visibilidad Headless (Croquis Base de Puertas/Ventanas)

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

