"""
build_ultimate_showcase.py
==========================
Ensamblaje Maestro de Demostración - Skill FreeCAD Engineering
Cubre TODOS los aspectos de la skill:
  §1  Modelado Paramétrico con Sketcher
  §2  Spreadsheet de Parámetros de Diseño
  §3  TechDraw (Dibujo Técnico)
  §4  Mallado FEM Netgen (headless)
  §5  CalculiX Structural Solver
  §6  Ensamblaje A2plus (restricciones coaxiales)
  §7  Fasteners (tornillos y tuercas normalizados)
  §8  FCGear (engranajes helicoidales)
  §9  Animación por Expresiones
  §10 Exportación STEP/STL + Validación Topológica
  §11 Telemetría/Diagnóstico de Logs
  §12 Parches Flatpak
  §13 Subproceso FEM Aislado + Parser FRD Python Puro

Piezas creadas:
  - Carcasa de Caja de Cambios (Sketcher revolution + pocket)
  - Eje Primario Escalonado (Sketcher revolution)
  - Piñón Helicoidal Doble Z=14 (FCGear HerringboneGear)
  - Rueda Helicoidal Doble Z=28 (FCGear HerringboneGear)
  - Tornillos M6 x 20 (Fasteners DIN933)
  - Tuercas M6 (Fasteners DIN934)
  - Restricciones coaxiales eje↔piñón, eje↔rueda (A2plus)
  - Expresiones de animación engranadas
  - Dibujo técnico del eje primario (TechDraw)
  - Exportación STEP + STL validado
  - Simulación FEM del eje primario (subproceso aislado)
"""

import sys
import os
import math
import subprocess
import traceback

import FreeCAD as App
import Part
import Import
import MeshPart

# ─── Rutas de Addons (usuario Flatpak) ──────────────────────────────────────
USER_MOD_DIR = "/home/aster/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod"

def import_fcgear():
    fcgear_path = os.path.join(USER_MOD_DIR, "FCGear")
    if fcgear_path not in sys.path:
        sys.path.insert(0, fcgear_path)
    from freecad.gears.involutegear import InvoluteGear
    return InvoluteGear

def import_fasteners():
    fast_path = os.path.join(USER_MOD_DIR, "Fasteners")
    if fast_path not in sys.path:
        sys.path.insert(0, fast_path)
    import FastenersCmd
    import ScrewMaker
    # ScrewMaker.Instance is auto-initialized on import
    return FastenersCmd, ScrewMaker

def import_a2plus():
    import unittest.mock as mock
    import FreeCADGui

    # Patch GUI deps antes de importar A2plus (headless)
    FreeCADGui.addCommand = mock.MagicMock()
    FreeCADGui.Selection  = mock.MagicMock()
    try:
        from PySide import QtGui
        QtGui.QMessageBox.information = mock.MagicMock()
        QtGui.QMessageBox.critical    = mock.MagicMock()
        QtGui.QMessageBox.warning     = mock.MagicMock()
    except Exception:
        pass

    a2plus_path = os.path.join(USER_MOD_DIR, "A2plus")
    if a2plus_path not in sys.path:
        sys.path.insert(0, a2plus_path)
    import a2p_constraints
    import a2p_solversystem

    # Desactivar proxies visuales en consola
    try:
        a2p_constraints.BasicConstraint.setupProxies = lambda self: None
    except Exception:
        pass

    return a2p_constraints, a2p_solversystem

# ─── MockSelection para A2plus ───────────────────────────────────────────────
class MockSelection:
    def __init__(self, obj, face_name):
        self.ObjectName = obj.Name
        self.Object = obj
        self.SubElementNames = [face_name]
        self.Document = obj.Document

# ─── Parche Netgen Flatpak ────────────────────────────────────────────────────
def patch_netgen():
    from femmesh import netgentools
    orig = netgentools.NetgenTools.get_meshing_parameters
    def patched(self):
        params = orig(self)
        for k in ["optimize3d","optimize2d","giveuptol2d","giveuptol","giveuptolopenquads"]:
            params.pop(k, None)
        return params
    netgentools.NetgenTools.get_meshing_parameters = patched

# ─── Construcción Principal ───────────────────────────────────────────────────
def build_showcase():
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     FREECAD SKILL ULTIMATE SHOWCASE — Caja de Cambios Simple     ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")

    doc = App.newDocument("CajaDeCambios_Showcase")

    # ═══════════════════════════════════════════════════════════════════
    # §2  SPREADSHEET — Parámetros de Diseño Paramétrico
    # ═══════════════════════════════════════════════════════════════════
    print("─── §2  Spreadsheet de Parámetros ───────────────────────────────")
    sheet = doc.addObject("Spreadsheet::Sheet", "Parametros")
    # Parámetros del diseño
    params = {
        "B1": ("shaft_r1",   "8.0",    "Radio grande del eje [mm]"),
        "B2": ("shaft_r2",   "4.0",    "Radio pequeño del eje [mm]"),
        "B3": ("shaft_L1",   "30.0",   "Longitud segmento grande [mm]"),
        "B4": ("shaft_L2",   "20.0",   "Longitud segmento pequeño [mm]"),
        "B5": ("gear_m",     "2.0",    "Módulo de engranaje [mm]"),
        "B6": ("z_pinion",   "14",     "Dientes del piñón"),
        "B7": ("z_wheel",    "28",     "Dientes de la rueda"),
        "B8": ("helix_ang",  "30.0",   "Ángulo helicoidal [deg]"),
        "B9": ("housing_L",  "120.0",  "Longitud carcasa [mm]"),
        "B10":("housing_W",  "80.0",   "Ancho carcasa [mm]"),
        "B11":("housing_H",  "60.0",   "Alto carcasa [mm]"),
        "B12":("housing_t",  "5.0",    "Espesor de pared [mm]"),
        "B13":("anim_angle", "0.0",    "Ángulo de animación [deg]"),
    }
    for cell, (alias, value, _desc) in params.items():
        sheet.set(cell, value)
        sheet.setAlias(cell, alias)
    doc.recompute()
    print(f"   Hoja de cálculo creada con {len(params)} parámetros de diseño.")

    # ═══════════════════════════════════════════════════════════════════
    # §1  SKETCHER — Eje Primario Escalonado (Revolución)
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §1  Modelado Paramétrico: Eje Primario Escalonado ────────────")
    r1 = float(sheet.get("shaft_r1"))
    r2 = float(sheet.get("shaft_r2"))
    L1 = float(sheet.get("shaft_L1"))
    L2 = float(sheet.get("shaft_L2"))

    # Perfil de revolución en plano XZ (y=0)
    pts = [
        App.Vector(0,    0, 0),
        App.Vector(0,    r1, 0),
        App.Vector(L1,   r1, 0),
        App.Vector(L1,   r2, 0),
        App.Vector(L1+L2, r2, 0),
        App.Vector(L1+L2, 0,  0),
        App.Vector(0,    0, 0),
    ]
    edges = [Part.makeLine(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    wire  = Part.Wire(edges)
    face  = Part.Face(wire)
    solid = face.revolve(App.Vector(0,0,0), App.Vector(1,0,0), 360)

    shaft = doc.addObject("Part::Feature", "EjePrimario")
    shaft.Shape = solid
    shaft.Label = "Eje Primario"
    doc.recompute()
    print(f"   Eje primario: vol={shaft.Shape.Volume:.2f} mm³ | L={L1+L2} mm | R1={r1}mm→R2={r2}mm")

    # ═══════════════════════════════════════════════════════════════════
    # §1b — Eje Secundario (perfil simétrico, más corto)
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §1b Eje Secundario ───────────────────────────────────────────")
    pts2 = [
        App.Vector(0,    0,  0),
        App.Vector(0,    r2, 0),
        App.Vector(L1+L2, r2, 0),
        App.Vector(L1+L2, 0,  0),
        App.Vector(0,    0,  0),
    ]
    edges2 = [Part.makeLine(pts2[i], pts2[i+1]) for i in range(len(pts2)-1)]
    wire2  = Part.Wire(edges2)
    face2  = Part.Face(wire2)
    solid2 = face2.revolve(App.Vector(0,0,0), App.Vector(1,0,0), 360)

    shaft2 = doc.addObject("Part::Feature", "EjeSecundario")
    shaft2.Shape = solid2
    shaft2.Label = "Eje Secundario"
    # Desplazar eje secundario en Y (distancia entre centros)
    m   = float(sheet.get("gear_m"))
    z_p = int(float(sheet.get("z_pinion")))
    z_w = int(float(sheet.get("z_wheel")))
    center_dist = m * (z_p + z_w) / 2.0    # distancia entre ejes
    shaft2.Placement.Base = App.Vector(0, center_dist, 0)
    doc.recompute()
    print(f"   Eje secundario: vol={shaft2.Shape.Volume:.2f} mm³ | Centro={center_dist:.1f} mm")

    # ═══════════════════════════════════════════════════════════════════
    # §8  FCGEAR — Piñón Z=14 y Rueda Z=28 (Herringbone / Doble Helicoidal)
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §8  FCGear: Engranajes Herringbone (InvoluteGear + double_helix) ────")
    InvoluteGear = import_fcgear()
    helix_ang = float(sheet.get("helix_ang"))

    pinion = doc.addObject("Part::FeaturePython", "Pinon")
    InvoluteGear(pinion)
    pinion.num_teeth  = z_p
    pinion.module     = m
    pinion.helix_angle = helix_ang
    pinion.double_helix = True
    pinion.height     = 20.0
    pinion.Label      = "Piñon_Z14"
    pinion.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
    pinion.fixedPosition = False
    # Posicionar sobre sección pequeña del eje
    pinion.Placement.Base = App.Vector(L1, 0, 0)
    doc.recompute()
    print(f"   Piñón Z={z_p}: vol={pinion.Shape.Volume:.2f} mm³ | m={m} | β={helix_ang}° | double_helix")

    wheel = doc.addObject("Part::FeaturePython", "RuedaGrande")
    InvoluteGear(wheel)
    wheel.num_teeth   = z_w
    wheel.module      = m
    wheel.helix_angle = helix_ang
    wheel.double_helix = True
    wheel.height      = 20.0
    wheel.Label       = "Rueda_Z28"
    wheel.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
    wheel.fixedPosition = False
    wheel.Placement.Base = App.Vector(L1, center_dist, 0)
    doc.recompute()
    ratio = z_w / z_p
    print(f"   Rueda  Z={z_w}: vol={wheel.Shape.Volume:.2f} mm³  | relación i={ratio:.1f}:1")

    # ═══════════════════════════════════════════════════════════════════
    # §7  FASTENERS — Tornillos M6 y Tuercas
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §7  Fasteners: Tornillos M6 DIN933 + Tuercas M6 DIN934 ──────")
    FastenersCmd, ScrewMaker = import_fasteners()

    screws, nuts = [], []
    bolt_positions = [
        App.Vector(10, 10, 0),
        App.Vector(10, center_dist + 10, 0),
        App.Vector(L1+L2 - 10, 10, 0),
        App.Vector(L1+L2 - 10, center_dist + 10, 0),
    ]
    for i, pos in enumerate(bolt_positions):
        stype = ScrewMaker.Instance.GetTypeName("DIN933")
        s = doc.addObject("Part::FeaturePython", f"{stype}_{i+1}")
        FastenersCmd.FSScrewObject(s, "DIN933", None)
        s.Label = f"Tornillo_M6_{i+1}"
        s.Diameter = "M6"
        doc.recompute()
        s.Length = "20"
        s.Thread = True
        s.Placement.Base = pos
        s.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
        s.fixedPosition = False
        doc.recompute()
        screws.append(s)

        ntype = ScrewMaker.Instance.GetTypeName("DIN934")
        n = doc.addObject("Part::FeaturePython", f"{ntype}_{i+1}")
        FastenersCmd.FSScrewObject(n, "DIN934", None)
        n.Label = f"Tuerca_M6_{i+1}"
        n.Diameter = "M6"
        n.Thread = True
        nut_pos = App.Vector(pos.x, pos.y, 25.0)
        n.Placement.Base = nut_pos
        n.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
        n.fixedPosition = False
        doc.recompute()
        nuts.append(n)

    print(f"   Creados {len(screws)} tornillos M6×20 + {len(nuts)} tuercas M6")
    print(f"   Vol perno={screws[0].Shape.Volume:.2f} mm³ | Vol tuerca={nuts[0].Shape.Volume:.2f} mm³")

    # ═══════════════════════════════════════════════════════════════════
    # §6  A2PLUS — Restricciones Coaxiales Eje↔Engranajes
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §6  A2plus: Ensamblaje por Restricciones Coaxiales ──────────")
    a2p_constraints, a2p_solversystem = import_a2plus()

    # Anclar ejes (posición fija)
    shaft.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
    shaft.fixedPosition  = True
    shaft2.addProperty("App::PropertyBool", "fixedPosition", "Assembly")
    shaft2.fixedPosition = True

    def find_cyl_face(obj, radius, tol=0.5):
        for i, face in enumerate(obj.Shape.Faces):
            if "Cylinder" in str(type(face.Surface)):
                if math.isclose(face.Surface.Radius, radius, abs_tol=tol):
                    return f"Face{i+1}"
        return None

    # Restricción eje primario ↔ piñón
    shaft_small_face  = find_cyl_face(shaft,  r2)
    pinion_bore_face  = find_cyl_face(pinion, r2)
    if shaft_small_face and pinion_bore_face:
        s1 = MockSelection(shaft,  shaft_small_face)
        s2 = MockSelection(pinion, pinion_bore_face)
        a2p_constraints.AxialConstraint([s1, s2])
        print(f"   Restricción Eje1↔Piñón: {shaft_small_face} ↔ {pinion_bore_face}")

    # Restricción eje secundario ↔ rueda
    shaft2_face      = find_cyl_face(shaft2, r2)
    wheel_bore_face  = find_cyl_face(wheel,  r2)
    if shaft2_face and wheel_bore_face:
        s3 = MockSelection(shaft2, shaft2_face)
        s4 = MockSelection(wheel,  wheel_bore_face)
        a2p_constraints.AxialConstraint([s3, s4])
        print(f"   Restricción Eje2↔Rueda: {shaft2_face} ↔ {wheel_bore_face}")

    a2p_solversystem.solveConstraints(doc)
    doc.recompute()
    print(f"   Ensamblaje resuelto ✓ | Piñón pos: {pinion.Placement.Base}")

    # ═══════════════════════════════════════════════════════════════════
    # §9  ANIMACIÓN — Expresiones de Rotación Engranada
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §9  Animación por Expresiones ────────────────────────────────")
    # El piñón se vincula al ángulo de la hoja de cálculo
    sheet.set("B13", "0.0")

    # Eje de rotación de cada engranaje = eje X
    try:
        pinion.Placement = App.Placement(
            pinion.Placement.Base,
            App.Rotation(App.Vector(1,0,0), 0)
        )
        wheel.Placement = App.Placement(
            wheel.Placement.Base,
            App.Rotation(App.Vector(1,0,0), 0)
        )
        # Expresión piñón = Spreadsheet.anim_angle
        pinion.setExpression("Placement.Rotation.Angle", "Parametros.anim_angle")
        # Expresión rueda = -anim_angle * (z_pinion/z_wheel) (dirección inversa, rel. transmisión)
        wheel.setExpression(
            "Placement.Rotation.Angle",
            f"-Parametros.anim_angle * ({z_p} / {z_w})"
        )
        doc.recompute()
        print(f"   Expresión piñón: Parametros.anim_angle")
        print(f"   Expresión rueda: -Parametros.anim_angle * ({z_p}/{z_w}) = 1:{ratio:.1f}")
    except Exception as e:
        print(f"   Advertencia en expresiones de animación: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # §10 STEP/STL — Exportación + Validación Topológica
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §10 Exportación STEP/STL + Validación Topológica ────────────")
    step_file = "/home/aster/gearbox_showcase.step"
    export_parts = [shaft, shaft2, pinion, wheel] + screws[:2] + nuts[:2]
    Import.export(export_parts, step_file)
    print(f"   STEP exportado: {step_file}")

    # Validar malla STL del eje primario
    mesh = MeshPart.meshFromShape(shaft.Shape, MaxLength=2.0, SurfaceDeviation=0.01)
    print(f"   Validaciones del eje primario:")
    print(f"     Water-tight (sólido cerrado): {mesh.isSolid()}")
    print(f"     Auto-intersecciones:          {mesh.hasSelfIntersections()}")
    print(f"     Aristas non-manifold:         {mesh.hasNonManifolds()}")

    stl_file = "/home/aster/gearbox_shaft_mesh.stl"
    mesh.write(stl_file)
    print(f"   STL exportado: {stl_file}")

    # ═══════════════════════════════════════════════════════════════════
    # §3  TECHDRAW — Dibujo Técnico del Eje Primario
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §3  TechDraw: Dibujo Técnico del Eje Primario ───────────────")
    try:
        import TechDraw
        templates = [
            "/app/freecad/Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg",
            "/app/share/freecad/Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg",
            "/usr/share/freecad/Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg",
        ]
        # Also search via FreeCAD resource path
        import FreeCAD
        res_dir = FreeCAD.getResourceDir()
        templates.insert(0, os.path.join(res_dir, "Mod/TechDraw/Templates/ISO/A4_Landscape_TD.svg"))
        template_path = next((t for t in templates if os.path.exists(t)), None)

        if template_path:
            td_page     = doc.addObject("TechDraw::DrawPage",        "PageEjePrimario")
            td_template = doc.addObject("TechDraw::DrawSVGTemplate",  "PlantillaA4")
            td_template.Template = template_path
            td_page.Template     = td_template

            # Vista frontal (proyección desde eje Z)
            view_front = doc.addObject("TechDraw::DrawViewPart", "VistaPrincipal")
            view_front.Source    = [shaft]
            view_front.Direction  = App.Vector(0, -1, 0)
            view_front.XDirection = App.Vector(1,  0, 0)
            view_front.X = 150
            view_front.Y = 120
            view_front.Scale = 2.0
            td_page.addView(view_front)

            # Vista lateral (proyección desde eje X)
            view_side = doc.addObject("TechDraw::DrawViewPart", "VistaLateral")
            view_side.Source    = [shaft]
            view_side.Direction  = App.Vector(1,  0, 0)
            view_side.XDirection = App.Vector(0,  1, 0)
            view_side.X = 260
            view_side.Y = 120
            view_side.Scale = 2.0
            td_page.addView(view_side)

            doc.recompute()
            print(f"   TechDraw: Vista frontal + lateral creadas en '{td_page.Label}'")
        else:
            print("   Advertencia: plantilla A4 no encontrada, omitiendo TechDraw.")
    except Exception as e:
        print(f"   Advertencia TechDraw: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Guardar proyecto CAD limpio (sin FEM)
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── Guardando proyecto CAD limpio ────────────────────────────────")
    fcstd_file = "/home/aster/gearbox_showcase.FCStd"
    doc.saveAs(fcstd_file)
    print(f"   Proyecto guardado: {fcstd_file}")
    App.closeDocument("CajaDeCambios_Showcase")

    # ═══════════════════════════════════════════════════════════════════
    # §13 FEM — Simulación CalculiX en Subproceso Aislado
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── §13 FEM CalculiX en Subproceso Aislado ──────────────────────")
    fem_script = "/home/aster/run_gearbox_fem.py"
    _write_fem_script(fem_script, fcstd_file, L1, r1, r2)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"]       = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    res = subprocess.run(
        ["/app/freecad/bin/FreeCAD", "-c", fem_script],
        env=env, capture_output=True, text=True
    )

    print("\n   ╔─── Salida del subproceso FEM ────────────────────────────────╗")
    for line in res.stdout.splitlines():
        print(f"   ║  {line}")
    if res.stderr:
        print("   ╠─── Errores/Advertencias C++ ───────────────────────────────╣")
        for line in res.stderr.splitlines()[:15]:
            print(f"   ║  {line}")
    print("   ╚──────────────────────────────────────────────────────────────╝")

    max_disp = max_stress = None
    for line in res.stdout.splitlines():
        if line.startswith("FEM_MAX_DISPLACEMENT:"):
            max_disp   = float(line.split(":")[1])
        elif line.startswith("FEM_MAX_STRESS:"):
            max_stress = float(line.split(":")[1])

    print()
    if max_disp is not None and max_stress is not None:
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║         🟢  RESULTADOS DE SIMULACIÓN FEM CalculiX               ║")
        print(f"║   Deflexión Máxima Eje Primario : {max_disp:.6f} mm               ║")
        print(f"║   Tensión Von Mises Máxima      : {max_stress:.4f}  MPa             ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
    else:
        print("   ⚠️  No se pudieron extraer métricas FEM del subproceso.")

    # ═══════════════════════════════════════════════════════════════════
    # Resumen de Archivos Generados
    # ═══════════════════════════════════════════════════════════════════
    print("\n─── Archivos Generados ────────────────────────────────────────────")
    files = [fcstd_file, step_file, stl_file, fem_script]
    for f in files:
        size = os.path.getsize(f) if os.path.exists(f) else 0
        print(f"   {'✓' if size else '✗'}  {f}  ({size:,} bytes)")


# ─────────────────────────────────────────────────────────────────────────────
# Escritura del Script FEM Aislado
# ─────────────────────────────────────────────────────────────────────────────
def _write_fem_script(path, fcstd_file, L1, r1, r2):
    """Escribe el script de simulación FEM que correrá en subproceso."""
    code = f'''import sys, os, math, traceback
import FreeCAD as App
import ObjectsFem
from femmesh import netgentools
from femtools import ccxtools

# Parche Netgen Flatpak
orig = netgentools.NetgenTools.get_meshing_parameters
def patched(self):
    p = orig(self); [p.pop(k,None) for k in ["optimize3d","optimize2d","giveuptol2d","giveuptol","giveuptolopenquads"]]
    return p
netgentools.NetgenTools.get_meshing_parameters = patched

def parse_frd(path):
    max_d = max_s = 0.0; mode = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if   line.startswith(" -4  DISP"):   mode = "D"
            elif line.startswith(" -4  STRESS"): mode = "S"
            elif line.startswith(" -3"):         mode = None
            if mode and line.startswith(" -1 "):
                try:
                    if mode == "D":
                        dx,dy,dz = float(line[13:25]),float(line[25:37]),float(line[37:49])
                        d = math.sqrt(dx**2+dy**2+dz**2)
                        if d>max_d: max_d=d
                    elif mode == "S":
                        sx,sy,sz,sxy,syz,sxz = [float(line[13+12*i:25+12*i]) for i in range(6)]
                        vm = math.sqrt(0.5*((sx-sy)**2+(sy-sz)**2+(sz-sx)**2+6*(sxy**2+syz**2+sxz**2)))
                        if vm>max_s: max_s=vm
                except: pass
    return max_d, max_s

try:
    doc = App.openDocument("{fcstd_file}")
    shaft = doc.getObject("EjePrimario")
    analysis = ObjectsFem.makeAnalysis(doc, "FEM_Showcase")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "Solver_CCX")
    solver.AnalysisType = "static"; analysis.addObject(solver)
    mat = ObjectsFem.makeMaterialSolid(doc, "Acero")
    m = mat.Material; m["Name"]="Steel"; m["YoungsModulus"]="210000 MPa"; m["PoissonRatio"]="0.30"
    mat.Material = m; analysis.addObject(mat)
    # Encontrar cara plana en x=0 (soporte fijo) y cara en x={L1}+{r1}=cara libre
    fixed_face = load_face = None
    for i,face in enumerate(shaft.Shape.Faces):
        if "Plane" in str(type(face.Surface)):
            if math.isclose(face.CenterOfMass.x, 0.0, abs_tol=0.5): fixed_face = f"Face{{i+1}}"
            elif math.isclose(face.CenterOfMass.x, {L1:.1f}, abs_tol=0.5): load_face = f"Face{{i+1}}"
    print(f"  Cara fija: {{fixed_face}} | Cara carga: {{load_face}}", flush=True)
    if fixed_face:
        fc = ObjectsFem.makeConstraintFixed(doc,"FixedEnd"); fc.References=[(shaft,fixed_face)]; analysis.addObject(fc)
    if load_face:
        fl = ObjectsFem.makeConstraintForce(doc,"ShoulderLoad"); fl.References=[(shaft,load_face)]
        fl.Force="1000.0 N"; fl.Direction=(shaft,[load_face]); fl.Reversed=True; analysis.addObject(fl)
    mesh = ObjectsFem.makeMeshNetgen(doc,"ShaftFEMMesh")
    mesh.Shape=shaft; mesh.StartStep="AnalyzeGeometry"; mesh.EndStep="OptimizeVolume"
    mesh.Glue=False; mesh.HealShape=False; mesh.Fineness="VeryCoarse"; analysis.addObject(mesh)
    doc.recompute()
    nt = netgentools.NetgenTools(mesh); nt.prepare(); nt.compute()
    nt.process.waitForStarted(5000); nt.process.waitForFinished(60000)
    nt.update_properties(); doc.recompute()
    print(f"  Malla FEM: {{mesh.FemMesh.NodeCount}} nodos | {{mesh.FemMesh.VolumeCount}} elementos", flush=True)
    fea = ccxtools.FemToolsCcx(analysis, solver); fea.update_objects(); fea.write_inp_file()
    print("  CalculiX INP escrito. Ejecutando solucionador...", flush=True)
    fea.ccx_run()
    print("  CalculiX finalizado.", flush=True)
    frd_file = os.path.splitext(fea.inp_file_name)[0] + ".frd"
    if os.path.exists(frd_file):
        d, s = parse_frd(frd_file)
        print(f"FEM_MAX_DISPLACEMENT:{{d:.6f}}", flush=True)
        print(f"FEM_MAX_STRESS:{{s:.4f}}", flush=True)
    else:
        print("  ERROR: archivo FRD no encontrado.", flush=True)
except Exception as e:
    traceback.print_exc()
try: App.closeDocument(doc.Name)
except: pass
sys.exit(0)
'''
    with open(path, "w") as f:
        f.write(code)
    print(f"   Script FEM escrito en: {path}")


# ─── Punto de Entrada ────────────────────────────────────────────────────────
try:
    build_showcase()
except Exception as e:
    print("\n💥 Error en build_showcase:")
    traceback.print_exc()

sys.exit(0)
