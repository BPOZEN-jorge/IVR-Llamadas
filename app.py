import json
import random
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

DATA_FILE_PATH = "turnos_datos.json"

# ==========================================
# DATOS INICIALES DE USUARIOS (Estructura base para JSON)
# ==========================================
USUARIOS_INICIALES = [
    {"posicion": 1, "real": "Alisson Correa Gaviria", "alias": "Alisson", "activo": True},
    {"posicion": 2, "real": "Ana Maria Sanchez Gamboa", "alias": "Maria Sanchez", "activo": True},
    {"posicion": 3, "real": "Andrea Mileidy londoño Bedoya", "alias": "Andrea Valverde", "activo": True},
    {"posicion": 4, "real": "Angie Valeria Quirama Hernández", "alias": "Valeria Hernandez", "activo": True},
    {"posicion": 5, "real": "Angie Vanessa García", "alias": "Maria Antonia García", "activo": True},
    {"posicion": 6, "real": "Brayan Andrey Bustamante", "alias": "Marcos Garcia", "activo": True},
    {"posicion": 7, "real": "Carlos Alberto Herrera Cardeño", "alias": "Carlos Herrera / Alberto Fernandez", "activo": True},
    {"posicion": 8, "real": "Claudia Marcela Manco Vargas", "alias": "Marcela", "activo": True},
    {"posicion": 9, "real": "Cristian David Acosta Montoya", "alias": "Manuel Vasquez", "activo": True},
    {"posicion": 10, "real": "Dayana Botero Rojas", "alias": "Isabel Botero", "activo": True},
    {"posicion": 11, "real": "Evelin Acevedo Cortés", "alias": "Gabriela", "activo": True},
    {"posicion": 12, "real": "Gustavo Adolfo Barrientos Serna", "alias": "Gustavo", "activo": True},
    {"posicion": 13, "real": "Iris Sabiana Cano Cano", "alias": "Maria Cano", "activo": True},
    {"posicion": 14, "real": "Janis Henao Vasco", "alias": "María José", "activo": True},
    {"posicion": 15, "real": "Johana Osorio Bedoya", "alias": "Johana Sanchez", "activo": True},
    {"posicion": 16, "real": "Juan Esteban Acevedo Garces", "alias": "Juan Esteban", "activo": True},
    {"posicion": 17, "real": "Juan Sebastian Serna Sepulveda", "alias": "Juan Sebastian", "activo": True},
    {"posicion": 18, "real": "Julián Andrés Osorio Aristizabal", "alias": "Andrés Aristizábal", "activo": True},
    {"posicion": 19, "real": "Karen Herrera Gonzalez", "alias": "Karen", "activo": True},
    {"posicion": 20, "real": "Kelly Jhoana Salas Ibarguen", "alias": "Kelly Salas", "activo": True},
    {"posicion": 21, "real": "Libia Paola Romero Cantillo", "alias": "Paola Romero", "activo": True},
    {"posicion": 22, "real": "Linda Liceth Pérez Pineda", "alias": "Linda Pérez / Elena Pérez", "activo": True},
    {"posicion": 23, "real": "Luis Alberto Lozano Ibarra", "alias": "Luis Lozano", "activo": True},
    {"posicion": 24, "real": "Manuela villegas Giraldo", "alias": "Manuela Villegas", "activo": True},
    {"posicion": 25, "real": "María Karolina Viana Cancio", "alias": "Karolina", "activo": True},
    {"posicion": 26, "real": "Mateo Cano Hincapié", "alias": "Antonio de la villa", "activo": True},
    {"posicion": 27, "real": "Omar David Barboza Carbonero", "alias": "Omar", "activo": True},
    {"posicion": 28, "real": "Oscar José Llanos Mendinueta", "alias": "Oscar", "activo": True},
    {"posicion": 29, "real": "Paula Andrea Guzman Jaramillo", "alias": "Paula", "activo": True},
    {"posicion": 30, "real": "Rosa Elvira Agamez López", "alias": "Flor Lopez", "activo": True},
    {"posicion": 31, "real": "Sara Gómez Bayona", "alias": "Sara Gómez", "activo": True},
    {"posicion": 32, "real": "Stefany Vanegas Arbelaez", "alias": "Stefany", "activo": True},
    {"posicion": 33, "real": "Tatiana Magreth Acevedo Marín", "alias": "Tatiana", "activo": True},
    {"posicion": 34, "real": "Tomas Castaño Gómez", "alias": "Tomas", "activo": True},
    {"posicion": 35, "real": "Viviana Pacheco Córdoba", "alias": "Viviana Gómez", "activo": True},
    {"posicion": 36, "real": "Yarlen Biviana Son Cedeño", "alias": "Maria Rodriguez", "activo": True},
    {"posicion": 37, "real": "Yarnedis Cecilia Urrutia Pérez", "alias": "Cecilia López", "activo": True},
    {"posicion": 38, "real": "Yeismer Miranda Ramirez", "alias": "Leo Miranda", "activo": True},
    {"posicion": 39, "real": "Yesica Paola Lopez Arango", "alias": "Yesica López", "activo": True},
    {"posicion": 40, "real": "Yesly Marilyn Carrero Rivera", "alias": "Marilyn Carrero", "activo": True},
]

def obtener_fecha_hora_colombia() -> datetime:
    """Retorna objeto datetime actual en Zona Horaria de Colombia."""
    return datetime.now(ZoneInfo("America/Bogota"))

def obtener_hora_colombia_str() -> str:
    """Retorna la fecha y hora actual formateada en hora de Colombia (America/Bogota)."""
    return obtener_fecha_hora_colombia().strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# GESTIÓN DE PERSISTENCIA VÍA API DE GITHUB
# ==========================================
def obtener_repositorio_github():
    token = st.secrets.get("github", {}).get("token")
    repo_name = st.secrets.get("github", {}).get("repo")
    if not token or not repo_name:
        st.error("⚠️ Configuración incompleta de GitHub en los secretos (`st.secrets`).")
        st.stop()
    g = Github(token)
    return g.get_repo(repo_name)

def cargar_datos_desde_github() -> dict:
    """Carga el archivo JSON desde GitHub. Si no existe, lo inicializa."""
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    try:
        content = repo.get_contents(DATA_FILE_PATH, ref=branch)
        data = json.loads(content.decoded_content.decode("utf-8"))
        return data
    except GithubException as e:
        if e.status == 404:
            # Archivo no existe aún en GitHub: Crear con valores por defecto
            datos_iniciales = {
                "turnos": USUARIOS_INICIALES,
                "historial": [],
                "configuracion": {"modo_auto": "true"},
                "horario_excel": []
            }
            guardar_datos_en_github(datos_iniciales, "Inicializar base de datos JSON")
            return datos_iniciales
        st.error(f"Error al conectar con GitHub: {e}")
        st.stop()

def guardar_datos_en_github(data: dict, mensaje_commit: str):
    """Guarda los datos en GitHub generando un commit directo."""
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    json_str = json.dumps(data, indent=4, ensure_ascii=False)

    try:
        content = repo.get_contents(DATA_FILE_PATH, ref=branch)
        repo.update_file(
            path=DATA_FILE_PATH,
            message=f"Auto-update: {mensaje_commit}",
            content=json_str,
            sha=content.sha,
            branch=branch
        )
    except GithubException as e:
        if e.status == 404:
            repo.create_file(
                path=DATA_FILE_PATH,
                message=f"Crear archivo: {mensaje_commit}",
                content=json_str,
                branch=branch
            )
        else:
            st.error(f"Error guardando cambios en GitHub: {e}")

# ==========================================
# MANEJO DE ESTADO EN MEMORIA Y CACHÉ
# ==========================================
if "db_data" not in st.session_state:
    st.session_state.db_data = cargar_datos_desde_github()

def sync_data():
    """Recarga los datos actualizados desde GitHub a la sesión actual."""
    st.session_state.db_data = cargar_datos_desde_github()

def obtener_configuracion(clave: str, valor_defecto: str = "") -> str:
    return st.session_state.db_data.get("configuracion", {}).get(clave, valor_defecto)

def guardar_configuracion(clave: str, valor: str):
    data = st.session_state.db_data
    if "configuracion" not in data:
        data["configuracion"] = {}
    data["configuracion"][clave] = valor
    guardar_datos_en_github(data, f"Actualizar configuracion {clave}={valor}")
    st.session_state.db_data = data

def obtener_lista_turnos() -> list:
    turnos = st.session_state.db_data.get("turnos", [])
    return sorted(turnos, key=lambda x: x["posicion"])

def cambiar_estado_agente(posicion: int, activo: bool):
    data = st.session_state.db_data
    modificado = False
    for t in data.get("turnos", []):
        if t["posicion"] == posicion:
            if t["activo"] != activo:
                t["activo"] = activo
                modificado = True
            break
    if modificado:
        guardar_datos_en_github(data, f"Cambiar estado agente pos {posicion} a {activo}")
        st.session_state.db_data = data

def guardar_horario_db(df: pd.DataFrame):
    data = st.session_state.db_data
    data["horario_excel"] = df.to_dict(orient="records")
    guardar_datos_en_github(data, "Carga de nuevo horario Excel/CSV")
    st.session_state.db_data = data

def obtener_horario_db() -> pd.DataFrame:
    records = st.session_state.db_data.get("horario_excel", [])
    return pd.DataFrame(records) if records else pd.DataFrame()

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

    agentes_activos = {}
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

        agentes_activos[nombre.lower()] = esta_activo

    data = st.session_state.db_data
    hubo_cambios = False
    for t in data.get("turnos", []):
        nombre_norm = t["real"].replace('\xa0', ' ').strip().lower()
        if nombre_norm in agentes_activos:
            nuevo_estado = agentes_activos[nombre_norm]
            if t["activo"] != nuevo_estado:
                t["activo"] = nuevo_estado
                hubo_cambios = True

    if hubo_cambios:
        guardar_datos_en_github(data, "Sincronización automática de estados según horario")
        st.session_state.db_data = data

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
    data = st.session_state.db_data
    historial = data.get("historial", [])
    turnos = obtener_lista_turnos()

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

    # Reordenar turnos (el que atendió pasa al final)
    turnos_sin_atendiendo = [t for t in turnos if t["posicion"] != pos_atendiendo]
    nuevos_turnos = turnos_sin_atendiendo + [agente_atendiendo]

    for idx, t in enumerate(nuevos_turnos, start=1):
        t["posicion"] = idx

    data["historial"] = historial
    data["turnos"] = nuevos_turnos

    guardar_datos_en_github(data, f"Salto de turno atendido por {alias} (ID: {call_id_clean})")
    st.session_state.db_data = data

    return True, f"✅ ¡Turno completado por **{alias}** ({nombre_real})! ID: `{call_id_clean}` y Teléfono: `{telefono_clean}` registrados con éxito."

def obtener_historial_saltos() -> pd.DataFrame:
    historial = st.session_state.db_data.get("historial", [])
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
    data = st.session_state.db_data
    data["historial"] = []
    guardar_datos_en_github(data, "Vaciar historial de llamadas")
    st.session_state.db_data = data

def reiniciar_turnos_originales():
    data = st.session_state.db_data
    data["turnos"] = [dict(u) for u in USUARIOS_INICIALES]
    guardar_datos_en_github(data, "Restablecer turnos al orden inicial")
    st.session_state.db_data = data

def reorganizar_turnos_al_azar():
    data = st.session_state.db_data
    turnos = obtener_lista_turnos()
    random.shuffle(turnos)
    for idx, t in enumerate(turnos, start=1):
        t["posicion"] = idx
    data["turnos"] = turnos
    guardar_datos_en_github(data, "Reorganizar turnos al azar")
    st.session_state.db_data = data

# ==========================================
# INTERFAZ DE NAVEGACIÓN Y VISTAS
# ==========================================
st.sidebar.title("📌 Portal de Turnos")
if st.sidebar.button("🔄 Sincronizar con GitHub", use_container_width=True):
    sync_data()
    st.sidebar.success("Datos actualizados desde el repositorio.")

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
        st.caption("Usa estas casillas para activar o desactivar manualmente a un agente.")

        turnos_admin = obtener_lista_turnos()
        
        with st.expander("Ver y Gestionar Lista de Ausencias Manualmente", expanded=not modo_auto):
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
                    if nuevo_estado != t["activo"]:
                        cambiar_estado_agente(t["posicion"], nuevo_estado)
                        st.toast(f"Agente {t['alias']} marcado como {'Activo' if nuevo_estado else 'Ausente'}.")
                        st.rerun()

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