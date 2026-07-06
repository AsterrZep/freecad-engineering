# 🔧 freecad-engineering — Plugin para Antigravity CLI

Plugin de [Antigravity CLI](https://antigravity.dev) que extiende al agente con una **guía de referencia completa y validada** para modelado en FreeCAD mediante Python (headless / `FreeCADCmd`).

## ✨ Características

- **BIM y planos arquitectónicos 2D/3D** — flujo completo validado contra FreeCAD 1.1.1 (Flatpak)
- **Modelado paramétrico con Sketcher** — buenas prácticas, restricciones, soporte de bocetos
- **Análisis FEM** (Calculix + Netgen) — incluyendo monkey-patch para entornos Flatpak/sandboxed
- **TechDraw** — generación de planos DXF/SVG sin abrir GUI
- **Tablas de ingeniería** (Spreadsheet) — diseño paramétrico bidireccional
- **Documentación de errores reales** — cada regla fue descubierta y validada en sesiones de desarrollo reales

## 📋 Contenido del SKILL.md

| Sección | Tema |
|---|---|
| 1 | Modelado paramétrico con Sketcher |
| 2 | Tablas de ingeniería (Spreadsheet) |
| 3 | Análisis FEM (Calculix / Netgen) |
| 4 | Malla FEM — diagnóstico y propiedades |
| 5 | Parches para entornos Flatpak |
| **6** | **BIM completo — planos arquitectónicos headless** |
| 6.1 | Jerarquía IFC (Site→Building→Floor) |
| 6.2 | Losa de piso y alineación perimetral |
| 6.3 | ⚠️ Muros con `Draft.makeWire` (NO Sketcher en headless) |
| 6.4 | Puertas y ventanas (`makeWindowPreset`) |
| 6.5 | Organización en contenedores (`addObject` uno a uno) |
| 6.6 | Simbología — arcos de giro de puertas |
| 6.7 | Modos de proyección `Shape2DView` |
| 6.8 | ✅ TechDraw sin descuadre — `Part::Compound` + `DrawViewPart` |
| 6.9 | Exportación SVG y DXF headless |
| 6.10 | Visibilidad headless (sin `GuiDocument.xml`) |

## 🚀 Instalación

```bash
# Clonar en la carpeta de plugins de Antigravity
git clone git@github.com:AsterrZep/freecad-engineering.git \
  ~/.gemini/config/plugins/freecad-engineering
```

O si ya tienes el directorio de plugins:

```bash
cd ~/.gemini/config/plugins
git clone git@github.com:AsterrZep/freecad-engineering.git
```

Luego reinicia Antigravity CLI para que el plugin sea detectado automáticamente.

## ⚡ Errores conocidos documentados

### ❌ Sketcher en headless → geometría degenerada
`Sketcher::SketchObject` con restricciones de coincidencia emite `Both points are equal`, extiende la bounding box a valores incorrectos y produce el "descuadre" en TechDraw. **Usar `Draft.makeWire` en su lugar.**

### ❌ `Part::Feature.Shape` manual → se pierde en recompute
Asignar manualmente una forma a `Part::Feature` no sobrevive un `doc.recompute()` porque no hay DAG de dependencias. **Usar `Part::Compound` con `Links`.**

### ❌ Dos `DrawViewDraft` en TechDraw → descuadre
TechDraw centra cada vista por separado en su propia bounding box. Si los centroides difieren (ej. arcos de giro extienden Y), las vistas se desplazan. **Usar un único `TechDraw::DrawViewPart` desde un `Part::Compound`.**

### ❌ Inyectar `GuiDocument.xml` en el ZIP → corrupción
El lector C++ de FreeCAD falla con `Reading failed from embedded file: GuiDocument.xml` al abrir archivos guardados en headless con XML inyectado manualmente. **No inyectar — dejar que la GUI recalcule los defaults.**

## 🧪 Proyecto de ejemplo

Incluye el script de referencia [`create_architectural_plan.py`](https://github.com/AsterrZep/freecad-engineering-bim) que genera un plano completo de una casa simple (8×6m) con muros, puertas, ventanas y plano de planta 2D exportado a SVG y DXF.

## 📄 Licencia

MIT — libre para usar, modificar y compartir.
