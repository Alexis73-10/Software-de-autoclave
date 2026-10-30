# tools/entrega/compilar_entrega.py
"""Entrega 1.0.0-alpha.N en un solo comando (etapa VER, §2).

    python tools/entrega/compilar_entrega.py [--con-generador]
        [--python-compilacion RUTA] [--iscc RUTA] [--sin-suite-serie] [--sin-suite]

Desde `dev` con el árbol limpio:
  1. N = mayor etiqueta v1.0.0-alpha.K + 1 (D-VER-3) y se escribe `_version.py`;
  2. commit `chore(ver): 1.0.0-alpha.N` (con la entrada de HISTORIAL_VERSIONES.md);
  3. compila Autoclave, AutoclaveBackend y AutoclaveSettings.spec (y el
     generador con --con-generador), con `_build_info.py` de entrega;
  4. tools/verificar_entrega_neutra.py dist/Autoclave;
  5. el .exe compilado reporta 1.0.0-alpha.N (`--escribir-version`: escribe la
     versión en un JSON y sale sin abrir el enlace de E/S ni ninguna ventana);
  6. Inno Setup -> Autoclave_Setup_1.0.0-alpha.N.exe (AppVerNum, §2.3);
  7. carpeta entrega/v1.0.0-alpha.N_<AAAA-MM-DD>/ (zip, Setup, LEEME,
     SHA256SUMS.txt, manifiesto, entorno_build.txt, usb/);
  8. etiqueta anotada v1.0.0-alpha.N sobre el commit del paso 2.
Si falla un paso de 3 a 8, el commit del paso 2 se deshace (`git reset --keep`),
no queda etiqueta y N no se consume. No hace push: imprime el comando.

Salidas: 0 entrega hecha; 1 falló un paso (deshecho); 2 verificaciones previas
no superadas (nada tocado)."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ / "src"))
import info_compilacion as ic  # noqa: E402
from autoclave import _version as ver  # noqa: E402

RAMA = "dev"
SPECS = ("Autoclave", "AutoclaveBackend", "AutoclaveSettings")
ARCHIVO_VERSION = Path("src") / "autoclave" / "_version.py"
HISTORIAL = Path("docs") / "versiones" / "HISTORIAL_VERSIONES.md"
LEEME = Path("docs") / "instalacion" / "LEEME_INSTALACION.md"
ISS = Path("tools") / "instalador" / "autoclave.iss"
# Entrega anterior a este esquema: la compilación I (K13)
ETIQUETA_PREVIA_AL_ESQUEMA = "inst-2026-10-24-i"
_ALPHA = re.compile(r"^v1\.0\.0-alpha\.(\d+)$")
_NUM_ETAPA = {"alpha": 1, "beta": 2, "rc": 3}
N_MAXIMO = 999


class FalloPaso(Exception):
    """Un paso de 3 a 8 no se cumplió: se deshace la entrega."""


# ── cálculos puros ──────────────────────────────────────────────────────────

def calcular_n(etiquetas) -> int:
    """D-VER-3: mayor v1.0.0-alpha.K + 1 en orden numérico; 1 si no hay.
    Las demás (inst-*, archivo/*, v1.0.0-beta.*...) no cuentan."""
    numeros = [int(m.group(1)) for e in etiquetas if (m := _ALPHA.match(str(e).strip()))]
    return max(numeros, default=0) + 1


def app_ver_num(semver: str) -> str:
    """§2.3: cuarto campo = etapa × 1000 + N (alpha 1, beta 2, rc 3); final = 9000."""
    mayor, menor, parche, etapa, n = ver.partes_semver(semver)
    if etapa is None:
        return f"{mayor}.{menor}.{parche}.9000"
    if not 1 <= n <= N_MAXIMO:
        raise ValueError(f"N fuera de 1..{N_MAXIMO}: {semver}")
    return f"{mayor}.{menor}.{parche}.{_NUM_ETAPA[etapa] * 1000 + n}"


def reescribir_version(texto: str, semver: str) -> str:
    """Cambia solo las dos asignaciones de `_version.py`."""
    nuevo, n1 = re.subn(r'^__version__ = "[^"]*"$', f'__version__ = "{ver.semver_a_pep440(semver)}"',
                        texto, count=1, flags=re.M)
    nuevo, n2 = re.subn(r'^VERSION_SEMVER = "[^"]*"$', f'VERSION_SEMVER = "{semver}"',
                        nuevo, count=1, flags=re.M)
    if (n1, n2) != (1, 1):
        raise ValueError("_version.py no tiene las líneas __version__ / VERSION_SEMVER esperadas")
    return nuevo


def entrada_historial(semver: str, fecha: str, base: str, num: str, anterior: str | None,
                      commits: list[str]) -> str:
    lineas = [f"## {semver} — {fecha}", "",
              f"- Etiqueta: `v{semver}` (commit `chore(ver): {semver}`, sobre `{base}`)",
              f"- AppVerNum: `{num}`",
              f"- SHA-256 del Setup y del zip: en el mensaje de la etiqueta y en "
              f"`entrega/v{semver}_{fecha}/SHA256SUMS.txt` (solo existen después de compilar)",
              f"- Commits desde `{anterior}`:" if anterior else "- Commits: (sin entrega anterior)"]
    lineas += [f"  - {c}" for c in commits] or ["  - (ninguno)"]
    return "\n".join(lineas) + "\n\n"


MARCA_ENTRADAS = "<!-- entradas:"


def agregar_al_historial(texto: str, entrada: str) -> str:
    """La entrada más nueva va primero, justo debajo de la línea de la marca."""
    i = texto.find(MARCA_ENTRADAS)
    if i < 0:
        raise ValueError(f"{HISTORIAL} no tiene la línea «{MARCA_ENTRADAS} ...»")
    fin = texto.find("\n", i)
    fin = len(texto) if fin < 0 else fin + 1
    return texto[:fin] + "\n" + entrada + texto[fin:]


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ── verificaciones previas (§2.1) ───────────────────────────────────────────

@dataclass
class Previas:
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def verificaciones_previas(git, correr_suite, existe=os.path.exists, herramientas=()) -> Previas:
    """`git(*args) -> str`; `correr_suite() -> (ok, detalle)`; `herramientas`:
    [(nombre, ruta)] que deben existir. Nada de esto modifica el repositorio."""
    p = Previas()
    rama = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if rama != RAMA:
        p.errores.append(f"La rama actual es '{rama}': la entrega se hace desde '{RAMA}' (D-VER-4)")
    cambiados, sin_versionar_producto, sin_versionar_otros = ic.estado_arbol(
        git("status", "--porcelain", "--untracked-files=all"))
    if cambiados:
        p.errores.append("Archivos versionados modificados o en el índice: " + ", ".join(cambiados))
    if sin_versionar_producto:
        p.errores.append("Archivos sin versionar en carpetas del producto "
                         f"({', '.join(ic.CARPETAS_PRODUCTO)}): " + ", ".join(sin_versionar_producto))
    if sin_versionar_otros:
        p.avisos.append(f"{len(sin_versionar_otros)} archivo(s) sin versionar fuera del producto "
                        "(no bloquean): " + ", ".join(sin_versionar_otros[:20])
                        + (" ..." if len(sin_versionar_otros) > 20 else ""))
    try:
        local = git("rev-parse", RAMA).strip()
        remota = git("rev-parse", f"origin/{RAMA}").strip()
        if local != remota:
            p.avisos.append(f"'{RAMA}' local ({local[:7]}) no coincide con 'origin/{RAMA}' "
                            f"({remota[:7]}) según la última consulta al remoto")
    except RuntimeError as e:
        p.avisos.append(f"No se pudo comparar con origin/{RAMA}: {e}")
    for nombre, ruta in herramientas:
        if not ruta or not existe(ruta):
            p.errores.append(f"No se encuentra {nombre}: {ruta}")
    if not p.errores:   # la suite tarda: solo si lo demás está bien
        ok, detalle = correr_suite()
        if not ok:
            p.errores.append(f"La suite no está en verde: {detalle}")
    return p


def correr_suite_real(python: str, raiz: Path, reintentar_en_serie: bool = True):
    """Misma invocación que las tandas (`pytest tests -n auto`). Las rojas se
    repiten en serie (`--lf`); verde solo si en serie pasan todas."""
    r = subprocess.run([python, "-m", "pytest", "tests", "-n", "auto", "-q"], cwd=str(raiz),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    resumen = (r.stdout.strip().splitlines() or ["(sin salida)"])[-1]
    print(f"   suite en paralelo: {resumen}")
    if r.returncode == 0:
        return True, resumen
    if not reintentar_en_serie:
        return False, resumen
    s = subprocess.run([python, "-m", "pytest", "tests", "--lf", "-q"], cwd=str(raiz),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    serie = (s.stdout.strip().splitlines() or ["(sin salida)"])[-1]
    print(f"   rojas repetidas en serie: {serie}")
    return s.returncode == 0, f"en paralelo: {resumen}; en serie: {serie}"


# ── contexto y pasos 3 a 8 ──────────────────────────────────────────────────

@dataclass
class Contexto:
    raiz: Path
    semver: str
    num: str
    fecha: str
    python_compilacion: str
    iscc: str
    con_generador: bool = False
    commit: str = ""
    carpeta: Path | None = None
    sumas: dict = field(default_factory=dict)

    @property
    def etiqueta(self) -> str:
        return f"v{self.semver}"


def _correr(cmd, cwd, entorno=None, timeout=None, registro: Path | None = None):
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=entorno, timeout=timeout,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if registro is not None:
        registro.parent.mkdir(parents=True, exist_ok=True)
        registro.write_text(f"$ {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}", encoding="utf-8")
    if r.returncode != 0:
        cola = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
        raise FalloPaso(f"{Path(str(cmd[0])).name} salió con {r.returncode}:\n{cola}")
    return r


def paso_compilar(ctx: Contexto) -> None:
    entorno = dict(os.environ, **{ic.VARIABLE_ETIQUETA: ctx.etiqueta})
    registros = ctx.raiz / "build" / "entrega_registros"
    specs = list(SPECS) + (["GeneradorCodigos"] if ctx.con_generador else [])
    for spec in specs:
        print(f"   PyInstaller {spec}.spec ...")
        _correr([ctx.python_compilacion, "-m", "PyInstaller", "--noconfirm",
                 Path("packaging") / f"{spec}.spec"], ctx.raiz, entorno,
                registro=registros / f"build_{spec}.log")
    info = (ctx.raiz / ic.ARCHIVO).read_text(encoding="utf-8")
    if f"ETIQUETA = {ctx.etiqueta!r}" not in info or "SUCIO = False" not in info:
        raise FalloPaso(f"_build_info.py no es de entrega limpia:\n{info}")


def paso_verificar_neutra(ctx: Contexto) -> None:
    _correr([ctx.python_compilacion, Path("tools") / "verificar_entrega_neutra.py",
             Path("dist") / "Autoclave"], ctx.raiz)


def paso_verificar_version_exe(ctx: Contexto) -> None:
    exe = ctx.raiz / "dist" / "Autoclave" / "Autoclave.exe"
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "version.json"
        _correr([exe, "--escribir-version", salida], ctx.raiz, timeout=120)
        if not salida.is_file():
            raise FalloPaso("Autoclave.exe --escribir-version no escribió el archivo")
        datos = json.loads(salida.read_text(encoding="utf-8"))
    comp = datos.get("compilacion") or {}
    if (datos.get("mostrada") != ctx.semver or not datos.get("congelado")
            or comp.get("etiqueta") != ctx.etiqueta
            or not ctx.commit.startswith(comp.get("commit") or "-")):
        raise FalloPaso(f"El .exe no reporta la entrega {ctx.semver} ({ctx.commit[:7]}): {datos}")
    print(f"   el .exe reporta {datos['completa']}")


def paso_setup(ctx: Contexto) -> None:
    ctx.carpeta = ctx.raiz / "entrega" / f"{ctx.etiqueta}_{ctx.fecha}"
    if ctx.carpeta.exists():
        raise FalloPaso(f"Ya existe {ctx.carpeta}")
    ctx.carpeta.mkdir(parents=True)
    shutil.copytree(ctx.raiz / "dist" / "Autoclave", ctx.carpeta / "Autoclave")
    _correr([ctx.iscc, "/Q", f"/DEntrega={ctx.carpeta}", f"/DAppVer={ctx.semver}",
             f"/DAppVerNum={ctx.num}", ISS], ctx.raiz, registro=ctx.carpeta / "iscc.log")
    if not (ctx.carpeta / f"Autoclave_Setup_{ctx.semver}.exe").is_file():
        raise FalloPaso(f"ISCC no dejó Autoclave_Setup_{ctx.semver}.exe")


def _escribir_lf(ruta: Path, texto: str) -> None:
    # con LF, como las sumas de la I: `sha256sum -c` no lee líneas con CRLF
    ruta.write_text(texto, encoding="utf-8", newline="\n")


def _manifiesto(carpeta: Path) -> list[str]:
    base = carpeta.parent
    return [f"{sha256(f)} *{f.relative_to(base).as_posix()}"
            for f in sorted(carpeta.rglob("*"), key=lambda x: x.as_posix()) if f.is_file()]


def paso_carpeta(ctx: Contexto) -> None:
    c = ctx.carpeta
    setup = f"Autoclave_Setup_{ctx.semver}.exe"
    zip_nombre = f"Autoclave_{ctx.etiqueta}.zip"
    with zipfile.ZipFile(c / zip_nombre, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((c / "Autoclave").rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(c).as_posix())
    with zipfile.ZipFile(c / zip_nombre) as z:
        if z.testzip() is not None:
            raise FalloPaso(f"{zip_nombre} dañado")
    manifiesto = _manifiesto(c / "Autoclave")
    _escribir_lf(c / "MANIFIESTO_CARPETA_Autoclave.sha256", "\n".join(manifiesto) + "\n")
    freeze = _correr([ctx.python_compilacion, "-m", "pip", "freeze"], ctx.raiz).stdout
    pyver = _correr([ctx.python_compilacion, "--version"], ctx.raiz).stdout.strip()
    (c / "entorno_build.txt").write_text(
        f"# {ctx.etiqueta} — {pyver} ({ctx.python_compilacion})\n{freeze}", encoding="utf-8")
    shutil.copy2(ctx.raiz / LEEME, c / "LEEME_INSTALACION.md")
    archivos = [setup, zip_nombre]
    if ctx.con_generador:
        shutil.copy2(ctx.raiz / "dist" / "GeneradorCodigos.exe", c / "GeneradorCodigos.exe")
        archivos.append("GeneradorCodigos.exe")
    archivos.append("Autoclave/Autoclave.exe")
    ctx.sumas = {a: sha256(c / a) for a in archivos}
    _escribir_lf(c / "SHA256SUMS.txt", "".join(f"{h} *{a}\n" for a, h in ctx.sumas.items()))
    usb = c / "usb"
    usb.mkdir()
    shutil.copy2(c / setup, usb / setup)
    _escribir_lf(usb / "SHA256SUMS.txt", f"{ctx.sumas[setup]} *{setup}\n")
    shutil.copy2(c / "LEEME_INSTALACION.md", usb / "LEEME_INSTALACION.md")
    drivers = ctx.raiz / "entrega" / "drivers"
    if drivers.is_dir():
        shutil.copytree(drivers, usb / "drivers")
    else:
        (usb / "drivers").mkdir()
    if sha256(usb / setup) != ctx.sumas[setup]:
        raise FalloPaso("La copia del Setup en usb/ no coincide")


PASOS = [("3 compilar", paso_compilar),
         ("4 verificar_entrega_neutra", paso_verificar_neutra),
         ("5 versión del .exe", paso_verificar_version_exe),
         ("6 Inno Setup", paso_setup),
         ("7 carpeta de entrega", paso_carpeta)]


def mensaje_etiqueta(ctx: Contexto, commits: list[str]) -> str:
    lineas = [f"Autoclave {ctx.semver}", "",
              f"Fecha: {ctx.fecha}", f"Commit: {ctx.commit}", f"AppVerNum: {ctx.num}", ""]
    lineas += [f"SHA-256 {a}: {h}" for a, h in ctx.sumas.items()]
    lineas += ["", "Commits desde la entrega anterior:"] + ([f"- {c}" for c in commits] or ["- (ninguno)"])
    return "\n".join(lineas) + "\n"


# ── secuencia completa (§2.2) ───────────────────────────────────────────────

def entregar(raiz: Path, python_compilacion: str, iscc: str, con_generador=False, pasos=None,
             git=None, ahora=None) -> int:
    """Pasos 1 a 10, ya superadas las verificaciones previas."""
    raiz = Path(raiz)
    git = git or (lambda *a: ic.git(raiz, *a))
    pasos = PASOS if pasos is None else pasos
    etiquetas = git("tag", "--list").split()
    n = calcular_n(etiquetas)
    semver = f"1.0.0-alpha.{n}"
    num = app_ver_num(semver)   # ValueError si N > 999, antes de tocar nada
    fecha = (ahora or datetime.now()).strftime("%Y-%m-%d")
    base = git("rev-parse", "HEAD").strip()
    anterior = f"v1.0.0-alpha.{n - 1}" if n > 1 else (
        ETIQUETA_PREVIA_AL_ESQUEMA if ETIQUETA_PREVIA_AL_ESQUEMA in etiquetas else None)
    commits = (git("log", "--oneline", "--no-merges", f"{anterior}..HEAD").splitlines()
               if anterior else [])
    print(f"1. N = {n}: {semver} (AppVerNum {num}); base {base[:7]}")

    build_info = raiz / ic.ARCHIVO
    build_info_previo = build_info.read_bytes() if build_info.exists() else None

    # 1-2: _version.py + historial, un commit (si algo falla aquí, los dos
    # archivos vuelven a HEAD: el árbol estaba limpio)
    try:
        archivo_version = raiz / ARCHIVO_VERSION
        archivo_version.write_text(
            reescribir_version(archivo_version.read_text(encoding="utf-8"), semver), encoding="utf-8")
        historial = raiz / HISTORIAL
        historial.write_text(agregar_al_historial(
            historial.read_text(encoding="utf-8"),
            entrada_historial(semver, fecha, base[:7], num, anterior, commits)), encoding="utf-8")
        git("add", ARCHIVO_VERSION.as_posix(), HISTORIAL.as_posix())
        git("commit", "-q", "-m", f"chore(ver): {semver}")
    except BaseException:
        git("reset", "-q", "--keep", base)
        git("checkout", "-q", base, "--", ARCHIVO_VERSION.as_posix(), HISTORIAL.as_posix())
        raise
    ctx = Contexto(raiz, semver, num, fecha, python_compilacion, iscc, con_generador,
                   commit=git("rev-parse", "HEAD").strip())
    print(f"2. commit {ctx.commit[:7]} chore(ver): {semver}")

    paso_actual = "8 etiqueta"
    try:
        for nombre, funcion in pasos:
            paso_actual = nombre
            print(f"{nombre} ...")
            funcion(ctx)
        paso_actual = "8 etiqueta"
        git("tag", "-a", ctx.etiqueta, ctx.commit, "-m", mensaje_etiqueta(ctx, commits))
    except BaseException as e:   # 9: deshacer, N no se consume (también con Ctrl+C)
        print(f"\nFALLÓ el paso {paso_actual}: {e}", file=sys.stderr)
        git("reset", "-q", "--keep", base)
        if build_info_previo is None:
            build_info.unlink(missing_ok=True)
        else:
            build_info.write_bytes(build_info_previo)
        if ctx.carpeta is not None and ctx.carpeta.exists():
            apartada = ctx.carpeta.with_name(
                f"{ctx.carpeta.name}.fallida-{datetime.now().strftime('%H%M%S')}")
            ctx.carpeta.rename(apartada)
            print(f"La carpeta incompleta quedó en {apartada}", file=sys.stderr)
        print(f"Deshecho: HEAD vuelve a {base[:7]}, sin etiqueta {ctx.etiqueta}; "
              f"N = {n} sigue libre.", file=sys.stderr)
        if isinstance(e, KeyboardInterrupt):
            raise
        return 1
    print(f"8. etiqueta anotada {ctx.etiqueta} sobre {ctx.commit[:7]}")
    print(f"\nEntrega lista en {ctx.carpeta}")
    print(f"Para publicarla (no se ejecuta):\n   git push origin {RAMA} {ctx.etiqueta}")
    return 0


def _python_compilacion_defecto() -> str | None:
    if os.environ.get("AUTOCLAVE_PYTHON_COMPILACION"):
        return os.environ["AUTOCLAVE_PYTHON_COMPILACION"]
    venv = RAIZ.parent / "_venv_t8_producto" / "Scripts" / "python.exe"
    return str(venv) if venv.exists() else None


def _iscc_defecto() -> str:
    return os.environ.get("AUTOCLAVE_ISCC") or str(
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Entrega 1.0.0-alpha.N (etapa VER)")
    ap.add_argument("--con-generador", action="store_true",
                    help="compila también GeneradorCodigos.spec y lo deja en la carpeta (fuera de usb/)")
    ap.add_argument("--python-compilacion", default=_python_compilacion_defecto(),
                    help="python con PyInstaller (defecto: AUTOCLAVE_PYTHON_COMPILACION o "
                         "..\\_venv_t8_producto)")
    ap.add_argument("--iscc", default=_iscc_defecto(), help="ISCC.exe de Inno Setup 6")
    ap.add_argument("--sin-suite-serie", action="store_true",
                    help="no repetir en serie las rojas de la suite en paralelo")
    # 28-oct: entrega rápida sin la suite (decisión de Cristian); el resto de
    # verificaciones previas (rama dev, árbol limpio, herramientas) sigue igual
    ap.add_argument("--sin-suite", action="store_true",
                    help="NO corre la suite de pruebas (entrega rápida, bajo responsabilidad de quien compila)")
    args = ap.parse_args(argv)

    git = lambda *a: ic.git(RAIZ, *a)  # noqa: E731
    print("Verificaciones previas ...")
    if args.sin_suite:
        print("AVISO: --sin-suite: la suite de pruebas NO se corre en esta entrega")
    previas = verificaciones_previas(
        git, (lambda: (True, "omitida (--sin-suite)")) if args.sin_suite
        else (lambda: correr_suite_real(sys.executable, RAIZ, not args.sin_suite_serie)),
        herramientas=[("el python de compilación", args.python_compilacion),
                      ("ISCC.exe", args.iscc)])
    for a in previas.avisos:
        print(f"AVISO: {a}")
    if previas.errores:
        for e in previas.errores:
            print(f"BLOQUEA: {e}", file=sys.stderr)
        print("Entrega no iniciada: no se tocó nada.", file=sys.stderr)
        return 2
    return entregar(RAIZ, args.python_compilacion, args.iscc, args.con_generador)


if __name__ == "__main__":
    sys.exit(main())
