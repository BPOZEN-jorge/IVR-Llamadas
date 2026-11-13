import hmac
import json
import random
import threading
import time as time_lib
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from ciclo_diario import HORA_ACTIVACION, aplicar_ciclo_diario
from github import Github, GithubException

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Turnero de Ventas: Activación y Asignaciones",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# SEPARACIÓN DE ARCHIVOS PARA PREVENIR CONFLICTOS CONCURRENTES
FILE_TURNOS = "turnos_orden.json"      # Posiciones, historial de llamadas y saltos manuales del admin
FILE_LOG_SALTOS = "saltos_log.json"    # Mapeo temporal independiente de TODOS los saltos (agente y admin)

TIPO_SALTO_LLAMADA = "LLAMADA"          # Salto por llamada atendida por el agente (con PIN)
TIPO_SALTO_ADMIN = "SALTO_ADMIN"        # Salto manual decidido por el admin (con motivo)
TIPO_INACTIVO = "INACTIVO"              # Admin marca inactivo -> se va al final de la fila
TIPO_REACTIVADO = "REACTIVADO"          # Admin reactiva -> entra al final de los activos
TIPO_RESET_DIARIO = "RESET_DIARIO"      # 00:00 Colombia: todos quedan inactivos
MOTIVO_LLEGADA = "Llegada / inicio de jornada"

# ==========================================
# DATOS INICIALES DE USUARIOS
# ==========================================
USUARIOS_INICIALES = [
    {"posicion": 1, "real": "Alisson Correa Gaviria", "alias": "Alisson"},
    {"posicion": 2, "real": "Ana Maria Sanchez Gamboa", "alias": "Maria Sanchez"},
    {"posicion": 3, "real": "Andrea Mileidy londoño Bedoya", "alias": "Andrea Valverde"},
    {"posicion": 4, "real": "Angie Valeria Quirama Hernández", "alias": "Valeria Hernandez"},
    {"posicion": 5, "real": "Angie Vanessa García", "alias": "Maria Antonia García"},
    {"posicion": 6, "real": "Brayan Andrey Bustamante", "alias": "Marcos Garcia"},
    {"posicion": 7, "real": "Carlos Alberto Herrera Cardeño", "alias": "Carlos Herrera / Alberto Fernandez"},
    {"posicion": 8, "real": "Claudia Marcela Manco Vargas", "alias": "Marcela"},
    {"posicion": 9, "real": "Cristian David Acosta Montoya", "alias": "Manuel Vasquez"},
    {"posicion": 11, "real": "Evelin Acevedo Cortés", "alias": "Gabriela"},
    {"posicion": 12, "real": "Gustavo Adolfo Barrientos Serna", "alias": "Gustavo"},
    {"posicion": 13, "real": "Iris Sabiana Cano Cano", "alias": "Maria Cano"},
    {"posicion": 15, "real": "Johana Osorio Bedoya", "alias": "Johana Sanchez"},
    {"posicion": 16, "real": "Juan Esteban Acevedo Garces", "alias": "Juan Esteban"},
    {"posicion": 17, "real": "Juan Sebastian Serna Sepulveda", "alias": "Juan Sebastian"},
    {"posicion": 19, "real": "Karen Herrera Gonzalez", "alias": "Karen"},
    {"posicion": 21, "real": "Libia Paola Romero Cantillo", "alias": "Paola Romero"},
    {"posicion": 22, "real": "Linda Liceth Pérez Pineda", "alias": "Linda Pérez / Elena Pérez"},
    {"posicion": 23, "real": "Luis Alberto Lozano Ibarra", "alias": "Luis Lozano"},
    {"posicion": 24, "real": "Manuela villegas Giraldo", "alias": "Manuela Villegas"},
    {"posicion": 25, "real": "María Karolina Viana Cancio", "alias": "Karolina"},
    {"posicion": 26, "real": "Mateo Cano Hincapié", "alias": "Antonio de la villa"},
    {"posicion": 27, "real": "Omar David Barboza Carbonero", "alias": "Omar"},
    {"posicion": 28, "real": "Oscar José Llanos Mendinueta", "alias": "Oscar"},
    {"posicion": 29, "real": "Paula Andrea Guzman Jaramillo", "alias": "Paula"},
    {"posicion": 30, "real": "Rosa Elvira Agamez López", "alias": "Flor Lopez"},
    {"posicion": 31, "real": "Sara Gómez Bayona", "alias": "Sara Gómez"},
    {"posicion": 34, "real": "Tomas Castaño Gómez", "alias": "Tomas"},
    {"posicion": 35, "real": "Viviana Pacheco Córdoba", "alias": "Viviana Gómez"},
    {"posicion": 36, "real": "Yarlen Biviana Son Cedeño", "alias": "Maria Rodriguez"},
    {"posicion": 37, "real": "Yarnedis Cecilia Urrutia Pérez", "alias": "Cecilia López"},
    {"posicion": 38, "real": "Yeismer Miranda Ramirez", "alias": "Leo Miranda"},
    {"posicion": 39, "real": "Yesica Paola Lopez Arango", "alias": "Yesica López"},
    {"posicion": 40, "real": "Yesly Marilyn Carrero Rivera", "alias": "Marilyn Carrero"},
]


def obtener_fecha_hora_colombia() -> datetime:
    """Retorna objeto datetime actual en Zona Horaria de Colombia."""
    return datetime.now(ZoneInfo("America/Bogota"))


def obtener_hora_colombia_str() -> str:
    """Retorna la fecha y hora actual formateada en hora de Colombia (America/Bogota)."""
    return obtener_fecha_hora_colombia().strftime("%Y-%m-%d %H:%M:%S")


# ==========================================
# CONEXIÓN Y OPERACIONES ATÓMICAS EN GITHUB
# ==========================================
@st.cache_resource(show_spinner=False)
def _conectar_repo(token: str, repo_name: str):
    """Se reutiliza la conexión: evita una llamada extra a la API de GitHub en cada lectura/escritura."""
    return Github(token).get_repo(repo_name)


def obtener_repositorio_github():
    token = st.secrets.get("github", {}).get("token")
    repo_name = st.secrets.get("github", {}).get("repo")
    if not token or not repo_name:
        st.error("⚠️ Configuración incompleta de GitHub en los secretos (`st.secrets`).")
        st.stop()
    return _conectar_repo(token, repo_name)


# ==========================================
# ASIGNACIONES DESDE EL TURNERO ATC (REPO [github].repo_atc)
# ==========================================
FILE_ATC = "atc_ventas_ruleta.json"   # En el repo de ATC: historial de asignaciones que hacen los ATC
REPO_ATC_POR_DEFECTO = "BPOZEN-jorge/ATC-Llamadas"
COORDINADORES = ["Jose", "Paula", "Victor"]   # Rotación del turnero (igual que en ATC)
COORDINADOR_POR_AGENTE = {
    "Alisson Correa Gaviria": "Paula", "Ana Maria Sanchez Gamboa": "Paula", "Andrea Mileidy londoño Bedoya": "Paula",
    "Angie Valeria Quirama Hernández": "Victor", "Angie Vanessa García": "Jose", "Brayan Andrey Bustamante": "Paula",
    "Carlos Alberto Herrera Cardeño": "Jose", "Claudia Marcela Manco Vargas": "Paula",
    "Cristian David Acosta Montoya": "Jose", "Evelin Acevedo Cortés": "Victor",
    "Gustavo Adolfo Barrientos Serna": "Victor", "Iris Sabiana Cano Cano": "Paula",
    "Johana Osorio Bedoya": "Paula", "Juan Esteban Acevedo Garces": "Jose", "Juan Sebastian Serna Sepulveda": "Paula",
    "Karen Herrera Gonzalez": "Victor", "Libia Paola Romero Cantillo": "Victor", "Linda Liceth Pérez Pineda": "Paula",
    "Luis Alberto Lozano Ibarra": "Paula", "Manuela villegas Giraldo": "Jose", "María Karolina Viana Cancio": "Victor",
    "Mateo Cano Hincapié": "Jose", "Omar David Barboza Carbonero": "Paula", "Oscar José Llanos Mendinueta": "Jose",
    "Paula Andrea Guzman Jaramillo": "Paula", "Rosa Elvira Agamez López": "Paula", "Sara Gómez Bayona": "Jose",
    "Tomas Castaño Gómez": "Paula", "Viviana Pacheco Córdoba": "Victor",
    "Yarlen Biviana Son Cedeño": "Paula", "Yarnedis Cecilia Urrutia Pérez": "Jose", "Yeismer Miranda Ramirez": "Victor",
    "Yesica Paola Lopez Arango": "Victor", "Yesly Marilyn Carrero Rivera": "Victor",
}
TIPOS_ASIGNACION = {                  # Tipo en ATC -> cómo se le muestra al asesor
    "Transferido (turno)": "Turno",
    "Siguiente en Ruleta": "Turno",
    "Reasignado al Mismo Agente": "Cliente recurrente",
}
REFRESCO_ASIGNACIONES = 3             # Segundos entre actualizaciones de "Mis asignaciones"
MAX_INTENTOS_PIN_ASESOR = 5


@st.cache_resource(show_spinner=False)
def _cache_lecturas() -> dict:
    return {"lock": threading.Lock(), "items": {}}


def leer_rapido(repo_name: str, file_path: str, max_edad: float = 1.0):
    """
    Lectura para MOSTRAR, compartida entre todas las sesiones, con petición condicional (ETag):
    si el archivo no cambió, GitHub responde 304 y esa consulta NO gasta el límite de la API.
    """
    cache = _cache_lecturas()
    clave = f"{repo_name}/{file_path}"
    with cache["lock"]:
        item = cache["items"].get(clave)
        if item and time_lib.time() - item["t"] < max_edad:
            return item["data"]
        gh = st.secrets.get("github", {})
        headers = {
            "Authorization": f"Bearer {gh.get('token', '')}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if item:
            headers["If-None-Match"] = item["etag"]
        try:
            r = requests.get(f"https://api.github.com/repos/{repo_name}/contents/{file_path}",
                             params={"ref": gh.get("branch", "main")}, headers=headers, timeout=15)
        except requests.RequestException:
            if item:
                return item["data"]  # sin conexión momentánea: se muestra lo último conocido
            raise
        if r.status_code == 304 and item:
            item["t"] = time_lib.time()
            return item["data"]
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        cache["items"][clave] = {"etag": r.headers.get("ETag", ""), "data": data, "t": time_lib.time()}
        return data


def asignaciones_atc(nombre_real: str | None = None, fecha: str | None = None) -> list | None:
    """
    Clientes que los ATC asignaron (más recientes primero), del repo [github].repo_atc o ATC-Llamadas.
    None si no se pudo leer (token, red o GitHub caído): la vista muestra un aviso en vez de caerse.
    """
    repo_atc = st.secrets.get("github", {}).get("repo_atc") or REPO_ATC_POR_DEFECTO
    try:
        historial = (leer_rapido(repo_atc, FILE_ATC) or {}).get("historial", [])
    except Exception:  # noqa: BLE001
        return None
    filas = [h for h in historial if h.get("tipo") in TIPOS_ASIGNACION]
    if nombre_real:
        filas = [h for h in filas if h.get("agente_ventas_real") == nombre_real]
    if fecha:
        filas = [h for h in filas if str(h.get("fecha_hora", "")).startswith(fecha)]
    return filas


def orden_turnero(turnos: list, cambios_ivr: list, datos_atc: dict, hoy: str) -> list:
    """
    ORDEN ÚNICO DEL TURNERO: esta función es idéntica en las apps IVR y ATC, así las dos muestran la misma fila.
    Solo asesores ACTIVOS en IVR.
    1) Coordinador en rotación COORDINADORES desde el coordinador en turno de ATC (si no tiene activos, se salta).
    2) Dentro del coordinador: menos asignaciones hoy -> a quien hace más tiempo no le toca ->
       orden de activación en IVR ("activo desde": quien se activó antes va primero) -> nombre.
    Devuelve [{"real", "alias", "coordinador"}] en orden; el primero es el turno disponible.
    """
    activo_desde = {}
    for c in cambios_ivr:
        fecha, nombre = str(c.get("fecha_hora", "")), c.get("nombre_real")
        if c.get("tipo") == "REACTIVADO" and nombre and fecha.startswith(hoy):
            activo_desde[nombre] = max(activo_desde.get(nombre, ""), fecha)

    asignaciones, ultimo = {}, {}
    for h in datos_atc.get("historial", []):
        fecha, nombre, tipo = str(h.get("fecha_hora", "")), h.get("agente_ventas_real"), h.get("tipo")
        if not nombre or not fecha.startswith(hoy):
            continue
        if tipo in ("Transferido (turno)", "Siguiente en Ruleta"):
            asignaciones[nombre] = asignaciones.get(nombre, 0) + 1
        if tipo in ("Transferido (turno)", "Siguiente en Ruleta", "No disponible (saltado)"):
            ultimo[nombre] = max(ultimo.get(nombre, ""), fecha)

    por_coord = {}
    for c in COORDINADORES:
        candidatos = [t for t in turnos if t.get("activo", True) and COORDINADOR_POR_AGENTE.get(t["real"]) == c]
        candidatos.sort(key=lambda t: (asignaciones.get(t["real"], 0), ultimo.get(t["real"], ""),
                                       activo_desde.get(t["real"], "~"), t["real"]))
        por_coord[c] = candidatos

    # Si ATC aún no hizo su reset de hoy, la rotación del día empieza igual por el primer coordinador
    puntero = int(datos_atc.get("puntero_coordinador", 0)) if datos_atc.get("ultimo_reset_diario", "") >= hoy else 0
    puntero %= len(COORDINADORES)
    usados = {c: 0 for c in COORDINADORES}
    resultado = []
    while True:
        for salto in range(len(COORDINADORES)):
            c = COORDINADORES[(puntero + salto) % len(COORDINADORES)]
            if usados[c] < len(por_coord[c]):
                t = por_coord[c][usados[c]]
                usados[c] += 1
                resultado.append({"real": t["real"], "alias": t["alias"], "coordinador": c})
                puntero = (puntero + salto + 1) % len(COORDINADORES)
                break
        else:
            return resultado


def datos_atc_o_none() -> dict | None:
    """Archivo del turnero ATC (asignaciones y coordinador en turno). None si no se pudo leer."""
    try:
        return leer_rapido(st.secrets.get("github", {}).get("repo_atc") or REPO_ATC_POR_DEFECTO, FILE_ATC) or {}
    except Exception:  # noqa: BLE001
        return None


def asesor_por_pin(pin: str) -> str | None:
    """El PIN de IVR identifica al asesor (secrets [pins])."""
    pin_clean = (pin or "").strip()
    if not pin_clean:
        return None
    encontrado = None
    for nombre, correcto in st.secrets.get("pins", {}).items():
        if hmac.compare_digest(pin_clean.encode(), str(correcto).strip().encode()):
            encontrado = nombre
    return encontrado


import base64


class ConflictoGithub(Exception):
    """Otro usuario guardó el mismo archivo entre nuestra lectura y nuestra escritura."""


def sha_leido(file_path: str):
    """SHA de la última lectura de este archivo en esta ejecución (para escritura segura)."""
    return st.session_state.get(f"_sha_{file_path}")


def ejecutar_con_reintentos(operacion, intentos: int = 4):
    """
    Ejecuta una operación de lectura+escritura. Si otro usuario guardó en medio (ConflictoGithub),
    se repite TODA la operación con datos frescos, así nunca se pisan los cambios del otro.
    """
    for _ in range(intentos):
        try:
            return operacion()
        except ConflictoGithub:
            time_lib.sleep(0.3 + random.random() * 0.7)
    return False, "❌ Varias personas guardaron al mismo tiempo. Espera un momento e intenta nuevamente."


def leer_json_github(file_path: str, default_payload: dict) -> dict:
    """Lee un archivo JSON individual directamente desde GitHub con soporte para archivos >1MB."""
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    try:
        content = repo.get_contents(file_path, ref=branch)
        st.session_state[f"_sha_{file_path}"] = content.sha

        # Si la API devuelve Base64 (archivos pequeños < 1MB)
        if getattr(content, "encoding", None) == "base64":
            raw_data = content.decoded_content.decode("utf-8")
        else:
            # Para archivos > 1MB o con otro encoding, se consulta el blob directamente por su SHA
            blob = repo.get_git_blob(content.sha)
            raw_data = base64.b64decode(blob.content).decode("utf-8")
            
        return json.loads(raw_data)
        
    except GithubException as e:
        if e.status == 404:
            escribir_json_github(file_path, default_payload, f"Inicializar {file_path}")
            return default_payload
        st.error(f"Error leyendo {file_path}: {e}")
        st.stop()


def escribir_json_github(file_path: str, payload: dict, mensaje_commit: str, retries: int = 3,
                         sha_esperado: str | None = None):
    """
    Guarda un JSON en GitHub.
    - Con sha_esperado (el SHA de la lectura): escritura segura. Si otro usuario guardó en medio,
      GitHub responde 409 y se lanza ConflictoGithub para repetir la operación con datos frescos.
    - Sin sha_esperado: escritura directa (solo para crear archivos que no existen).
    """
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    json_str = json.dumps(payload, indent=4, ensure_ascii=False)

    if sha_esperado is not None:
        try:
            resultado = repo.update_file(
                path=file_path,
                message=f"Auto-update: {mensaje_commit}",
                content=json_str,
                sha=sha_esperado,
                branch=branch,
            )
            st.session_state[f"_sha_{file_path}"] = resultado["content"].sha
            return True
        except GithubException as e:
            if e.status == 409 or (e.status == 422 and "sha" in str(e.data).lower()):
                raise ConflictoGithub(file_path) from e
            st.error(f"❌ Error al guardar en {file_path}: {e}")
            return False

    for intento in range(retries):
        try:
            try:
                content = repo.get_contents(file_path, ref=branch)
                repo.update_file(
                    path=file_path,
                    message=f"Auto-update: {mensaje_commit}",
                    content=json_str,
                    sha=content.sha,
                    branch=branch,
                )
            except GithubException as ex:
                if ex.status == 404:
                    repo.create_file(
                        path=file_path,
                        message=f"Crear archivo: {mensaje_commit}",
                        content=json_str,
                        branch=branch,
                    )
                else:
                    raise ex
            return True
        except GithubException as e:
            if intento < retries - 1:
                time_lib.sleep(0.5)
            else:
                st.error(f"❌ Error al guardar en {file_path} tras varios intentos: {e}")
                return False


# ==========================================
# LÓGICA DE GESTIÓN DEL LOG INDEPENDIENTE DE SALTOS
# ==========================================
def guardar_eventos_log_salto(eventos: list):
    """Guarda uno o varios registros en saltos_log.json (un solo commit) para mapeo temporal."""
    if not eventos:
        return
    primero = eventos[0]
    tipo = primero.get("tipo")
    if tipo == TIPO_SALTO_LLAMADA:
        msg = f"Log Salto: {primero.get('alias')} (ID: {primero.get('call_id')})"
    elif len(eventos) == 1:
        msg = f"Log {tipo}: {primero.get('alias')} - {primero.get('motivo', '')[:60]}"
    else:
        msg = f"Log cambios de estado: {len(eventos)} agentes - {primero.get('motivo', '')[:60]}"

    # El log se reintenta por su cuenta: el cambio en turnos_orden.json ya quedó guardado.
    for _ in range(5):
        log_actual = leer_json_github(FILE_LOG_SALTOS, {"saltos": []})
        log_actual.setdefault("saltos", [])
        for ev in eventos:
            ev["id_evento"] = len(log_actual["saltos"]) + 1
            log_actual["saltos"].insert(0, dict(ev))
        try:
            escribir_json_github(FILE_LOG_SALTOS, log_actual, msg, sha_esperado=sha_leido(FILE_LOG_SALTOS))
            return
        except ConflictoGithub:
            time_lib.sleep(0.3 + random.random() * 0.7)
    st.warning("⚠️ El cambio se guardó, pero no se pudo escribir en el log de cambios (mucha concurrencia).")


def guardar_evento_log_salto(datos_salto: dict):
    guardar_eventos_log_salto([datos_salto])


# ==========================================
# LÓGICA DE LECTURA DE DATOS
# ==========================================
def _default_turnos() -> dict:
    return {
        "turnos": [dict(u) for u in USUARIOS_INICIALES],
        "historial": [],
        "saltos_admin": [],
    }


def obtener_estructura_completa_fresca() -> tuple[list, list, list]:
    """Carga orden de turnos (ya priorizado por saltos del día), historial y saltos manuales desde GitHub."""
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    turnos_lista = _fila_priorizada(data_turnos)
    historial = data_turnos.get("historial", [])
    saltos_admin = data_turnos.get("saltos_admin", [])
    st.session_state.data_turnos_cache = data_turnos
    return turnos_lista, historial, saltos_admin


def obtener_lista_turnos() -> list:
    turnos, _, _ = obtener_estructura_completa_fresca()
    return turnos


def _limpiar_turnos(turnos: list) -> list:
    """
    Deja solo los campos que se persisten y solo a quienes están hoy en el equipo de ventas
    (USUARIOS_INICIALES): quien sale del equipo no vuelve a la fila. Si no hay 'activo' se asume activo.
    """
    equipo = {u["real"] for u in USUARIOS_INICIALES}
    return [
        {"posicion": t["posicion"], "real": t["real"], "alias": t["alias"], "activo": bool(t.get("activo", True))}
        for t in turnos if t["real"] in equipo
    ]


def _renumerar(turnos: list) -> list:
    for idx, t in enumerate(turnos, start=1):
        t["posicion"] = idx
    return turnos


def _ordenar_fila(turnos: list) -> list:
    """Activos arriba (en su orden) e inactivos siempre abajo (en su orden)."""
    turnos = _limpiar_turnos(turnos)
    activos = [t for t in turnos if t["activo"]]
    inactivos = [t for t in turnos if not t["activo"]]
    return _renumerar(activos + inactivos)


def _snapshot_fila(turnos: list) -> list:
    return [
        {"posicion": t["posicion"], "alias": t["alias"], "real": t["real"], "activo": bool(t.get("activo", True))}
        for t in turnos
    ]


# ==========================================
# PRIORIDAD POR SALTOS DEL DÍA
# ==========================================
def contar_saltos_hoy(data_turnos: dict) -> dict:
    """
    Cuenta por agente (nombre real) los saltos de HOY (hora Colombia):
    - "ivr": llamadas IVR registradas con PIN (historial). Es lo ÚNICO que define la prioridad.
    - "admin": saltos manuales del admin (saltos_admin). Solo informativo, NO cuenta.
    Solo lee lo que ya existe en turnos_orden.json; no modifica datos.
    """
    hoy = obtener_fecha_hora_colombia().strftime("%Y-%m-%d")
    conteos = {}

    def sumar(registro: dict, clave: str):
        fecha = str(registro.get("fecha_hora", ""))
        nombre = registro.get("nombre_real")
        if not nombre or not fecha.startswith(hoy):
            return
        c = conteos.setdefault(nombre, {"ivr": 0, "admin": 0, "ultima_ivr": ""})
        c[clave] += 1
        if clave == "ivr":
            c["ultima_ivr"] = max(c["ultima_ivr"], fecha)

    for h in data_turnos.get("historial", []):
        sumar(h, "ivr")
    for s in data_turnos.get("saltos_admin", []):
        sumar(s, "admin")
    return conteos


def horas_activacion_hoy(data_turnos: dict) -> dict:
    """
    Por agente (nombre real), a partir de cambios_estado de HOY (solo lectura):
    - "llegada": primera vez que se activó hoy.
    - "activo_desde": última activación de hoy (si luego lo inactivaron y reactivaron, cambia).
    """
    hoy = obtener_fecha_hora_colombia().strftime("%Y-%m-%d")
    horas = {}
    for c in data_turnos.get("cambios_estado", []):
        fecha = str(c.get("fecha_hora", ""))
        nombre = c.get("nombre_real")
        if c.get("tipo") != TIPO_REACTIVADO or not nombre or not fecha.startswith(hoy):
            continue
        h = horas.setdefault(nombre, {"llegada": fecha, "activo_desde": fecha})
        h["llegada"] = min(h["llegada"], fecha)
        h["activo_desde"] = max(h["activo_desde"], fecha)
    return horas


def _aplicar_prioridad(turnos: list, conteos: dict) -> list:
    """
    Orden efectivo de la fila:
    1) Activos primero, inactivos al final (igual que antes).
    2) Entre activos, quien tenga MENOS llamadas IVR registradas hoy va primero.
       Los saltos del admin no suman: solo mandan al final de su grupo.
    3) A igualdad de llamadas IVR se respeta el orden actual (llegada / rotación): el sort es estable.
    """
    fila = _ordenar_fila(sorted(turnos, key=lambda x: x["posicion"]))
    activos = [t for t in fila if t["activo"]]
    inactivos = [t for t in fila if not t["activo"]]
    activos.sort(key=lambda t: conteos.get(t["real"], {}).get("ivr", 0))
    return _renumerar(activos + inactivos)


def _fila_priorizada(data_turnos: dict) -> list:
    return _aplicar_prioridad(data_turnos.get("turnos", USUARIOS_INICIALES), contar_saltos_hoy(data_turnos))


def _primer_activo(turnos: list):
    return next((t for t in turnos if t.get("activo", True)), None)


def _mover_al_final_de_activos(turnos: list, nombre_real: str) -> list:
    """
    Saca al agente de su posición y lo pone al FINAL de los activos (justo antes de los inactivos).
    Se usa al atender una llamada, en el salto manual del admin y al reactivar a alguien.
    """
    fila = _ordenar_fila(turnos)
    agente = next(t for t in fila if t["real"] == nombre_real)
    resto = [t for t in fila if t["real"] != nombre_real]
    agente["activo"] = True
    n_activos = sum(1 for t in resto if t["activo"])
    resto.insert(n_activos, agente)
    return _renumerar(resto)


def _mover_al_final_como_inactivo(turnos: list, nombre_real: str) -> list:
    """Marca al agente inactivo y lo manda al final de la fila (pierde su posición anterior)."""
    fila = _ordenar_fila(turnos)
    agente = next(t for t in fila if t["real"] == nombre_real)
    resto = [t for t in fila if t["real"] != nombre_real]
    agente["activo"] = False
    return _renumerar(resto + [agente])


# ==========================================
# VALIDACIONES DEL ADMIN
# ==========================================
def _validar_registrado_por(registrado_por: str):
    """Quien hace el cambio debe identificarse (antes quedaba 'Admin' si se dejaba vacío)."""
    nombre = (registrado_por or "").strip()
    if len(nombre) < 2:
        return None, "⚠️ Escribe tu nombre en **Tu nombre (admin)** en la barra lateral antes de guardar cambios."
    return nombre, None


# ==========================================
# ACTIVO / INACTIVO (ADMIN) -> INACTIVO SE VA AL FINAL SIN RESPETAR POSICIÓN
# ==========================================
def guardar_cambios_estado_admin(estados_seleccionados: dict, motivo: str, registrado_por: str) -> tuple[bool, str]:
    return ejecutar_con_reintentos(lambda: _guardar_cambios_estado_admin(estados_seleccionados, motivo, registrado_por))


def _guardar_cambios_estado_admin(estados_seleccionados: dict, motivo: str, registrado_por: str) -> tuple[bool, str]:
    """
    estados_seleccionados: {nombre_real: activo(bool)} SOLO con los interruptores que el admin movió.
    - Activo -> Inactivo: se va al final de la fila (pierde su posición).
    - Inactivo -> Activo: entra al final de los activos (no recupera su posición anterior).
    - Si otro admin ya lo dejó en ese estado, no se toca (no se duplica ni se revierte).
    """
    motivo_clean = motivo.strip()
    registrado_por_clean, error = _validar_registrado_por(registrado_por)
    if error:
        return False, error

    turnos, _, _ = obtener_estructura_completa_fresca()
    estado_actual = {t["real"]: bool(t.get("activo", True)) for t in turnos}
    cambios = [(nombre, nuevo) for nombre, nuevo in estados_seleccionados.items()
               if nombre in estado_actual and estado_actual[nombre] != nuevo]

    if not cambios:
        if estados_seleccionados:
            return False, "ℹ️ No hay nada que guardar: esa(s) persona(s) ya estaban en ese estado (quizá otro admin lo hizo)."
        return False, "ℹ️ No moviste ningún interruptor."
    if len(motivo_clean) < 5:
        return False, "⚠️ Debes escribir el motivo del cambio de estado (mínimo 5 caracteres)."

    now_col = obtener_hora_colombia_str()
    fila = _ordenar_fila(turnos)
    eventos = []
    for nombre, nuevo_activo in cambios:
        snapshot = _snapshot_fila(fila)
        agente = next(t for t in fila if t["real"] == nombre)
        pos_previa = agente["posicion"]
        if nuevo_activo:
            fila = _mover_al_final_de_activos(fila, nombre)
        else:
            fila = _mover_al_final_como_inactivo(fila, nombre)
        eventos.append({
            "tipo": TIPO_REACTIVADO if nuevo_activo else TIPO_INACTIVO,
            "fecha_hora": now_col,
            "call_id": "",
            "telefono": "",
            "nombre_real": nombre,
            "alias": agente["alias"],
            "posicion_al_saltar": pos_previa,
            "motivo": motivo_clean,
            "registrado_por": registrado_por_clean,
            "orden_previo_snapshot": snapshot,
        })

    data_turnos = st.session_state.data_turnos_cache  # misma lectura fresca de arriba
    data_turnos["turnos"] = fila
    data_turnos["turnos"] = _fila_priorizada(data_turnos)
    data_turnos.setdefault("cambios_estado", [])
    for ev in eventos:
        data_turnos["cambios_estado"].insert(0, {
            "fecha_hora": ev["fecha_hora"],
            "tipo": ev["tipo"],
            "nombre_real": ev["nombre_real"],
            "alias": ev["alias"],
            "posicion_previa": ev["posicion_al_saltar"],
            "motivo": ev["motivo"],
            "registrado_por": ev["registrado_por"],
        })

    resumen = ", ".join(f"{e['alias']}→{'Activo' if e['tipo'] == TIPO_REACTIVADO else 'Inactivo'}" for e in eventos)
    if escribir_json_github(FILE_TURNOS, data_turnos, f"Admin: estados ({resumen[:120]}) - Motivo: {motivo_clean[:60]}",
                            sha_esperado=sha_leido(FILE_TURNOS)):
        guardar_eventos_log_salto(eventos)
        return True, f"✅ Se guardaron {len(eventos)} cambio(s) de estado: {resumen}"
    return False, "❌ Hubo un fallo temporal de comunicación con GitHub. Intenta nuevamente."


def registrar_llegada(nombre_real: str, registrado_por: str) -> tuple[bool, str]:
    """Activa a una persona por llegada. Entra al final de los activos (orden de llegada = orden de turno)."""
    return guardar_cambios_estado_admin({nombre_real: True}, MOTIVO_LLEGADA, registrado_por)


# ==========================================
# RESET DIARIO 00:00 (HORA COLOMBIA)
# ==========================================
def aplicar_reset_diario_si_corresponde():
    """
    Ciclo diario (ciclo_diario.py): 00:00 todos inactivos y 03:00 todos activos (hora Colombia).
    Lo hace la tarea programada de GitHub; esto es el respaldo: si aún no se hizo, lo aplica la primera
    carga de la app. Se revisa una vez por sesión en cada tramo del día (antes y después de las 03:00).
    """
    ahora = obtener_fecha_hora_colombia()
    tramo = f"{ahora:%Y-%m-%d}-{'activacion' if ahora.hour >= HORA_ACTIVACION else 'reset'}"
    if st.session_state.get("reset_diario_verificado") == tramo:
        return
    resultado = ejecutar_con_reintentos(_reset_diario)
    if resultado is True or resultado is None:  # None = ya estaba hecho
        st.session_state.reset_diario_verificado = tramo  # si falló, se reintenta en la próxima carga


def _reset_diario():
    """Devuelve None si no había nada que hacer, False si no se pudo guardar; con conflicto se repite."""
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    acciones = aplicar_ciclo_diario(data_turnos, obtener_fecha_hora_colombia())
    if not acciones:
        return None
    data_turnos["turnos"] = _renumerar(_ordenar_fila(data_turnos.get("turnos", USUARIOS_INICIALES)))
    nombres = {"reset": "reset 00:00 (todos inactivos)",
               "activacion": f"activación {HORA_ACTIVACION:02d}:00 (todos activos)",
               "inicializar": "activación automática programada desde mañana"}
    texto = " y ".join(nombres.get(a, a) for a in acciones)
    if not escribir_json_github(FILE_TURNOS, data_turnos, f"Auto: ciclo diario - {texto}",
                                sha_esperado=sha_leido(FILE_TURNOS)):
        return False
    return True


def obtener_cambios_estado_df() -> pd.DataFrame:
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    cambios = data_turnos.get("cambios_estado", [])
    if not cambios:
        return pd.DataFrame()
    return pd.DataFrame(cambios).rename(columns={
        "fecha_hora": "Fecha / Hora (Colombia)",
        "tipo": "Cambio",
        "nombre_real": "Nombre Real",
        "alias": "Alias",
        "posicion_previa": "Posición previa",
        "motivo": "Motivo",
        "registrado_por": "Registrado por",
    })


# ==========================================
# INTERFAZ DE NAVEGACIÓN Y VISTAS
# ==========================================
aplicar_reset_diario_si_corresponde()

st.sidebar.title("📌 Portal de Turnos")
opcion_vista = st.sidebar.radio("Navegación:", ["📋 Mis asignaciones ATC", "🛡️ Vista Administrador"])

# ------------------------------------------
# VISTA: ADMINISTRADOR
# ------------------------------------------
if opcion_vista == "🛡️ Vista Administrador":
    st.title("🛡️ Panel de Control - Administrador")

    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False

    if not st.session_state.admin_logged:
        with st.form("form_admin_pass"):
            admin_pass = st.text_input("Contraseña de Administrador:", type="password")
            btn_admin = st.form_submit_button("Ingresar", use_container_width=True)
        if btn_admin:
            if admin_pass == st.secrets.get("passwords", {}).get("admin_password", "admin123"):
                st.session_state.admin_logged = True
                st.success("✅ Acceso concedido.")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
    else:
        admin_nombre = st.sidebar.text_input(
            "👤 Tu nombre (admin)", key="admin_nombre", placeholder="Obligatorio para guardar cambios",
            help="Queda registrado en cada activación e inactivación que hagas.",
        )
        if st.sidebar.button("Cerrar Sesión Admin", use_container_width=True):
            st.session_state.admin_logged = False
            st.rerun()

        tab_activacion, tab_cambios, tab_asignaciones_atc = st.tabs([
            "⚙️ Activación",
            "👥 Cambios Activo / Inactivo",
            "📞 Asignaciones",
        ])

        # ------------------------------------------
        # TAB 1: ACTIVACIÓN (FILA ÚNICA DEL TURNERO)
        # ------------------------------------------
        with tab_activacion:
            turnos_admin_vista = obtener_lista_turnos()
            data_ivr_adm = st.session_state.data_turnos_cache
            activaciones_hoy = horas_activacion_hoy(data_ivr_adm)
            hoy_adm = obtener_fecha_hora_colombia().strftime("%Y-%m-%d")
            datos_atc_adm = datos_atc_o_none()
            if datos_atc_adm is None:
                st.warning("⚠️ No se pudo leer el turnero ATC: el orden se muestra sin las asignaciones de hoy.")
            orden_adm = orden_turnero(turnos_admin_vista, data_ivr_adm.get("cambios_estado", []),
                                      datos_atc_adm or {}, hoy_adm)
            posicion = {o["real"]: i for i, o in enumerate(orden_adm, start=1)}
            asig_hoy, ultima_asig = {}, {}
            for h in (datos_atc_adm or {}).get("historial", []):
                f, n = str(h.get("fecha_hora", "")), h.get("agente_ventas_real")
                if n and f.startswith(hoy_adm) and h.get("tipo") in ("Transferido (turno)", "Siguiente en Ruleta"):
                    asig_hoy[n] = asig_hoy.get(n, 0) + 1
                    ultima_asig[n] = max(ultima_asig.get(n, ""), f)

            st.subheader("📋 Fila actual del turnero")
            st.caption(
                f"**Mismo orden que el turnero ATC.** Rotación {' → '.join(COORDINADORES)}; dentro de cada coordinador "
                "va quien tenga **menos asignaciones hoy**, luego a quien hace más tiempo no le toca y luego **quien se "
                "activó antes**. **Llegada hoy** = primera activación del día; **Activo desde** = última activación."
            )
            filas_fila = []
            for t in sorted(turnos_admin_vista, key=lambda x: (posicion.get(x["real"], 999), x["alias"].lower())):
                a = activaciones_hoy.get(t["real"], {})
                activo = t.get("activo", True)
                pos = posicion.get(t["real"])
                filas_fila.append({
                    "Turno": "🎯 Disponible" if pos == 1 else (pos or ""),
                    "Estado": "🟢 Activo" if activo else "🔴 Inactivo",
                    "Coordinador": COORDINADOR_POR_AGENTE.get(t["real"], ""),
                    "Alias": t["alias"],
                    "Nombre Real": t["real"],
                    "🕒 Llegada hoy": a.get("llegada", "")[11:] or "—",
                    "Activo desde": (a.get("activo_desde", "")[11:] or "—") if activo else "—",
                    "📞 Asignaciones hoy": asig_hoy.get(t["real"], 0),
                    "Última asignación": ultima_asig.get(t["real"], "")[11:16] or "—",
                })
            st.dataframe(pd.DataFrame(filas_fila).astype(str), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("🚪 Registrar Llegada")
            st.caption(
                f"A las 00:00 (hora Colombia) todos quedan inactivos y a las {HORA_ACTIVACION:02d}:00 se activan todos "
                "automáticamente. Usa esto para activar a alguien que estaba inactivo: "
                "a igualdad de asignaciones, **va primero quien se activó antes**."
            )
            inactivos_admin = [t for t in turnos_admin_vista if not t.get("activo", True)]
            if not inactivos_admin:
                st.success("✅ Todos los asesores están activos.")
            else:
                for coord in COORDINADORES:
                    del_coord = sorted([t for t in inactivos_admin if COORDINADOR_POR_AGENTE.get(t["real"]) == coord],
                                       key=lambda x: x["alias"].lower())
                    if not del_coord:
                        continue
                    st.markdown(f"**{coord}**")
                    cols_llegada = st.columns(3)
                    for i, t in enumerate(del_coord):
                        with cols_llegada[i % 3]:
                            if st.button(f"✅ {t['alias']}", key=f"llegada_{t['real']}", use_container_width=True, help=t["real"]):
                                exito, msj = registrar_llegada(t["real"], admin_nombre)
                                if exito:
                                    st.toast(f"{t['alias']} activado/a")
                                    st.rerun()
                                elif msj.startswith("ℹ️"):
                                    st.info(f"{t['alias']} ya estaba activo/a (otro admin lo activó). Se actualizó la vista.")
                                else:
                                    st.error(msj)

            st.markdown("---")
            st.subheader("👥 Marcar Activo / Inactivo")
            st.caption(
                "Inactivo = no recibe asignaciones. Al **reactivarlo**, su \"activo desde\" es la nueva hora: queda "
                "detrás de quienes tengan sus mismas asignaciones y se activaron antes."
            )
            with st.expander("Ver y gestionar estados", expanded=True):
                # Solo se envían los interruptores que ESTE admin movió (sincronizados con el estado real),
                # para que un guardado nunca revierta lo que otro admin hizo mientras tanto.
                estados_seleccionados = {}
                for coord in COORDINADORES:
                    st.markdown(f"**{coord}**")
                    for t in sorted([x for x in turnos_admin_vista if COORDINADOR_POR_AGENTE.get(x["real"]) == coord],
                                    key=lambda x: x["alias"].lower()):
                        activo_t = bool(t.get("activo", True))
                        k_toggle, k_base = f"toggle_agente_{t['real']}", f"base_agente_{t['real']}"
                        if st.session_state.get(k_base) != activo_t:
                            st.session_state[k_base] = activo_t
                            st.session_state[k_toggle] = activo_t
                        col_name, col_status = st.columns([3, 1])
                        with col_name:
                            st.write(f"**{t['alias']}** ({t['real']})")
                        with col_status:
                            nuevo = st.toggle("Activo" if activo_t else "Inactivo", key=k_toggle)
                        if nuevo != activo_t:
                            estados_seleccionados[t["real"]] = nuevo
                if estados_seleccionados:
                    st.caption("Cambios pendientes por guardar: " + ", ".join(
                        f"{t['alias']}→{'Activo' if estados_seleccionados[t['real']] else 'Inactivo'}"
                        for t in turnos_admin_vista if t["real"] in estados_seleccionados))
                motivo_estado = st.text_input(
                    "Motivo del cambio (obligatorio):",
                    placeholder="Ej: Almuerzo / Capacitación / Terminó jornada / Regresó de pausa",
                    key="motivo_estado",
                )
                if st.button("💾 Guardar Cambios de Estado", type="primary", use_container_width=True):
                    exito, msj = guardar_cambios_estado_admin(estados_seleccionados, motivo_estado, admin_nombre)
                    if exito:
                        st.success(msj)
                        st.rerun()
                    elif msj.startswith("ℹ️"):
                        st.info(msj)
                    else:
                        st.error(msj)

        # ------------------------------------------
        # TAB 2: CAMBIOS DE ESTADO
        # ------------------------------------------
        with tab_cambios:
            st.subheader("👥 Historial de Cambios Activo / Inactivo")
            df_cambios_estado = obtener_cambios_estado_df()
            if df_cambios_estado.empty:
                st.info("Aún no se han registrado cambios de estado.")
            else:
                st.dataframe(df_cambios_estado.astype(str), use_container_width=True, hide_index=True)
                st.download_button(
                    label="📥 Descargar Cambios de Estado (CSV)",
                    data=df_cambios_estado.to_csv(index=False).encode("utf-8"),
                    file_name=f"cambios_estado_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # ------------------------------------------
        # TAB 3: ASIGNACIONES QUE HICIERON LOS ATC
        # ------------------------------------------
        with tab_asignaciones_atc:
            st.subheader("📞 Historial de asignaciones (turnero ATC)")
            fecha_adm = st.date_input("Día:", value=obtener_fecha_hora_colombia().date(),
                                      max_value=obtener_fecha_hora_colombia().date(), key="fecha_asig_adm")
            filas_adm = asignaciones_atc(fecha=fecha_adm.strftime("%Y-%m-%d"))
            if filas_adm is None:
                st.warning("⚠️ No se pudieron leer las asignaciones de ATC (revisa el token de GitHub y "
                           "`repo_atc` en los secrets). Se reintenta al recargar.")
            elif not filas_adm:
                st.info("No hay asignaciones ese día.")
            else:
                df_asig = pd.DataFrame([{
                    "Hora": str(h.get("fecha_hora", ""))[11:16],
                    "Asesor": h.get("agente_ventas_alias", ""),
                    "Nombre Real": h.get("agente_ventas_real", ""),
                    "Coordinador": h.get("coordinador", ""),
                    "Teléfono": h.get("telefono", ""),
                    "Tipo": TIPOS_ASIGNACION.get(h.get("tipo"), h.get("tipo")),
                    "ATC": h.get("agente_atc", ""),
                } for h in filas_adm]).astype(str)
                st.metric("Clientes asignados", len(df_asig))
                st.dataframe(df_asig, use_container_width=True, hide_index=True)
                st.download_button(
                    label="📥 Descargar asignaciones (CSV)",
                    data=df_asig.to_csv(index=False).encode("utf-8"),
                    file_name=f"asignaciones_atc_{fecha_adm.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )


# ------------------------------------------
# VISTA: MIS ASIGNACIONES ATC (ASESOR CON SU PIN)
# ------------------------------------------
@st.fragment(run_every=REFRESCO_ASIGNACIONES)
def panel_mis_asignaciones(nombre_real: str, fecha: str):
    """Se actualiza solo: en cuanto un ATC le asigna un cliente, aparece aquí con un aviso."""
    filas = asignaciones_atc(nombre_real, fecha)
    if filas is None:
        st.warning("⚠️ No se pudieron leer las asignaciones en este momento. Se reintenta en unos segundos.")
        return

    turnos_ivr = (leer_rapido(st.secrets["github"]["repo"], FILE_TURNOS) or {}).get("turnos", [])
    activo = next((bool(t.get("activo", True)) for t in turnos_ivr if t.get("real") == nombre_real), False)
    st.caption("🟢 Estás **activo**: recibes turnos." if activo else "🔴 Estás **inactivo**: no recibes turnos.")

    claves = [f"{h.get('fecha_hora')}|{h.get('telefono')}|{h.get('id')}" for h in filas]
    vistas = st.session_state.get("asignaciones_vistas")
    if vistas is None:
        st.session_state["asignaciones_vistas"] = set(claves)  # primera carga: sin avisos
    else:
        for h, k in zip(filas, claves):
            if k not in vistas:
                st.toast(f"📞 Nuevo cliente asignado: {h.get('telefono', '')}", icon="🆕")
                vistas.add(k)

    st.metric("Clientes asignados", len(filas))
    if not filas:
        st.info("Aún no tienes clientes asignados ese día.")
    else:
        ultimo = filas[0]
        st.success(f"🆕 **Último asignado:** `{ultimo.get('telefono', '')}` a las "
                   f"{str(ultimo.get('fecha_hora', ''))[11:16]} · ATC {ultimo.get('agente_atc', '')}")
        st.dataframe(pd.DataFrame([{
            "Hora": str(h.get("fecha_hora", ""))[11:16],
            "Teléfono": h.get("telefono", ""),
            "Tipo": TIPOS_ASIGNACION.get(h.get("tipo"), h.get("tipo")),
            "ATC": h.get("agente_atc", ""),
        } for h in filas]).astype(str), use_container_width=True, hide_index=True)
    st.caption(f"Actualizado: {obtener_hora_colombia_str()[11:]} · se refresca cada {REFRESCO_ASIGNACIONES} s")


if opcion_vista == "📋 Mis asignaciones ATC":
    st.title("📋 Mis asignaciones (ATC)")
    asesor = st.session_state.get("asesor_logueado")

    if not asesor:
        st.caption("Ingresa tu PIN para ver los clientes que te asignan desde ATC.")
        intentos_pin = st.session_state.get("intentos_pin_asesor", 0)
        if intentos_pin >= MAX_INTENTOS_PIN_ASESOR:
            st.error("🔒 Demasiados PIN incorrectos. Recarga la página para intentarlo de nuevo.")
        else:
            with st.form("form_pin_asesor", clear_on_submit=True):
                pin_asesor = st.text_input("🔑 Tu PIN de 4 dígitos:", type="password", max_chars=4)
                ver = st.form_submit_button("Ver mis asignaciones", type="primary", use_container_width=True)
            if ver:
                nombre = asesor_por_pin(pin_asesor)
                if nombre:
                    st.session_state.update(asesor_logueado=nombre, intentos_pin_asesor=0, asignaciones_vistas=None)
                    st.rerun()
                st.session_state["intentos_pin_asesor"] = intentos_pin + 1
                restantes = MAX_INTENTOS_PIN_ASESOR - intentos_pin - 1
                if restantes <= 0:
                    st.rerun()
                st.error(f"❌ PIN incorrecto. Intentos restantes: {restantes}")
    else:
        alias = next((u["alias"] for u in USUARIOS_INICIALES if u["real"] == asesor), asesor)
        c_nombre, c_salir = st.columns([4, 1])
        with c_nombre:
            st.subheader(f"👤 {alias}")
            st.caption(asesor)
        with c_salir:
            if st.button("🚪 Salir", use_container_width=True):
                st.session_state.pop("asesor_logueado", None)
                st.session_state.pop("asignaciones_vistas", None)
                st.rerun()
        fecha_sel = st.date_input("Día:", value=obtener_fecha_hora_colombia().date(),
                                  max_value=obtener_fecha_hora_colombia().date(), key="fecha_mis_asig")
        panel_mis_asignaciones(asesor, fecha_sel.strftime("%Y-%m-%d"))
