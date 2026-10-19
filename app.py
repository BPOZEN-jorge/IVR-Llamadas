import json
import random
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
    {"posicion": 18, "real": "Julián Andrés Osorio Aristizabal", "alias": "Andrés Aristizábal"},
    {"posicion": 19, "real": "Karen Herrera Gonzalez", "alias": "Karen"},
    {"posicion": 20, "real": "Kelly Jhoana Salas Ibarguen", "alias": "Kelly Salas"},
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
    {"posicion": 32, "real": "Stefany Vanegas Arbelaez", "alias": "Stefany"},
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
                time_lib.sleep(0.5)  # Esperar medio segundo antes de reintentar
            else:
                st.error(f"❌ Error al guardar en {file_path} tras varios intentos: {e}")
                return False

# ==========================================
# LOGICA DE LECTURA Y MEZCLA DE DATOS (READ-ON-MERGE)
# ==========================================
def obtener_estructura_completa_fresca() -> tuple[list, list, dict, list]:
    """Carga de forma independiente el orden/historial y los estados de los agentes, mezclándolos en vivo."""
    def_turnos = {
        "turnos": USUARIOS_INICIALES,
        "historial": [],
        "configuracion": {"modo_auto": "true"},
        "horario_excel": []
    }
    def_estados = {u["real"]: True for u in USUARIOS_INICIALES}

    data_turnos = leer_json_github(FILE_TURNOS, def_turnos)
    data_estados = leer_json_github(FILE_ESTADOS, def_estados)

    turnos_lista = sorted(data_turnos.get("turnos", USUARIOS_INICIALES), key=lambda x: x["posicion"])
    historial = data_turnos.get("historial", [])
    config = data_turnos.get("configuracion", {"modo_auto": "true"})
    horario_excel = data_turnos.get("horario_excel", [])

    # Inyectar el estado activo/ausente más reciente desde data_estados
    for t in turnos_lista:
        nombre = t["real"]
        t["activo"] = data_estados.get(nombre, True)

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

def guardar_cambios_masivos_agentes(estados_nuevos: dict):
    """Guarda Exclusivamente en `agentes_estados.json` sin tocar las posiciones ni el historial."""
    estados_actuales = leer_json_github(FILE_ESTADOS, {u["real"]: True for u in USUARIOS_INICIALES})
    cambios = 0
    
    # Mapear posicion a nombre_real
    turnos_actuales, _, _, _ = obtener_estructura_completa_fresca()
    mapa_pos_nombre = {t["posicion"]: t["real"] for t in turnos_actuales}

    for pos, nuevo_activo in estados_seleccionados.items():
        nombre_real = mapa_pos_nombre.get(pos)
        if nombre_real and estados_actuales.get(nombre_real) != nuevo_activo:
            estados_actuales[nombre_real] = nuevo_activo
            cambios += 1

    if cambios > 0:
        if escribir_json_github(FILE_ESTADOS, estados_actuales, f"Admin: Actualización de {cambios} estados"):
            return True, f"✅ ¡Se guardaron correctamente los estados de {cambios} agentes!"
    return False, "ℹ️ No se detectaron cambios de estado para guardar."

def guardar_horario_db(df: pd.DataFrame):
    data_turnos = leer_json_github(FILE_TURNOS, {})
    data_turnos["horario_excel"] = df.to_dict(orient="records")
    escribir_json_github(FILE_TURNOS, data_turnos, "Admin: Carga de horario Excel")

def obtener_horario_db() -> pd.DataFrame:
    _, _, _, horario_excel = obtener_estructura_completa_fresca()
    return pd.DataFrame(horario_excel) if horario_excel else pd.DataFrame()

def actualizar_estados_segun_horario(df_horario: pd.DataFrame):
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
    
    for real_name in estados_actuales.keys():
        nombre_norm = real_name.replace('\xa0', ' ').strip().lower()
        if nombre_norm in agentes_activos_horario:
            nuevo_st = agentes_activos_horario[nombre_norm]
            if estados_actuales[real_name] != nuevo_st:
                estados_actuales[real_name] = nuevo_st
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
    
    # Cargar versión más reciente mezclada
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

    # Registrar en historial
    nuevo_registro = {
        "id": len(historial) + 1,
        "call_id": call_id_clean,
        "telefono": telefono_clean,
        "nombre_real": nombre_real,
        "alias": alias,
        "fecha_hora": now_col
    }
    historial.insert(0, nuevo_registro)

    # Reordenar turnos limpiando la llave 'activo' antes de guardar a JSON (solo guardamos posiciones)
    turnos_limpios = [{"posicion": t["posicion"], "real": t["real"], "alias": t["alias"]} for t in turnos]
    agente_limpio = next(t for t in turnos_limpios if t["posicion"] == pos_atendiendo)
    
    turnos_sin_atendiendo = [t for t in turnos_limpios if t["posicion"] != pos_atendiendo]
    nuevos_turnos = turnos_sin_atendiendo + [agente_limpio]

    for idx, t in enumerate(nuevos_turnos, start=1):
        t["posicion"] = idx

    data_turnos = leer_json_github(FILE_TURNOS, {})
    data_turnos["historial"] = historial
    data_turnos["turnos"] = nuevos_turnos

    # GUARDAR ÚNICAMENTE EN FILE_TURNOS (Sin colisión con cambios de estado en FILE_ESTADOS)
    if escribir_json_github(FILE_TURNOS, data_turnos, f"Avanzar turno atendido por {alias} (ID: {call_id_clean})"):
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
            st.caption(f"Posición Fila: #{actual['posicion']}")

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

    st.markdown("---")
    st.subheader("📋 Fila Actual de Posiciones")
    
    tabla_display = [
        {
            "Posición": t["posicion"],
            "Estado": "🟢 Activo" if t["activo"] else "🔴 Ausente",
            "Nombre Real": t["real"],
            "Alias / Nombre en Sistema": t["alias"]
        } for t in turnos_actuales
    ]
    
    st.dataframe(pd.DataFrame(tabla_display), use_container_width=True, hide_index=True)

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
            st.info("ℹ️ La activación automática según el Excel está **ACTIVADA** y persistirá tras reinicios.")
            df_actual = obtener_horario_db()
            if not df_actual.empty:
                if st.button("🔄 Sincronizar Horario Ahora"):
                    actualizar_estados_segun_horario(df_actual)
                    st.success("✅ Agentes sincronizados según la hora actual de Colombia.")
                    st.rerun()
            else:
                st.warning("⚠️ No se ha subido ningún archivo de Excel aún.")
        else:
            st.warning("⚠️ Activación automática **DESACTIVADA**. Se usará la activación manual como opción de respaldo.")

        st.markdown("---")
        st.subheader("👥 Control Manual de Ausencias (Segunda Opción)")
        st.caption("Usa estas casillas para activar o desactivar manualmente a un agente y presiona el botón al final para publicar los cambios en GitHub.")

        turnos_admin = obtener_lista_turnos()
        
        with st.expander("Ver y Gestionar Lista de Ausencias Manualmente", expanded=not modo_auto):
            estados_seleccionados = {}
            for t in turnos_admin:
                col_name, col_status = st.columns([3, 1])
                with col_name:
                    st.write(f"#{t['posicion']} **{t['alias']}** ({t['real']})")
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
        st.subheader("📊 Historial de Registro de Llamadas y Saltos")
        df_historial = obtener_historial_saltos()

        if df_historial.empty:
            st.info("Aún no se han registrado saltos de turno.")
        else:
            st.dataframe(df_historial, use_container_width=True, hide_index=True)

            col_csv, col_del = st.columns(2)
            with col_csv:
                csv_data = df_historial.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Descargar Reporte CSV (Hora Colombia)",
                    data=csv_data,
                    file_name=f"reporte_saltos_turnos_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

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