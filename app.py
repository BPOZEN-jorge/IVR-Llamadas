import json
import random
import time as time_lib
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from github import Github, GithubException

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Sistema de Turnos y Llamadas BPO",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# SEPARACIÓN DE ARCHIVOS PARA PREVENIR CONFLICTOS CONCURRENTES
FILE_TURNOS = "turnos_orden.json"      # Posiciones, historial de llamadas y saltos manuales del admin
FILE_LOG_SALTOS = "saltos_log.json"    # Mapeo temporal independiente de TODOS los saltos (agente y admin)

TIPO_SALTO_LLAMADA = "LLAMADA"          # Salto por llamada atendida por el agente (con PIN)
TIPO_SALTO_ADMIN = "SALTO_ADMIN"        # Salto manual decidido por el admin (con motivo)

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
    {"posicion": 10, "real": "Dayana Botero Rojas", "alias": "Isabel Botero"},
    {"posicion": 11, "real": "Evelin Acevedo Cortés", "alias": "Gabriela"},
    {"posicion": 12, "real": "Gustavo Adolfo Barrientos Serna", "alias": "Gustavo"},
    {"posicion": 13, "real": "Iris Sabiana Cano Cano", "alias": "Maria Cano"},
    {"posicion": 14, "real": "Janis Henao Vasco", "alias": "María José"},
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
    {"posicion": 33, "real": "Tatiana Magreth Acevedo Marín", "alias": "Tatiana"},
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
def obtener_repositorio_github():
    token = st.secrets.get("github", {}).get("token")
    repo_name = st.secrets.get("github", {}).get("repo")
    if not token or not repo_name:
        st.error("⚠️ Configuración incompleta de GitHub en los secretos (`st.secrets`).")
        st.stop()
    g = Github(token)
    return g.get_repo(repo_name)


def leer_json_github(file_path: str, default_payload: dict) -> dict:
    """Lee un archivo JSON individual directamente desde GitHub."""
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    try:
        content = repo.get_contents(file_path, ref=branch)
        return json.loads(content.decoded_content.decode("utf-8"))
    except GithubException as e:
        if e.status == 404:
            escribir_json_github(file_path, default_payload, f"Inicializar {file_path}")
            return default_payload
        st.error(f"Error leyendo {file_path}: {e}")
        st.stop()


def escribir_json_github(file_path: str, payload: dict, mensaje_commit: str, retries: int = 3):
    """Guarda un JSON en GitHub reintentando automáticamente en caso de colisión de hash (commit concurrente)."""
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    json_str = json.dumps(payload, indent=4, ensure_ascii=False)

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
def guardar_evento_log_salto(datos_salto: dict):
    """Guarda un registro independiente en saltos_log.json para mapeo temporal."""
    log_actual = leer_json_github(FILE_LOG_SALTOS, {"saltos": []})
    if "saltos" not in log_actual:
        log_actual["saltos"] = []
    datos_salto.setdefault("id_evento", len(log_actual["saltos"]) + 1)
    log_actual["saltos"].insert(0, datos_salto)

    if datos_salto.get("tipo") == TIPO_SALTO_ADMIN:
        msg = f"Log Salto ADMIN: {datos_salto.get('alias')} - {datos_salto.get('motivo', '')[:60]}"
    else:
        msg = f"Log Salto: {datos_salto.get('alias')} (ID: {datos_salto.get('call_id')})"
    escribir_json_github(FILE_LOG_SALTOS, log_actual, msg)


def obtener_log_saltos_df() -> pd.DataFrame:
    """Carga y procesa el log de saltos para descargarlo o mostrarlo."""
    log_actual = leer_json_github(FILE_LOG_SALTOS, {"saltos": []})
    saltos = log_actual.get("saltos", [])
    if not saltos:
        return pd.DataFrame()

    registros = []
    for s in saltos:
        registros.append({
            "ID Evento": s.get("id_evento"),
            "Tipo": s.get("tipo", TIPO_SALTO_LLAMADA),
            "Fecha/Hora (Colombia)": s.get("fecha_hora"),
            "ID Llamada": s.get("call_id", ""),
            "Teléfono": s.get("telefono", ""),
            "Agente (Alias)": s.get("alias"),
            "Agente (Real)": s.get("nombre_real"),
            "Posición al Saltar": s.get("posicion_al_saltar"),
            "Motivo (Admin)": s.get("motivo", ""),
            "Registrado por": s.get("registrado_por", ""),
            "Orden previo snapshot": json.dumps(s.get("orden_previo_snapshot", []), ensure_ascii=False),
        })
    return pd.DataFrame(registros)


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
    """Carga orden de turnos, historial de llamadas y saltos manuales del admin desde GitHub."""
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    turnos_lista = sorted(data_turnos.get("turnos", USUARIOS_INICIALES), key=lambda x: x["posicion"])
    historial = data_turnos.get("historial", [])
    saltos_admin = data_turnos.get("saltos_admin", [])
    st.session_state.data_turnos_cache = data_turnos
    return turnos_lista, historial, saltos_admin


def obtener_lista_turnos() -> list:
    turnos, _, _ = obtener_estructura_completa_fresca()
    return turnos


def _limpiar_turnos(turnos: list) -> list:
    """Deja solo los campos que se persisten (descarta claves antiguas como activo/manual)."""
    return [{"posicion": t["posicion"], "real": t["real"], "alias": t["alias"]} for t in turnos]


def _snapshot_fila(turnos: list) -> list:
    return [{"posicion": t["posicion"], "alias": t["alias"], "real": t["real"]} for t in turnos]


def _mover_al_final(turnos: list, posicion: int) -> list:
    """Mueve al agente en `posicion` al final de la fila y renumera."""
    turnos_limpios = _limpiar_turnos(turnos)
    agente = next(t for t in turnos_limpios if t["posicion"] == posicion)
    nuevos = [t for t in turnos_limpios if t["posicion"] != posicion] + [agente]
    for idx, t in enumerate(nuevos, start=1):
        t["posicion"] = idx
    return nuevos


# ==========================================
# SALTO POR LLAMADA ATENDIDA (AGENTE CON PIN)
# ==========================================
def registrar_salto_turno(call_id: str, telefono: str, pin_ingresado: str) -> tuple[bool, str]:
    call_id_clean = call_id.strip()
    telefono_clean = telefono.strip()
    pin_clean = pin_ingresado.strip()

    if not call_id_clean:
        return False, "⚠️ Debes ingresar un ID de llamada válido."
    if not telefono_clean:
        return False, "⚠️ Debes ingresar un número de teléfono válido."
    if not pin_clean:
        return False, "⚠️ Debes ingresar tu PIN personal de 4 dígitos."

    now_col = obtener_hora_colombia_str()
    turnos, historial, _ = obtener_estructura_completa_fresca()

    if any(h.get("call_id") == call_id_clean for h in historial):
        return False, f"❌ El ID de llamada '{call_id_clean}' ya fue registrado previamente."
    if any(h.get("telefono") == telefono_clean for h in historial):
        return False, f"❌ El número de teléfono '{telefono_clean}' ya fue atendido previamente."

    if not turnos:
        return False, "❌ No hay agentes en la fila de turnos."

    # El turno lo tiene siempre la PRIMERA persona de la fila
    agente_atendiendo = turnos[0]
    pos_atendiendo = agente_atendiendo["posicion"]
    nombre_real = agente_atendiendo["real"]
    alias = agente_atendiendo["alias"]

    # VALIDACIÓN DEL PIN SECRETO
    pins_secretos = st.secrets.get("pins", {})
    pin_correcto = str(pins_secretos.get(nombre_real, "")).strip()
    if not pin_correcto:
        return False, f"⚠️ No se ha configurado un PIN para **{nombre_real}** en los secretos del sistema."
    if pin_clean != pin_correcto:
        return False, f"🔒 **PIN incorrecto.** No puedes ceder o avanzar el turno de **{alias}**."

    snapshot_fila_previa = _snapshot_fila(turnos)

    nuevo_registro = {
        "id": len(historial) + 1,
        "call_id": call_id_clean,
        "telefono": telefono_clean,
        "nombre_real": nombre_real,
        "alias": alias,
        "fecha_hora": now_col,
    }
    historial.insert(0, nuevo_registro)

    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    data_turnos["historial"] = historial
    data_turnos["turnos"] = _mover_al_final(turnos, pos_atendiendo)

    if escribir_json_github(FILE_TURNOS, data_turnos, f"Avanzar turno atendido por {alias} (ID: {call_id_clean})"):
        guardar_evento_log_salto({
            "tipo": TIPO_SALTO_LLAMADA,
            "fecha_hora": now_col,
            "call_id": call_id_clean,
            "telefono": telefono_clean,
            "nombre_real": nombre_real,
            "alias": alias,
            "posicion_al_saltar": pos_atendiendo,
            "orden_previo_snapshot": snapshot_fila_previa,
        })
        return True, (
            f"✅ ¡Turno completado por **{alias}** ({nombre_real})! "
            f"ID: `{call_id_clean}` y Teléfono: `{telefono_clean}` registrados con éxito."
        )
    return False, "❌ Hubo un fallo temporal de comunicación con GitHub. Intenta nuevamente."


# ==========================================
# SALTO MANUAL DEL ADMIN (POR DISPONIBILIDAD)
# ==========================================
def saltar_primero_admin(nombre_real_esperado: str, motivo: str, registrado_por: str) -> tuple[bool, str]:
    """
    El admin salta a la primera persona de la fila (la manda al final) indicando el motivo.
    Se valida que la persona en primer lugar siga siendo la misma que el admin vio en pantalla,
    para evitar saltar a alguien distinto si otro usuario avanzó la fila al mismo tiempo.
    """
    motivo_clean = motivo.strip()
    registrado_por_clean = registrado_por.strip() or "Admin"

    if len(motivo_clean) < 5:
        return False, "⚠️ Debes escribir el motivo del salto (mínimo 5 caracteres)."

    turnos, historial, saltos_admin = obtener_estructura_completa_fresca()
    if not turnos:
        return False, "❌ No hay agentes en la fila de turnos."

    primero = turnos[0]
    if primero["real"] != nombre_real_esperado:
        return False, (
            f"⚠️ La fila cambió mientras escribías: ahora el primero es **{primero['alias']}** "
            f"({primero['real']}). Revisa y vuelve a intentarlo."
        )

    now_col = obtener_hora_colombia_str()
    snapshot_fila_previa = _snapshot_fila(turnos)
    nuevos_turnos = _mover_al_final(turnos, primero["posicion"])
    siguiente = nuevos_turnos[0] if nuevos_turnos else None

    registro_admin = {
        "id": len(saltos_admin) + 1,
        "fecha_hora": now_col,
        "nombre_real": primero["real"],
        "alias": primero["alias"],
        "posicion_al_saltar": primero["posicion"],
        "motivo": motivo_clean,
        "registrado_por": registrado_por_clean,
        "nuevo_primero": siguiente["alias"] if siguiente else "",
    }
    saltos_admin.insert(0, registro_admin)

    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    data_turnos["turnos"] = nuevos_turnos
    data_turnos["historial"] = historial
    data_turnos["saltos_admin"] = saltos_admin

    commit_msg = f"Admin: salto manual de {primero['alias']} - Motivo: {motivo_clean[:80]}"
    if escribir_json_github(FILE_TURNOS, data_turnos, commit_msg):
        guardar_evento_log_salto({
            "tipo": TIPO_SALTO_ADMIN,
            "fecha_hora": now_col,
            "call_id": "",
            "telefono": "",
            "nombre_real": primero["real"],
            "alias": primero["alias"],
            "posicion_al_saltar": primero["posicion"],
            "motivo": motivo_clean,
            "registrado_por": registrado_por_clean,
            "orden_previo_snapshot": snapshot_fila_previa,
        })
        msg_sig = f" Ahora el turno es de **{siguiente['alias']}**." if siguiente else ""
        return True, f"✅ Se saltó a **{primero['alias']}** y quedó al final de la fila.{msg_sig}"
    return False, "❌ Hubo un fallo temporal de comunicación con GitHub. Intenta nuevamente."


def obtener_saltos_admin_df() -> pd.DataFrame:
    _, _, saltos_admin = obtener_estructura_completa_fresca()
    if not saltos_admin:
        return pd.DataFrame()
    df = pd.DataFrame(saltos_admin)
    return df.rename(columns={
        "id": "ID",
        "fecha_hora": "Fecha / Hora (Colombia)",
        "alias": "Alias Saltado",
        "nombre_real": "Nombre Real",
        "posicion_al_saltar": "Posición",
        "motivo": "Motivo",
        "registrado_por": "Registrado por",
        "nuevo_primero": "Quedó de primero",
    })


# ==========================================
# HISTORIAL Y REORDENAMIENTO
# ==========================================
def obtener_historial_saltos() -> pd.DataFrame:
    _, historial, _ = obtener_estructura_completa_fresca()
    if not historial:
        return pd.DataFrame()
    df = pd.DataFrame(historial)
    return df.rename(columns={
        "id": "ID Reg",
        "call_id": "ID Llamada",
        "telefono": "Teléfono",
        "alias": "Alias",
        "nombre_real": "Nombre Real",
        "fecha_hora": "Fecha / Hora (Colombia)",
    })


def vaciar_historial_llamadas():
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    data_turnos["historial"] = []
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Vaciar historial de llamadas")


def reiniciar_turnos_originales():
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    data_turnos["turnos"] = [dict(u) for u in USUARIOS_INICIALES]
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Restablecer turnos al orden inicial")


def reorganizar_turnos_al_azar():
    data_turnos = leer_json_github(FILE_TURNOS, _default_turnos())
    turnos = _limpiar_turnos(data_turnos.get("turnos", USUARIOS_INICIALES))
    random.shuffle(turnos)
    for idx, t in enumerate(turnos, start=1):
        t["posicion"] = idx
    data_turnos["turnos"] = turnos
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Reorganizar turnos al azar")


# ==========================================
# FUNCIONES AUXILIARES DE ZONAS HORARIAS ROBUSTAS
# ==========================================
def convertir_a_colombia_robust(columna_fechas: pd.Series, es_aircall: bool = True) -> pd.Series:
    """
    Convierte una serie de fechas a 'America/Bogota'.
    Si la serie proviene de Aircall (es_aircall=True) y no trae zona horaria explícita,
    asume 'Europe/Madrid' (España UTC+2) y resta las 7 horas a Colombia.
    Si proviene del sistema de saltos (es_aircall=False), asume 'America/Bogota'.
    """
    def parse_fecha(val):
        if pd.isna(val) or str(val).strip() in ["", "nan", "None", "N/A"]:
            return pd.NaT
        try:
            dt = pd.to_datetime(val)
            if dt.tzinfo is None:
                dt = dt.tz_localize("Europe/Madrid" if es_aircall else "America/Bogota")
            return dt.tz_convert("America/Bogota")
        except Exception:
            return pd.NaT

    return columna_fechas.apply(parse_fecha)


# ==========================================
# LÓGICA DE AUDITORÍA DE DEVOLUCIONES IVR
# ==========================================
def analizar_devoluciones_ivr_y_saltos(file1, file2, rama_filtro="", widget_filtro=""):
    try:
        df1 = pd.read_csv(file1)
        df2 = pd.read_csv(file2)

        # Cargar planilla de saltos/historial guardada internamente en GitHub
        df3 = obtener_historial_saltos()
        raw_log_saltos = leer_json_github(FILE_LOG_SALTOS, {"saltos": []}).get("saltos", [])

        # 1. Filtrado Exclusivo de Llamadas Perdidas en IVR
        mask_inbound_missed = (df1["direction"] == "inbound") & (df1["answered"] == "No")
        mask_ivr = (
            df1["line"].astype(str).str.contains("IVR", case=False, na=False)
            | df1["ivr branch"].notna()
            | df1["ivr widget"].notna()
            | (df1["time in ivr"].notna() & (df1["time in ivr"] != "00:00:00"))
        )
        if rama_filtro.strip():
            mask_ivr = mask_ivr & (df1["ivr branch"].astype(str).str.contains(rama_filtro.strip(), case=False, na=False))
        if widget_filtro.strip():
            mask_ivr = mask_ivr & (df1["ivr widget"].astype(str).str.contains(widget_filtro.strip(), case=False, na=False))

        df_perdidas_ivr = df1[mask_inbound_missed & mask_ivr].copy()
        if df_perdidas_ivr.empty:
            return pd.DataFrame(), "No se encontraron llamadas perdidas que cumplan con los criterios de IVR especificados."

        df_perdidas_ivr["num_limpio"] = df_perdidas_ivr["customer number"].astype(str).str.replace(r"\D", "", regex=True)

        # 2. Llamadas salientes (Outbound Aircall)
        df_salientes = df2[df2["direction"] == "outbound"].copy()
        df_salientes["num_limpio"] = df_salientes["customer number"].astype(str).str.replace(r"\D", "", regex=True)

        # 3. Conversión Homogénea de Fechas (España -> Colombia)
        col_fecha1 = "datetime (tz offset incl.)" if "datetime (tz offset incl.)" in df1.columns else "call start time"
        col_fecha2 = "datetime (tz offset incl.)" if "datetime (tz offset incl.)" in df2.columns else "call start time"
        df_perdidas_ivr["dt_perdida"] = convertir_a_colombia_robust(df_perdidas_ivr[col_fecha1], es_aircall=True)
        df_salientes["dt_saliente"] = convertir_a_colombia_robust(df_salientes[col_fecha2], es_aircall=True)

        col_nom3 = "Nombre Real"
        if not df3.empty:
            col_tel3 = "Teléfono" if "Teléfono" in df3.columns else df3.columns[2]
            col_nom3 = "Nombre Real" if "Nombre Real" in df3.columns else df3.columns[3]
            col_fecha3 = "Fecha / Hora (Colombia)" if "Fecha / Hora (Colombia)" in df3.columns else df3.columns[5]
            df3["num_limpio"] = df3[col_tel3].astype(str).str.replace(r"\D", "", regex=True)
            df3["dt_turno"] = convertir_a_colombia_robust(df3[col_fecha3], es_aircall=False)
        else:
            df3 = pd.DataFrame(columns=["num_limpio", "dt_turno", "Nombre Real", "Alias"])

        # Pre-procesar fechas del log una sola vez
        log_con_fechas = []
        for s in raw_log_saltos:
            dt_s = convertir_a_colombia_robust(pd.Series([s.get("fecha_hora")]), es_aircall=False).iloc[0]
            if pd.notna(dt_s):
                log_con_fechas.append((dt_s, s))

        numeros_devueltos = set(df_perdidas_ivr["num_limpio"]).intersection(set(df_salientes["num_limpio"]))
        if not numeros_devueltos:
            return pd.DataFrame(), "No se encontraron devoluciones a las llamadas perdidas de IVR."

        filas_resumen = []
        for num in numeros_devueltos:
            sub_perdidas = df_perdidas_ivr[df_perdidas_ivr["num_limpio"] == num].sort_values("dt_perdida")
            sub_salientes = df_salientes[df_salientes["num_limpio"] == num].sort_values("dt_saliente")
            sub_turnos = df3[df3["num_limpio"] == num].sort_values("dt_turno") if not df3.empty else pd.DataFrame()

            num_cliente = sub_perdidas["customer number"].iloc[0]
            fechas_perdidas_str = " | ".join(sub_perdidas["dt_perdida"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist())
            tot_perdidas = len(sub_perdidas)
            linea_ivr = " | ".join(sub_perdidas["line"].astype(str).unique().tolist())
            motivos_perdida = " | ".join(sub_perdidas["missed_call_reason"].astype(str).unique().tolist())
            rama_ivr = " | ".join(sub_perdidas["ivr branch"].dropna().astype(str).unique().tolist()) or "N/A"
            widget_ivr = " | ".join(sub_perdidas["ivr widget"].dropna().astype(str).unique().tolist()) or "N/A"

            tot_salientes = len(sub_salientes)
            horarios_salientes_str = " | ".join(sub_salientes["dt_saliente"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist())
            asesores_salientes_str = " | ".join(sub_salientes["user"].astype(str).unique().tolist())

            tot_turnos = len(sub_turnos) if not sub_turnos.empty else 0
            registrado_flag = "Sí" if tot_turnos > 0 else "NO REGISTRADO"
            horarios_turnos_str = (
                " | ".join(sub_turnos["dt_turno"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()) if tot_turnos > 0 else "N/A"
            )
            asesores_turnos_str = " | ".join(sub_turnos[col_nom3].astype(str).unique().tolist()) if tot_turnos > 0 else "N/A"

            # MAPEO TEMPORAL DE TURNO: quién estaba de PRIMERO en la fila al momento del evento
            primera_fecha_saliente = sub_salientes["dt_saliente"].iloc[0]
            agente_que_tocaba = "Desconocido (Sin snapshot)"
            coincidio_turno = "N/A"

            saltos_previos = [
                (dt_s, s) for dt_s, s in log_con_fechas
                if dt_s <= primera_fecha_saliente + pd.Timedelta(minutes=5)
            ]
            if saltos_previos:
                ultimo_salto = max(saltos_previos, key=lambda x: x[0])[1]
                snapshot = ultimo_salto.get("orden_previo_snapshot", [])
                # Compatibilidad con snapshots antiguos que traían "activo"
                candidatos = sorted(
                    [ag for ag in snapshot if ag.get("activo", True)],
                    key=lambda x: x.get("posicion", 999),
                )
                if candidatos:
                    agente_que_tocaba = candidatos[0].get("alias", "Desconocido")

            if agente_que_tocaba != "Desconocido (Sin snapshot)" and asesores_salientes_str != "N/A":
                if (agente_que_tocaba.lower() in asesores_salientes_str.lower()
                        or asesores_salientes_str.lower() in agente_que_tocaba.lower()):
                    coincidio_turno = "✅ COINCIDE (Atendió quien le tocaba)"
                else:
                    coincidio_turno = f"⚠️ NO COINCIDE (Tocaba: {agente_que_tocaba} | Devolvió: {asesores_salientes_str})"

            # Diagnóstico de Auditoría
            if tot_turnos > 0 and tot_salientes == 1:
                diagnostico = "✅ Devuelta IVR y Registrada en Saltos (1 sola vez)"
            elif tot_turnos > 0 and tot_salientes > 1:
                diagnostico = "🔄 Devuelta IVR y Registrada pero con MÚLTIPLES llamadas en Aircall"
            elif tot_turnos == 0 and tot_salientes > 1:
                diagnostico = "🔴 CRÍTICO: Múltiples Devoluciones a IVR en Aircall y NO Registrada en Saltos"
            else:
                diagnostico = "⚠️ INCONSISTENCIA: Devuelta en Aircall pero NO Registrada en Saltos"

            filas_resumen.append({
                "Número Cliente": num_cliente,
                "Línea IVR": linea_ivr,
                "Rama IVR": rama_ivr,
                "Widget IVR": widget_ivr,
                "Motivo Pérdida IVR": motivos_perdida,
                "Perdidas en IVR": tot_perdidas,
                "Horario Llamada Perdida IVR (Colombia)": fechas_perdidas_str,
                "Cant. Devoluciones (Aircall)": tot_salientes,
                "Horarios Devolución (Aircall / Colombia)": horarios_salientes_str,
                "Asesor que Devolvió (Aircall)": asesores_salientes_str,
                "Agente que le Tocaba (Snapshot)": agente_que_tocaba,
                "Validación de Turno": coincidio_turno,
                "Registrado en Saltos": registrado_flag,
                "Cant. Registros Saltos": tot_turnos,
                "Horarios Registro Saltos (Colombia)": horarios_turnos_str,
                "Asesores Registro Saltos": asesores_turnos_str,
                "Estado Auditoría": diagnostico,
            })

        df_resultado = pd.DataFrame(filas_resumen).sort_values(
            by=["Cant. Devoluciones (Aircall)", "Registrado en Saltos"],
            ascending=[False, True],
        )
        return df_resultado, None

    except Exception as e:
        return None, str(e)


# ==========================================
# INTERFAZ DE NAVEGACIÓN Y VISTAS
# ==========================================
st.sidebar.title("📌 Portal de Turnos")
opcion_vista = st.sidebar.radio("Navegación:", ["🎡 Fila de Turnos (Ruleta)", "🛡️ Vista Administrador"])

# ------------------------------------------
# VISTA 1: FILA DE TURNOS (RULETA)
# ------------------------------------------
if opcion_vista == "🎡 Fila de Turnos (Ruleta)":
    st.title("🔄 Control de Turnos y Llamadas")
    st.caption(f"Hora Colombia: `{obtener_hora_colombia_str()}`")
    st.caption("Ingresa el ID de la llamada, el Teléfono y tu PIN secreto de 4 dígitos para completar tu turno.")

    turnos_actuales = obtener_lista_turnos()
    actual = turnos_actuales[0] if turnos_actuales else None

    if actual:
        st.markdown("---")
        col_turn_1, col_turn_2 = st.columns([2, 3])

        with col_turn_1:
            st.metric(label="🎯 TURNO ACTUAL (ATENDIENDO)", value=actual["alias"])
            st.write(f"👤 **Nombre Real:** {actual['real']}")
            proximos = turnos_actuales[1:4]
            if proximos:
                st.caption("⏭️ Siguientes: " + " → ".join(p["alias"] for p in proximos))

        with col_turn_2:
            st.subheader("📞 Completar Turno Actual")
            with st.form("form_avanzar_turno", clear_on_submit=True):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    call_id_input = st.text_input("ID de la Llamada:", placeholder="Ej: CALL-9876543")
                with col_f2:
                    telefono_input = st.text_input("Teléfono del Cliente:", placeholder="Ej: 3001234567")
                pin_input = st.text_input("🔑 PIN Secreto (4 dígitos):", type="password", max_chars=4, placeholder="****")
                submit_salto = st.form_submit_button("Avanzar Turno ➡️", use_container_width=True, type="primary")

            if submit_salto:
                exito, mensaje = registrar_salto_turno(call_id_input, telefono_input, pin_input)
                if exito:
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error(mensaje)
    else:
        st.error("⚠️ No hay agentes en la fila de turnos.")

# ------------------------------------------
# VISTA 2: ADMINISTRADOR
# ------------------------------------------
elif opcion_vista == "🛡️ Vista Administrador":
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
        if st.sidebar.button("Cerrar Sesión Admin", use_container_width=True):
            st.session_state.admin_logged = False
            st.rerun()

        tab_gestion, tab_saltos_admin, tab_historial, tab_log_saltos, tab_auditoria_ivr = st.tabs([
            "⚙️ Gestión de la Fila",
            "⏭️ Saltos Manuales (Admin)",
            "📊 Historial de Llamadas",
            "📜 Log de Saltos y Mapeo Temporal",
            "🤖 Auditoría Devoluciones IVR",
        ])

        # ------------------------------------------
        # TAB 1: GESTIÓN DE LA FILA
        # ------------------------------------------
        with tab_gestion:
            turnos_admin_vista = obtener_lista_turnos()
            primero_admin = turnos_admin_vista[0] if turnos_admin_vista else None

            st.subheader("⏭️ Saltar Manualmente a la Primera Persona")
            st.caption(
                "Úsalo cuando la persona que tiene el turno no está disponible. "
                "Pasará al final de la fila y el motivo quedará guardado en GitHub."
            )

            if primero_admin:
                c_p1, c_p2 = st.columns([1, 2])
                with c_p1:
                    st.metric("🎯 Primero en la fila", primero_admin["alias"])
                    st.write(f"👤 {primero_admin['real']}")
                    if len(turnos_admin_vista) > 1:
                        st.caption(f"Si lo saltas, el turno pasa a **{turnos_admin_vista[1]['alias']}**.")
                with c_p2:
                    with st.form("form_salto_admin", clear_on_submit=True):
                        motivo_input = st.text_area(
                            "Motivo del salto (obligatorio):",
                            placeholder="Ej: En capacitación hasta las 11:00 / Pausa activa / Incapacidad / Fuera de horario",
                        )
                        registrado_por_input = st.text_input("Registrado por:", placeholder="Nombre del admin")
                        confirm_salto = st.checkbox(f"Confirmo saltar a {primero_admin['alias']}.")
                        btn_salto_admin = st.form_submit_button("⏭️ Saltar Turno", type="primary", use_container_width=True)

                    if btn_salto_admin:
                        if not confirm_salto:
                            st.warning("⚠️ Marca la casilla de confirmación para saltar el turno.")
                        else:
                            exito, msj = saltar_primero_admin(primero_admin["real"], motivo_input, registrado_por_input)
                            if exito:
                                st.success(msj)
                                st.rerun()
                            else:
                                st.error(msj)
            else:
                st.warning("⚠️ No hay agentes en la fila.")

            st.markdown("---")
            st.subheader("📋 Fila Actual de Posiciones")
            tabla_display = [
                {
                    "Posición": t["posicion"],
                    "Turno": "🎯 Atendiendo" if idx == 0 else "",
                    "Nombre Real": t["real"],
                    "Alias / Nombre en Sistema": t["alias"],
                }
                for idx, t in enumerate(turnos_admin_vista)
            ]
            st.dataframe(pd.DataFrame(tabla_display), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("⚙️ Opciones de Reordenamiento y Limpieza")
            col_admin_1, col_admin_2, col_admin_3 = st.columns(3)

            with col_admin_1:
                st.markdown("### 🎲 Rebobinar al Azar")
                st.caption("Mezcla la lista completa de agentes al azar.")
                confirm_random = st.checkbox("Confirmo mezclar la fila al azar.")
                if st.button("🔀 Mezclar Orden", disabled=not confirm_random, type="primary", use_container_width=True):
                    reorganizar_turnos_al_azar()
                    st.success("✅ ¡Fila mezclada con éxito!")
                    st.rerun()

            with col_admin_2:
                st.markdown("### 🔄 Restablecer Orden")
                st.caption("Restablece el orden alfabético inicial.")
                confirm_reset = st.checkbox("Confirmo reiniciar al orden inicial.")
                if st.button("Restablecer Fila", disabled=not confirm_reset, use_container_width=True):
                    reiniciar_turnos_originales()
                    st.success("✅ Fila de turnos restablecida.")
                    st.rerun()

            with col_admin_3:
                st.markdown("### 🗑️ Limpiar Historial")
                st.caption("Borra los registros de llamadas de prueba.")
                confirm_del_hist = st.checkbox("Confirmo borrar el historial.")
                if st.button("Vaciar Historial", disabled=not confirm_del_hist, use_container_width=True):
                    vaciar_historial_llamadas()
                    st.success("✅ Historial de llamadas vaciado.")
                    st.rerun()

        # ------------------------------------------
        # TAB 2: SALTOS MANUALES DEL ADMIN
        # ------------------------------------------
        with tab_saltos_admin:
            st.subheader("⏭️ Historial de Saltos Manuales del Admin")
            st.caption("Cada salto manual queda guardado en `turnos_orden.json` (clave `saltos_admin`) y en `saltos_log.json`.")
            df_saltos_admin = obtener_saltos_admin_df()
            if df_saltos_admin.empty:
                st.info("Aún no se han realizado saltos manuales.")
            else:
                st.dataframe(df_saltos_admin, use_container_width=True, hide_index=True)
                st.download_button(
                    label="📥 Descargar Saltos Manuales (CSV)",
                    data=df_saltos_admin.to_csv(index=False).encode("utf-8"),
                    file_name=f"saltos_admin_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # ------------------------------------------
        # TAB 3: HISTORIAL DE LLAMADAS
        # ------------------------------------------
        with tab_historial:
            st.subheader("📊 Historial de Registro de Llamadas")
            df_historial = obtener_historial_saltos()
            if df_historial.empty:
                st.info("Aún no se han registrado llamadas.")
            else:
                st.dataframe(df_historial, use_container_width=True, hide_index=True)
                st.download_button(
                    label="📥 Descargar Reporte Llamadas CSV",
                    data=df_historial.to_csv(index=False).encode("utf-8"),
                    file_name=f"reporte_llamadas_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # ------------------------------------------
        # TAB 4: LOG DE SALTOS Y MAPEO TEMPORAL
        # ------------------------------------------
        with tab_log_saltos:
            st.subheader("📜 Log de Saltos y Mapeo Temporal (`saltos_log.json`)")
            st.caption("Registro histórico independiente (llamadas y saltos del admin) para verificar quién estaba en qué posición antes de cada salto.")
            df_log_saltos = obtener_log_saltos_df()
            if df_log_saltos.empty:
                st.info("Aún no se han generado registros en el log independiente de saltos.")
            else:
                filtro_tipo = st.selectbox("Filtrar por tipo:", ["Todos", TIPO_SALTO_LLAMADA, TIPO_SALTO_ADMIN], key="filtro_tipo_log")
                df_log_mostrar = df_log_saltos if filtro_tipo == "Todos" else df_log_saltos[df_log_saltos["Tipo"] == filtro_tipo]
                st.dataframe(df_log_mostrar, use_container_width=True, hide_index=True)

                col_log_csv, col_log_json = st.columns(2)
                with col_log_csv:
                    st.download_button(
                        label="📥 Descargar Log de Saltos (CSV)",
                        data=df_log_saltos.to_csv(index=False).encode("utf-8"),
                        file_name=f"log_saltos_mapeo_temporal_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with col_log_json:
                    raw_log_json = leer_json_github(FILE_LOG_SALTOS, {"saltos": []})
                    st.download_button(
                        label="📥 Descargar Log de Saltos (JSON)",
                        data=json.dumps(raw_log_json, indent=4, ensure_ascii=False).encode("utf-8"),
                        file_name=f"saltos_log_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

        # ------------------------------------------
        # TAB 5: AUDITORÍA DE DEVOLUCIONES IVR Y CRUCE CON SALTOS
        # ------------------------------------------
        with tab_auditoria_ivr:
            st.subheader("🤖 Consolidado y Auditoría de Devoluciones IVR vs. Saltos")
            st.markdown("""
**Lógica de Análisis:**
1. **Carga los 2 archivos de Aircall** (Llamadas Perdidas Inbound y Devoluciones Outbound).
2. **Usa el registro de turnos y log de saltos guardado internamente** (sin necesidad de subir un 3er archivo).
3. **Analiza el mapeo temporal** para validar si el asesor que devolvió la llamada era el primero de la fila en ese momento (incluye los saltos manuales del admin).
""")

            col_u1, col_u2 = st.columns(2)
            with col_u1:
                file_perdidas = st.file_uploader("1. CSV Llamadas Perdidas (Inbound)", type=["csv"], key="audit_p1")
            with col_u2:
                file_callbacks = st.file_uploader("2. CSV Devoluciones / Salientes (Aircall Outbound)", type=["csv"], key="audit_p2")

            with st.expander("⚙️ Filtros Avanzados de IVR (Opcionales)"):
                col_f_ivr1, col_f_ivr2 = st.columns(2)
                with col_f_ivr1:
                    filtro_rama_ivr = st.text_input("Rama IVR especifica (ej: ATC):", value="", key="audit_f1")
                with col_f_ivr2:
                    filtro_widget_ivr = st.text_input("Widget IVR específico (ej: Ventas):", value="", key="audit_f2")

            if file_perdidas is not None and file_callbacks is not None:
                df_res_ivr, err_ivr = analizar_devoluciones_ivr_y_saltos(
                    file_perdidas, file_callbacks,
                    rama_filtro=filtro_rama_ivr,
                    widget_filtro=filtro_widget_ivr,
                )

                if err_ivr:
                    st.error(f"Error al procesar la auditoría: {err_ivr}")
                elif df_res_ivr.empty:
                    st.warning("No se encontraron números perdidos de IVR que hayan recibido llamadas salientes de devolución.")
                else:
                    total_numeros_devueltos = len(df_res_ivr)
                    no_registrados_saltos = len(df_res_ivr[df_res_ivr["Registrado en Saltos"] == "NO REGISTRADO"])
                    multiples_llamadas = len(df_res_ivr[df_res_ivr["Cant. Devoluciones (Aircall)"] > 1])
                    registrados_ok = total_numeros_devueltos - no_registrados_saltos

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Clientes IVR Devueltos", total_numeros_devueltos)
                    c2.metric("✅ Registrados en Saltos", registrados_ok)
                    c3.metric(
                        "🚨 Sin Registro en Saltos", no_registrados_saltos,
                        delta=f"{(no_registrados_saltos / total_numeros_devueltos * 100):.1f}% Omisión" if total_numeros_devueltos > 0 else "0%",
                        delta_color="inverse",
                    )
                    c4.metric("🔄 Marcaciones Múltiples (>1)", multiples_llamadas)

                    st.markdown("---")
                    st.subheader("📊 Consolidado Completo")
                    filtro_estado = st.selectbox(
                        "Filtrar Resultados por Estado:",
                        ["Todos los Devueltos de IVR", "Solo NO Registrados en Saltos",
                         "Solo Múltiples Llamadas en Aircall", "Solo Registrados Correctamente en Saltos"],
                        key="filtro_estado_auditoria",
                    )
                    if filtro_estado == "Solo NO Registrados en Saltos":
                        df_mostrar_ivr = df_res_ivr[df_res_ivr["Registrado en Saltos"] == "NO REGISTRADO"]
                    elif filtro_estado == "Solo Múltiples Llamadas en Aircall":
                        df_mostrar_ivr = df_res_ivr[df_res_ivr["Cant. Devoluciones (Aircall)"] > 1]
                    elif filtro_estado == "Solo Registrados Correctamente en Saltos":
                        df_mostrar_ivr = df_res_ivr[df_res_ivr["Registrado en Saltos"] == "Sí"]
                    else:
                        df_mostrar_ivr = df_res_ivr

                    st.dataframe(df_mostrar_ivr, use_container_width=True, hide_index=True)
                    st.download_button(
                        label="📥 Descargar Reporte Consolidado IVR (CSV)",
                        data=df_res_ivr.to_csv(index=False).encode("utf-8"),
                        file_name=f"reporte_devoluciones_ivr_vs_saltos_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            else:
                st.info("👈 Adjunta los dos archivos CSV de Aircall (Inbound y Outbound) para ejecutar la auditoría.")
