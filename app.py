import json
import random
import re
import time as time_lib
from datetime import datetime, time
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
FILE_TURNOS = "turnos_orden.json"     # Maneja posiciones e historial
FILE_ESTADOS = "agentes_estados.json" # Maneja únicamente toggles activo/ausente
FILE_LOG_SALTOS = "saltos_log.json"   # Mapeo temporal independiente de saltos de turno

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
                    branch=branch
                )
            except GithubException as ex:
                if ex.status == 404:
                    repo.create_file(
                        path=file_path,
                        message=f"Crear archivo: {mensaje_commit}",
                        content=json_str,
                        branch=branch
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
    default_log = {"saltos": []}
    log_actual = leer_json_github(FILE_LOG_SALTOS, default_log)
    
    if "saltos" not in log_actual:
        log_actual["saltos"] = []
    log_actual["saltos"].insert(0, datos_salto)
    escribir_json_github(FILE_LOG_SALTOS, log_actual, f"Log Salto: {datos_salto.get('alias')} (ID: {datos_salto.get('call_id')})")

def obtener_log_saltos_df() -> pd.DataFrame:
    """Carga y procesa el log de saltos para descargarlo o mostrarlo."""
    default_log = {"saltos": []}
    log_actual = leer_json_github(FILE_LOG_SALTOS, default_log)
    saltos = log_actual.get("saltos", [])
    if not saltos:
        return pd.DataFrame()
    registros = []
    for s in saltos:
        registros.append({
            "ID Evento": s.get("id_evento"),
            "Fecha/Hora (Colombia)": s.get("fecha_hora"),
            "ID Llamada": s.get("call_id"),
            "Teléfono": s.get("telefono"),
            "Agente (Alias)": s.get("alias"),
            "Agente (Real)": s.get("nombre_real"),
            "Posición al Saltar": s.get("posicion_al_saltar"),
            "Orden previo snapshot": json.dumps(s.get("orden_previo_snapshot", []), ensure_ascii=False)
        })
    return pd.DataFrame(registros)

# ==========================================
# LÓGICA DE LECTURA Y MEZCLA DE DATOS (READ-ON-MERGE)
# ==========================================
def obtener_estructura_completa_fresca() -> tuple[list, list, dict, list]:
    """Carga de forma independiente el orden/historial y los estados de los agentes, mezclándolos en vivo."""
    def_turnos = {
        "turnos": USUARIOS_INICIALES,
        "historial": [],
        "configuracion": {"modo_auto": "true"},
        "horario_excel": []
    }
    
    def_estados = {u["real"]: {"activo": True, "manual": False} for u in USUARIOS_INICIALES}
    data_turnos = leer_json_github(FILE_TURNOS, def_turnos)
    data_estados = leer_json_github(FILE_ESTADOS, def_estados)
    turnos_lista = sorted(data_turnos.get("turnos", USUARIOS_INICIALES), key=lambda x: x["posicion"])
    historial = data_turnos.get("historial", [])
    config = data_turnos.get("configuracion", {"modo_auto": "true"})
    horario_excel = data_turnos.get("horario_excel", [])
    for t in turnos_lista:
        nombre = t["real"]
        info_est = data_estados.get(nombre, True)
        
        if isinstance(info_est, dict):
            t["activo"] = info_est.get("activo", True)
            t["manual"] = info_est.get("manual", False)
        else:
            t["activo"] = bool(info_est)
            t["manual"] = False
    st.session_state.data_turnos_cache = data_turnos
    st.session_state.data_estados_cache = data_estados
    return turnos_lista, historial, config, horario_excel

def obtener_configuracion(clave: str, valor_defecto: str = "") -> str:
    _, _, config, _ = obtener_estructura_completa_fresca()
    return config.get(clave, valor_defecto)

def guardar_configuracion(clave: str, valor: str):
    data_turnos = leer_json_github(FILE_TURNOS, {})
    if "configuracion" not in data_turnos:
        data_turnos["configuracion"] = {}
    data_turnos["configuracion"][clave] = valor
    escribir_json_github(FILE_TURNOS, data_turnos, f"Configuración {clave}={valor}")

def obtener_lista_turnos() -> list:
    turnos, _, _, _ = obtener_estructura_completa_fresca()
    return turnos

def guardar_cambios_masivos_agentes(estados_seleccionados: dict):
    estados_actuales = leer_json_github(FILE_ESTADOS, {})
    cambios = 0
    
    turnos_actuales, _, _, _ = obtener_estructura_completa_fresca()
    mapa_pos_nombre = {t["posicion"]: t["real"] for t in turnos_actuales}
    for pos, nuevo_activo in estados_seleccionados.items():
        nombre_real = mapa_pos_nombre.get(pos)
        if nombre_real:
            val_actual = estados_actuales.get(nombre_real)
            est_anterior = val_actual.get("activo") if isinstance(val_actual, dict) else val_actual
            
            if est_anterior != nuevo_activo or not (isinstance(val_actual, dict) and val_actual.get("manual")):
                estados_actuales[nombre_real] = {
                    "activo": nuevo_activo,
                    "manual": True
                }
                cambios += 1
    if cambios > 0:
        if escribir_json_github(FILE_ESTADOS, estados_actuales, f"Admin: Anulación manual de {cambios} estados"):
            return True, f"✅ ¡Se guardaron correctamente los cambios manuales de {cambios} agentes!"
    return False, "ℹ️ No se detectaron cambios de estado para guardar."

def resetear_bloqueos_manuales():
    estados_actuales = leer_json_github(FILE_ESTADOS, {})
    for nombre in estados_actuales:
        if isinstance(estados_actuales[nombre], dict):
            estados_actuales[nombre]["manual"] = False
        else:
            estados_actuales[nombre] = {"activo": bool(estados_actuales[nombre]), "manual": False}
    escribir_json_github(FILE_ESTADOS, estados_actuales, "Admin: Restablecer control automático de horarios")

def guardar_horario_db(df: pd.DataFrame):
    data_turnos = leer_json_github(FILE_TURNOS, {})
    data_turnos["horario_excel"] = df.to_dict(orient="records")
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Carga de horario Excel")

def obtener_horario_db() -> pd.DataFrame:
    _, _, _, horario_excel = obtener_estructura_completa_fresca()
    return pd.DataFrame(horario_excel) if horario_excel else pd.DataFrame()

def actualizar_estados_segun_horario(df_horario: pd.DataFrame, forzar_resincro: bool = False):
    if df_horario.empty:
        return
    now_col = obtener_fecha_hora_colombia()
    fecha_hoy_str = now_col.strftime("%Y-%m-%d")
    hora_actual = now_col.time()
    df_horario = df_horario.copy()
    df_horario.columns = [str(c).strip() for c in df_horario.columns]
    
    if "Fecha" in df_horario.columns:
        df_horario["Fecha"] = pd.to_datetime(df_horario["Fecha"]).dt.strftime("%Y-%m-%d")
        df_hoy = df_horario[df_horario["Fecha"] == fecha_hoy_str]
    else:
        df_hoy = df_horario
    def parse_time(val):
        if pd.isna(val) or str(val).strip() in ["", "nan", "None", "00:00:00"]:
            return None
        if isinstance(val, time):
            return val
        if isinstance(val, datetime):
            return val.time()
        try:
            return datetime.strptime(str(val).strip(), "%H:%M:%S").time()
        except ValueError:
            try:
                return datetime.strptime(str(val).strip(), "%H:%M").time()
            except ValueError:
                return None
    agentes_activos_horario = {}
    for _, row in df_hoy.iterrows():
        nombre = str(row.get("Nombre", "")).replace('\xa0', ' ').strip()
        h_inicio = parse_time(row.get("Hora incio"))
        h_fin = parse_time(row.get("Hora fin"))
        
        int_inc = parse_time(row.get("Intermedio inicio"))
        int_fin = parse_time(row.get("Intermedio fin"))
        esta_activo = False
        if h_inicio and h_fin:
            if h_inicio <= hora_actual <= h_fin:
                esta_activo = True
                if int_inc and int_fin and (int_inc <= hora_actual <= int_fin):
                    esta_activo = False
        agentes_activos_horario[nombre.lower()] = esta_activo
    estados_actuales = leer_json_github(FILE_ESTADOS, {})
    hubo_cambios = False
    
    for real_name in list(estados_actuales.keys()):
        nombre_norm = real_name.replace('\xa0', ' ').strip().lower()
        
        info_actual = estados_actuales[real_name]
        es_manual = info_actual.get("manual", False) if isinstance(info_actual, dict) else False
        st_actual = info_actual.get("activo", True) if isinstance(info_actual, dict) else bool(info_actual)
        if es_manual and not forzar_resincro:
            continue
        if nombre_norm in agentes_activos_horario:
            nuevo_st = agentes_activos_horario[nombre_norm]
            if st_actual != nuevo_st or es_manual:
                estados_actuales[real_name] = {
                    "activo": nuevo_st,
                    "manual": False
                }
                hubo_cambios = True
    if hubo_cambios:
        escribir_json_github(FILE_ESTADOS, estados_actuales, "Auto: Sync de estados por horario")

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
    
    turnos, historial, _, _ = obtener_estructura_completa_fresca()
    if any(h.get("call_id") == call_id_clean for h in historial):
        return False, f"❌ El ID de llamada '{call_id_clean}' ya fue registrado previamente."
    if any(h.get("telefono") == telefono_clean for h in historial):
        return False, f"❌ El número de teléfono '{telefono_clean}' ya fue atendido previamente."
    agente_atendiendo = next((t for t in turnos if t["activo"]), None)
    if not agente_atendiendo:
        return False, "❌ Todos los agentes están marcados como Ausentes en este momento."
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
    # Mapeo temporal del estado de la fila ANTES del salto
    snapshot_fila_previa = [
        {"posicion": t["posicion"], "alias": t["alias"], "activo": t["activo"]} 
        for t in turnos
    ]
    # Registrar en historial tradicional
    nuevo_registro = {
        "id": len(historial) + 1,
        "call_id": call_id_clean,
        "telefono": telefono_clean,
        "nombre_real": nombre_real,
        "alias": alias,
        "fecha_hora": now_col
    }
    historial.insert(0, nuevo_registro)
    # Reordenar turnos
    turnos_limpios = [{"posicion": t["posicion"], "real": t["real"], "alias": t["alias"]} for t in turnos]
    agente_limpio = next(t for t in turnos_limpios if t["posicion"] == pos_atendiendo)
    
    turnos_sin_atendiendo = [t for t in turnos_limpios if t["posicion"] != pos_atendiendo]
    nuevos_turnos = turnos_sin_atendiendo + [agente_limpio]
    for idx, t in enumerate(nuevos_turnos, start=1):
        t["posicion"] = idx
    data_turnos = leer_json_github(FILE_TURNOS, {})
    data_turnos["historial"] = historial
    data_turnos["turnos"] = nuevos_turnos
    if escribir_json_github(FILE_TURNOS, data_turnos, f"Avanzar turno atendido por {alias} (ID: {call_id_clean})"):
        # REGISTRAR MAPEO TEMPORAL EN JSON INDEPENDIENTE
        datos_log_salto = {
            "id_evento": len(historial),
            "fecha_hora": now_col,
            "call_id": call_id_clean,
            "telefono": telefono_clean,
            "nombre_real": nombre_real,
            "alias": alias,
            "posicion_al_saltar": pos_atendiendo,
            "orden_previo_snapshot": snapshot_fila_previa
        }
        guardar_evento_log_salto(datos_log_salto)
        return True, f"✅ ¡Turno completado por **{alias}** ({nombre_real})! ID: `{call_id_clean}` y Teléfono: `{telefono_clean}` registrados con éxito."
    else:
        return False, "❌ Hubo un fallo temporal de comunicación con GitHub. Intenta nuevamente."

def obtener_historial_saltos() -> pd.DataFrame:
    _, historial, _, _ = obtener_estructura_completa_fresca()
    if not historial:
        return pd.DataFrame()
    df = pd.DataFrame(historial)
    df = df.rename(columns={
        "id": "ID Reg",
        "call_id": "ID Llamada",
        "telefono": "Teléfono",
        "alias": "Alias",
        "nombre_real": "Nombre Real",
        "fecha_hora": "Fecha / Hora (Colombia)"
    })
    return df

def vaciar_historial_llamadas():
    data_turnos = leer_json_github(FILE_TURNOS, {})
    data_turnos["historial"] = []
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Vaciar historial de llamadas")

def reiniciar_turnos_originales():
    data_turnos = leer_json_github(FILE_TURNOS, {})
    data_turnos["turnos"] = [dict(u) for u in USUARIOS_INICIALES]
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Restablecer turnos al orden inicial")

def reorganizar_turnos_al_azar():
    data_turnos = leer_json_github(FILE_TURNOS, {})
    turnos = data_turnos.get("turnos", USUARIOS_INICIALES)
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
                if es_aircall:
                    dt = dt.tz_localize('Europe/Madrid')
                else:
                    dt = dt.tz_localize('America/Bogota')
            return dt.tz_convert('America/Bogota')
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
        mask_inbound_missed = (df1['direction'] == 'inbound') & (df1['answered'] == 'No')
        
        mask_ivr = (
            df1['line'].astype(str).str.contains('IVR', case=False, na=False) |
            df1['ivr branch'].notna() |
            df1['ivr widget'].notna() |
            (df1['time in ivr'].notna() & (df1['time in ivr'] != '00:00:00'))
        )
        
        if rama_filtro.strip():
            mask_ivr = mask_ivr & (df1['ivr branch'].astype(str).str.contains(rama_filtro.strip(), case=False, na=False))
        if widget_filtro.strip():
            mask_ivr = mask_ivr & (df1['ivr widget'].astype(str).str.contains(widget_filtro.strip(), case=False, na=False))
        
        df_perdidas_ivr = df1[mask_inbound_missed & mask_ivr].copy()
        if df_perdidas_ivr.empty:
            return pd.DataFrame(), "No se encontraron llamadas perdidas que cumplan con los criterios de IVR especificados."
        
        df_perdidas_ivr['num_limpio'] = df_perdidas_ivr['customer number'].astype(str).str.replace(r'\D', '', regex=True)
        
        # 2. Llamadas salientes (Outbound Aircall)
        df_salientes = df2[df2['direction'] == 'outbound'].copy()
        df_salientes['num_limpio'] = df_salientes['customer number'].astype(str).str.replace(r'\D', '', regex=True)
        # 3. Conversión Homogénea de Fechas (España -> Colombia)
        col_fecha1 = 'datetime (tz offset incl.)' if 'datetime (tz offset incl.)' in df1.columns else 'call start time'
        col_fecha2 = 'datetime (tz offset incl.)' if 'datetime (tz offset incl.)' in df2.columns else 'call start time'
        df_perdidas_ivr['dt_perdida'] = convertir_a_colombia_robust(df_perdidas_ivr[col_fecha1], es_aircall=True)
        df_salientes['dt_saliente'] = convertir_a_colombia_robust(df_salientes[col_fecha2], es_aircall=True)
        if not df3.empty:
            col_tel3 = 'Teléfono' if 'Teléfono' in df3.columns else df3.columns[2]
            col_nom3 = 'Nombre Real' if 'Nombre Real' in df3.columns else df3.columns[3]
            col_fecha3 = 'Fecha / Hora (Colombia)' if 'Fecha / Hora (Colombia)' in df3.columns else df3.columns[5]
            df3['num_limpio'] = df3[col_tel3].astype(str).str.replace(r'\D', '', regex=True)
            df3['dt_turno'] = convertir_a_colombia_robust(df3[col_fecha3], es_aircall=False)
        else:
            df3 = pd.DataFrame(columns=['num_limpio', 'dt_turno', 'Nombre Real', 'Alias'])
        set_perdidos_ivr = set(df_perdidas_ivr['num_limpio'])
        set_salientes = set(df_salientes['num_limpio'])
        numeros_devueltos = set_perdidos_ivr.intersection(set_salientes)
        
        if not numeros_devueltos:
            return pd.DataFrame(), "No se encontraron devoluciones a las llamadas perdidas de IVR."
        filas_resumen = []
        for num in numeros_devueltos:
            sub_perdidas = df_perdidas_ivr[df_perdidas_ivr['num_limpio'] == num].sort_values('dt_perdida')
            sub_salientes = df_salientes[df_salientes['num_limpio'] == num].sort_values('dt_saliente')
            sub_turnos = df3[df3['num_limpio'] == num].sort_values('dt_turno') if not df3.empty else pd.DataFrame()
            
            num_cliente = sub_perdidas['customer number'].iloc[0]
            fechas_perdidas_str = " | ".join(sub_perdidas['dt_perdida'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist())
            tot_perdidas = len(sub_perdidas)
            
            linea_ivr = " | ".join(sub_perdidas['line'].astype(str).unique().tolist())
            motivos_perdida = " | ".join(sub_perdidas['missed_call_reason'].astype(str).unique().tolist())
            rama_ivr = " | ".join(sub_perdidas['ivr branch'].dropna().astype(str).unique().tolist()) or "N/A"
            widget_ivr = " | ".join(sub_perdidas['ivr widget'].dropna().astype(str).unique().tolist()) or "N/A"
            
            tot_salientes = len(sub_salientes)
            horarios_salientes_str = " | ".join(sub_salientes['dt_saliente'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist())
            asesores_salientes_str = " | ".join(sub_salientes['user'].astype(str).unique().tolist())
            
            tot_turnos = len(sub_turnos) if not sub_turnos.empty else 0
            registrado_flag = "Sí" if tot_turnos > 0 else "NO REGISTRADO"
            horarios_turnos_str = " | ".join(sub_turnos['dt_turno'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()) if tot_turnos > 0 else "N/A"
            asesores_turnos_str = " | ".join(sub_turnos[col_nom3].astype(str).unique().tolist()) if tot_turnos > 0 else "N/A"
            # MAPEO TEMPORAL DE TURNO: Evaluar en Hora Colombia quién estaba de primero activo al momento del evento
            primera_fecha_saliente = sub_salientes['dt_saliente'].iloc[0]
            agente_que_tocaba = "Desconocido (Sin snapshot)"
            coincidio_turno = "N/A"
            # Filtrar snapshots de saltos con hora normalizada a Colombia
            saltos_previos = []
            for s in raw_log_saltos:
                dt_s = convertir_a_colombia_robust(pd.Series([s.get('fecha_hora')]), es_aircall=False).iloc[0]
                if pd.notna(dt_s) and dt_s <= primera_fecha_saliente + pd.Timedelta(minutes=5):
                    saltos_previos.append((dt_s, s))
            if saltos_previos:
                # Obtener el snapshot inmediatamente previo más cercano
                ultimo_salto = max(saltos_previos, key=lambda x: x[0])[1]
                snapshot = ultimo_salto.get("orden_previo_snapshot", [])
                
                # Filtrar el primer agente activo ordenado por posición en la fila
                activos_snapshot = sorted([ag for ag in snapshot if ag.get("activo")], key=lambda x: x.get("posicion", 999))
                if activos_snapshot:
                    agente_que_tocaba = activos_snapshot[0].get("alias", "Desconocido")
            if agente_que_tocaba != "Desconocido (Sin snapshot)" and asesores_salientes_str != "N/A":
                if agente_que_tocaba.lower() in asesores_salientes_str.lower() or asesores_salientes_str.lower() in agente_que_tocaba.lower():
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
                'Número Cliente': num_cliente,
                'Línea IVR': linea_ivr,
                'Rama IVR': rama_ivr,
                'Widget IVR': widget_ivr,
                'Motivo Pérdida IVR': motivos_perdida,
                'Perdidas en IVR': tot_perdidas,
                'Horario Llamada Perdida IVR (Colombia)': fechas_perdidas_str,
                'Cant. Devoluciones (Aircall)': tot_salientes,
                'Horarios Devolución (Aircall / Colombia)': horarios_salientes_str,
                'Asesor que Devolvió (Aircall)': asesores_salientes_str,
                'Agente que le Tocaba (Snapshot)': agente_que_tocaba,
                'Validación de Turno': coincidio_turno,
                'Registrado en Saltos': registrado_flag,
                'Cant. Registros Saltos': tot_turnos,
                'Horarios Registro Saltos (Colombia)': horarios_turnos_str,
                'Asesores Registro Saltos': asesores_turnos_str,
                'Estado Auditoría': diagnostico
            })
        df_resultado = pd.DataFrame(filas_resumen).sort_values(
            by=['Cant. Devoluciones (Aircall)', 'Registrado en Saltos'],
            ascending=[False, True]
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
    usar_horario_auto = obtener_configuracion("modo_auto", "true") == "true"
    if usar_horario_auto:
        df_excel = obtener_horario_db()
        if not df_excel.empty:
            actualizar_estados_segun_horario(df_excel)
    turnos_actuales = obtener_lista_turnos()
    actual = next((t for t in turnos_actuales if t["activo"]), None)
    if actual:
        st.markdown("---")
        col_turn_1, col_turn_2 = st.columns([2, 3])
        with col_turn_1:
            st.metric(label="🎯 TURNO ACTUAL (ATENDIENDO)", value=actual["alias"])
            st.write(f"👤 **Nombre Real:** {actual['real']}")
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
        st.error("⚠️ Todos los agentes se encuentran marcados como Ausentes en este momento.")

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
        # PESTAÑAS DENTRO DEL PANEL ADMINISTRADOR
        tab_gestion, tab_historial, tab_log_saltos, tab_auditoria_ivr = st.tabs([
            "⚙️ Gestión General y Horarios",
            "📊 Historial de Llamadas",
            "📜 Log de Saltos y Mapeo Temporal",
            "🤖 Auditoría Devoluciones IVR"
        ])
        # ------------------------------------------
        # TAB 1: GESTIÓN GENERAL Y HORARIOS
        # ------------------------------------------
        with tab_gestion:
            st.subheader("📋 Fila Actual de Posiciones")
            turnos_admin_vista = obtener_lista_turnos()
            tabla_display = [
                {
                    "Posición": t["posicion"],
                    "Estado": ("🟢 Activo (Manual)" if t.get("manual") else "🟢 Activo") if t["activo"] else ("🔴 Ausente (Manual)" if t.get("manual") else "🔴 Ausente"),
                    "Nombre Real": t["real"],
                    "Alias / Nombre en Sistema": t["alias"]
                } for t in turnos_admin_vista
            ]
            st.dataframe(pd.DataFrame(tabla_display), use_container_width=True, hide_index=True)
            st.markdown("---")

            st.subheader("📅 Carga e Integración de Horario Excel")
            uploaded_file = st.file_uploader("Subir archivo de horarios (.xlsx, .csv)", type=["xlsx", "csv"])
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        df_excel = pd.read_csv(uploaded_file)
                    else:
                        df_excel = pd.read_excel(uploaded_file)
                    guardar_horario_db(df_excel)
                    st.success("✅ Archivo de horarios guardado permanentemente en GitHub.")
                    with st.expander("Ver Vista Previa del Horario Cargado"):
                        st.dataframe(df_excel.head(10), use_container_width=True)
                except Exception as e:
                    st.error(f"Error al leer el archivo: {e}")
            else:
                df_guardado = obtener_horario_db()
                if not df_guardado.empty:
                    st.info("ℹ️ Ya existe un horario cargado en la base de datos.")
            st.markdown("---")
            st.subheader("⚙️ Modo de Activación de Agentes")
            
            modo_auto_actual = obtener_configuracion("modo_auto", "true") == "true"
            modo_auto = st.toggle(
                "Usar Activación Automática por Horario (Hora Colombia)",
                value=modo_auto_actual,
                key="usar_horario_auto"
            )
            if modo_auto != modo_auto_actual:
                guardar_configuracion("modo_auto", "true" if modo_auto else "false")
                st.rerun()
            if modo_auto:
                st.info("ℹ️ La activación automática está **ACTIVADA**. Los cambios manuales mantendrán su prioridad hasta que se resincronice el horario.")
                df_actual = obtener_horario_db()
                if not df_actual.empty:
                    col_sync1, col_sync2 = st.columns(2)
                    with col_sync1:
                        if st.button("🔄 Sincronizar Horario (Respetar Modificaciones Manuales)"):
                            actualizar_estados_segun_horario(df_actual, forzar_resincro=False)
                            st.success("✅ Sincronizado sin alterar cambios manuales.")
                            st.rerun()
                    with col_sync2:
                        if st.button("⚡ Restablecer y Forzar Horario de Excel"):
                            resetear_bloqueos_manuales()
                            actualizar_estados_segun_horario(df_actual, forzar_resincro=True)
                            st.success("✅ Todos los estados volvieron a sincronizarse exactamente con el Excel.")
                            st.rerun()
                else:
                    st.warning("⚠️ No se ha subido ningún archivo de Excel aún.")
            else:
                st.warning("⚠️ Activación automática **DESACTIVADA**. Se usará únicamente el control manual de estados.")
            st.markdown("---")
            st.subheader("👥 Control Manual de Ausencias (Sobrescribe Horario)")
            st.caption("Al cambiar el toggle de un agente, su estado quedará fijado manualmente hasta que presiones 'Restablecer y Forzar Horario de Excel'.")
            turnos_admin = obtener_lista_turnos()
            
            with st.expander("Ver y Gestionar Lista de Ausencias Manualmente", expanded=True):
                estados_seleccionados = {}
                for t in turnos_admin:
                    col_name, col_status = st.columns([3, 1])
                    with col_name:
                        etiqueta_manual = " 📌 *(Manual)*" if t.get("manual") else ""
                        st.write(f"#{t['posicion']} **{t['alias']}** ({t['real']}){etiqueta_manual}")
                    with col_status:
                        nuevo_estado = st.toggle(
                            "Activo" if t["activo"] else "Ausente",
                            value=t["activo"],
                            key=f"toggle_agente_{t['posicion']}"
                        )
                        estados_seleccionados[t["posicion"]] = nuevo_estado
                st.markdown("---")
                if st.button("💾 Guardar y Publicar Cambios de Estado", type="primary", use_container_width=True):
                    exito, msj = guardar_cambios_masivos_agentes(estados_seleccionados)
                    if exito:
                        st.success(msj)
                        st.rerun()
                    else:
                        st.info(msj)
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
        # TAB 2: HISTORIAL DE LLAMADAS
        # ------------------------------------------
        with tab_historial:
            st.subheader("📊 Historial de Registro de Llamadas")
            df_historial = obtener_historial_saltos()
            if df_historial.empty:
                st.info("Aún no se han registrado llamadas.")
            else:
                st.dataframe(df_historial, use_container_width=True, hide_index=True)
                csv_data = df_historial.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Descargar Reporte Llamadas CSV",
                    data=csv_data,
                    file_name=f"reporte_llamadas_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        # ------------------------------------------
        # TAB 3: LOG DE SALTOS Y MAPEO TEMPORAL
        # ------------------------------------------
        with tab_log_saltos:
            st.subheader("📜 Log de Saltos y Mapeo Temporal (`saltos_log.json`)")
            st.caption("Registro histórico independiente para verificar quién estaba en qué posición antes de cada salto.")
            
            df_log_saltos = obtener_log_saltos_df()
            
            if df_log_saltos.empty:
                st.info("Aún no se han generado registros en el log independiente de saltos.")
            else:
                st.dataframe(df_log_saltos, use_container_width=True, hide_index=True)
                
                col_log_csv, col_log_json = st.columns(2)
                
                with col_log_csv:
                    csv_log_bytes = df_log_saltos.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📥 Descargar Log de Saltos (CSV)",
                        data=csv_log_bytes,
                        file_name=f"log_saltos_mapeo_temporal_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                with col_log_json:
                    raw_log_json = leer_json_github(FILE_LOG_SALTOS, {"saltos": []})
                    json_log_bytes = json.dumps(raw_log_json, indent=4, ensure_ascii=False).encode("utf-8")
                    st.download_button(
                        label="📥 Descargar Log de Saltos (JSON)",
                        data=json_log_bytes,
                        file_name=f"saltos_log_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        # ------------------------------------------
        # TAB 4: AUDITORÍA DE DEVOLUCIONES IVR Y CRUCE CON SALTOS
        # ------------------------------------------
        with tab_auditoria_ivr:
            st.subheader("🤖 Consolidado y Auditoría de Devoluciones IVR vs. Saltos")
            st.markdown("""
            **Lógica de Análisis:**
            1. **Carga los 2 archivos de Aircall** (Llamadas Perdidas Inbound y Devoluciones Outbound).
            2. **Usa el registro de turnos y log de saltos guardado internamente** (sin necesidad de subir un 3er archivo).
            3. **Analiza el mapeo temporal** para validar si el asesor que devolvió la llamada coincidía con el turno asignado en ese momento.
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
                    widget_filtro=filtro_widget_ivr
                )
                if err_ivr:
                    st.error(f"Error al procesar la auditoría: {err_ivr}")
                elif df_res_ivr.empty:
                    st.warning("No se encontraron números perdidos de IVR que hayan recibido llamadas salientes de devolución.")
                else:
                    total_numeros_devueltos = len(df_res_ivr)
                    no_registrados_saltos = len(df_res_ivr[df_res_ivr['Registrado en Saltos'] == 'NO REGISTRADO'])
                    multiples_llamadas = len(df_res_ivr[df_res_ivr['Cant. Devoluciones (Aircall)'] > 1])
                    registrados_ok = total_numeros_devueltos - no_registrados_saltos
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Clientes IVR Devueltos", total_numeros_devueltos)
                    c2.metric("✅ Registrados en Saltos", registrados_ok)
                    c3.metric("🚨 Sin Registro en Saltos", no_registrados_saltos, delta=f"{(no_registrados_saltos/total_numeros_devueltos*100):.1f}% Omisión" if total_numeros_devueltos>0 else "0%", delta_color="inverse")
                    c4.metric("🔄 Marcaciones Múltiples (>1)", multiples_llamadas)
                    st.markdown("---")
                    st.subheader("📊 Consolidado Completo")
                    filtro_estado = st.selectbox(
                        "Filtrar Resultados por Estado:",
                        ["Todos los Devueltos de IVR", "Solo NO Registrados en Saltos", "Solo Múltiples Llamadas en Aircall", "Solo Registrados Correctamente en Saltos"],
                        key="filtro_estado_auditoria"
                    )
                    if filtro_estado == "Solo NO Registrados en Saltos":
                        df_mostrar_ivr = df_res_ivr[df_res_ivr['Registrado en Saltos'] == 'NO REGISTRADO']
                    elif filtro_estado == "Solo Múltiples Llamadas en Aircall":
                        df_mostrar_ivr = df_res_ivr[df_res_ivr['Cant. Devoluciones (Aircall)'] > 1]
                    elif filtro_estado == "Solo Registrados Correctamente en Saltos":
                        df_mostrar_ivr = df_res_ivr[df_res_ivr['Registrado en Saltos'] == 'Sí']
                    else:
                        df_mostrar_ivr = df_res_ivr
                    st.dataframe(df_mostrar_ivr, use_container_width=True, hide_index=True)
                    csv_download_ivr = df_res_ivr.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Reporte Consolidado IVR (CSV)",
                        data=csv_download_ivr,
                        file_name=f"reporte_devoluciones_ivr_vs_saltos_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            else:
                st.info("👈 Adjunta los dos archivos CSV de Aircall (Inbound y Outbound) para ejecutar la auditoría.")
