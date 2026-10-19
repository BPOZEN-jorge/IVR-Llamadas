import sqlite3
import random
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Sistema de Turnos y Llamadas BPO",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "turnos_llamadas.db"

# ==========================================
# DATOS INICIALES DE USUARIOS (Nombres ajustados según Excel)
# ==========================================
USUARIOS_INICIALES = [
    {"real": "Alisson Correa Gaviria", "alias": "Alisson"},
    {"real": "Ana Maria Sanchez Gamboa", "alias": "Maria Sanchez"},
    {"real": "Andrea Mileidy londoño Bedoya", "alias": "Andrea Valverde"},
    {"real": "Angie Valeria Quirama Hernández", "alias": "Valeria Hernandez"},
    {"real": "Angie Vanessa García", "alias": "Maria Antonia García"},
    {"real": "Brayan Andrey Bustamante", "alias": "Marcos Garcia"},
    {"real": "Carlos Alberto Herrera Cardeño", "alias": "Carlos Herrera / Alberto Fernandez"},
    {"real": "Claudia Marcela Manco Vargas", "alias": "Marcela"},
    {"real": "Cristian David Acosta Montoya", "alias": "Manuel Vasquez"},
    {"real": "Dayana Botero Rojas", "alias": "Isabel Botero"},
    {"real": "Evelin Acevedo Cortés", "alias": "Gabriela"},
    {"real": "Gustavo Adolfo Barrientos Serna", "alias": "Gustavo"},
    {"real": "Iris Sabiana Cano Cano", "alias": "Maria Cano"},
    {"real": "Janis Henao Vasco", "alias": "María José"},
    {"real": "Johana Osorio Bedoya", "alias": "Johana Sanchez"},
    {"real": "Juan Esteban Acevedo Garces", "alias": "Juan Esteban"},
    {"real": "Juan Sebastian Serna Sepulveda", "alias": "Juan Sebastian"},
    {"real": "Julián Andrés Osorio Aristizabal", "alias": "Andrés Aristizábal"},
    {"real": "Karen Herrera Gonzalez", "alias": "Karen"},
    {"real": "Kelly Jhoana Salas Ibarguen", "alias": "Kelly Salas"},
    {"real": "Libia Paola Romero Cantillo", "alias": "Paola Romero"},
    {"real": "Linda Liceth Pérez Pineda", "alias": "Linda Pérez / Elena Pérez"},
    {"real": "Luis Alberto Lozano Ibarra", "alias": "Luis Lozano"},
    {"real": "Manuela villegas Giraldo", "alias": "Manuela Villegas"},
    {"real": "María Karolina Viana Cancio", "alias": "Karolina"},
    {"real": "Mateo Cano Hincapié", "alias": "Antonio de la villa"},
    {"real": "Omar David Barboza Carbonero", "alias": "Omar"},
    {"real": "Oscar José Llanos Mendinueta", "alias": "Oscar"},
    {"real": "Paula Andrea Guzman Jaramillo", "alias": "Paula"},
    {"real": "Rosa Elvira Agamez López", "alias": "Flor Lopez"},
    {"real": "Sara Gómez Bayona", "alias": "Sara Gómez"},
    {"real": "Stefany Vanegas Arbelaez", "alias": "Stefany"},
    {"real": "Tatiana Magreth Acevedo Marín", "alias": "Tatiana"},
    {"real": "Tomas Castaño Gómez", "alias": "Tomas"},
    {"real": "Viviana Pacheco Córdoba", "alias": "Viviana Gómez"},
    {"real": "Yarlen Biviana Son Cedeño", "alias": "Maria Rodriguez"},
    {"real": "Yarnedis Cecilia Urrutia Pérez", "alias": "Cecilia López"},
    {"real": "Yeismer Miranda Ramirez", "alias": "Leo Miranda"},
    {"real": "Yesica Paola Lopez Arango", "alias": "Yesica López"},
    {"real": "Yesly Marilyn Carrero Rivera", "alias": "Marilyn Carrero"},
]

def obtener_fecha_hora_colombia() -> datetime:
    """Retorna objeto datetime actual en Zona Horaria de Colombia."""
    return datetime.now(ZoneInfo("America/Bogota"))

def obtener_hora_colombia_str() -> str:
    """Retorna la fecha y hora actual formateada en hora de Colombia (America/Bogota)."""
    return obtener_fecha_hora_colombia().strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# BASE DE DATOS Y PERSISTENCIA
# ==========================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Tabla de orden actual de turnos con columna 'activo' (1 = Activo, 0 = Ausente)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS turnos_orden (
                posicion INTEGER PRIMARY KEY,
                nombre_real TEXT NOT NULL,
                alias TEXT NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        
        # Tabla de historial de saltos / registros de llamadas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historial_saltos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL UNIQUE,
                telefono TEXT NOT NULL UNIQUE,
                nombre_real TEXT NOT NULL,
                alias TEXT NOT NULL,
                fecha_hora TEXT NOT NULL
            )
            """
        )
        
        # Cargar usuarios por defecto si la tabla está vacía
        cursor.execute("SELECT COUNT(*) FROM turnos_orden")
        if cursor.fetchone()[0] == 0:
            for idx, user in enumerate(USUARIOS_INICIALES, start=1):
                cursor.execute(
                    "INSERT INTO turnos_orden (posicion, nombre_real, alias, activo) VALUES (?, ?, ?, 1)",
                    (idx, user["real"], user["alias"])
                )
        conn.commit()

def obtener_lista_turnos() -> list:
    """Devuelve la lista completa de turnos con su estado (Activo/Ausente)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT posicion, nombre_real, alias, activo FROM turnos_orden ORDER BY posicion ASC")
        rows = cursor.fetchall()
        return [{"posicion": r[0], "real": r[1], "alias": r[2], "activo": bool(r[3])} for r in rows]

def cambiar_estado_agente(posicion: int, activo: bool):
    """Cambia el estado de un agente entre Activo (1) y Ausente (0)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE turnos_orden SET activo = ? WHERE posicion = ?", (1 if activo else 0, posicion))
        conn.commit()

def actualizar_estados_segun_horario(df_horario: pd.DataFrame):
    """Evalúa el horario de Colombia y actualiza automáticamente qué agentes están activos."""
    now_col = obtener_fecha_hora_colombia()
    fecha_hoy_str = now_col.strftime("%Y-%m-%d")
    hora_actual = now_col.time()

    # Normalizar columnas y nombres
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

    # Mapeo de estado por agente
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

    turnos = obtener_lista_turnos()
    for t in turnos:
        nombre_norm = t["real"].replace('\xa0', ' ').strip().lower()
        if nombre_norm in agentes_activos:
            cambiar_estado_agente(t["posicion"], agentes_activos[nombre_norm])

def registrar_salto_turno(call_id: str, telefono: str, pin_ingresado: str) -> tuple[bool, str]:
    """Avanza el turno del primer agente ACTIVO en la fila previa validación de su PIN de seguridad."""
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

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM historial_saltos WHERE call_id = ?", (call_id_clean,))
        if cursor.fetchone()[0] > 0:
            return False, f"❌ El ID de llamada '{call_id_clean}' ya fue registrado previamente."

        cursor.execute("SELECT COUNT(*) FROM historial_saltos WHERE telefono = ?", (telefono_clean,))
        if cursor.fetchone()[0] > 0:
            return False, f"❌ El número de teléfono '{telefono_clean}' ya fue atendido previamente."

        cursor.execute("SELECT posicion, nombre_real, alias, activo FROM turnos_orden ORDER BY posicion ASC")
        turnos = cursor.fetchall()

        agente_atendiendo = None
        for t in turnos:
            if t[3] == 1:  # activo == 1
                agente_atendiendo = t
                break

        if not agente_atendiendo:
            return False, "❌ Todos los agentes están marcados como Ausentes en este momento."

        pos_atendiendo, nombre_real, alias, _ = agente_atendiendo

        # VALIDACIÓN DEL PIN SECRETO
        pins_secretos = st.secrets.get("pins", {})
        pin_correcto = str(pins_secretos.get(nombre_real, "")).strip()

        if not pin_correcto:
            return False, f"⚠️ No se ha configurado un PIN para **{nombre_real}** en los secretos del sistema."

        if pin_clean != pin_correcto:
            return False, f"🔒 **PIN incorrecto.** No puedes ceder o avanzar el turno de **{alias}**."

        cursor.execute(
            "INSERT INTO historial_saltos (call_id, telefono, nombre_real, alias, fecha_hora) VALUES (?, ?, ?, ?, ?)",
            (call_id_clean, telefono_clean, nombre_real, alias, now_col)
        )

        turnos_sin_atendiendo = [t for t in turnos if t[0] != pos_atendiendo]
        nuevos_turnos = turnos_sin_atendiendo + [agente_atendiendo]

        cursor.execute("DELETE FROM turnos_orden")
        for new_pos, t in enumerate(nuevos_turnos, start=1):
            cursor.execute(
                "INSERT INTO turnos_orden (posicion, nombre_real, alias, activo) VALUES (?, ?, ?, ?)",
                (new_pos, t[1], t[2], t[3])
            )

        conn.commit()
        return True, f"✅ ¡Turno completado por **{alias}** ({nombre_real})! ID: `{call_id_clean}` y Teléfono: `{telefono_clean}` registrados con éxito."

def obtener_historial_saltos() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT id AS 'ID Reg', call_id AS 'ID Llamada', telefono AS 'Teléfono', alias AS 'Alias', nombre_real AS 'Nombre Real', fecha_hora AS 'Fecha / Hora (Colombia)' FROM historial_saltos ORDER BY id DESC",
            conn,
        )
    return df

def vaciar_historial_llamadas():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historial_saltos")
        conn.commit()

def reiniciar_turnos_originales():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM turnos_orden")
        for idx, user in enumerate(USUARIOS_INICIALES, start=1):
            cursor.execute(
                "INSERT INTO turnos_orden (posicion, nombre_real, alias, activo) VALUES (?, ?, ?, 1)",
                (idx, user["real"], user["alias"])
            )
        conn.commit()

def reorganizar_turnos_al_azar():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT posicion, nombre_real, alias, activo FROM turnos_orden")
        turnos = cursor.fetchall()
        
        random.shuffle(turnos)
        
        cursor.execute("DELETE FROM turnos_orden")
        for idx, t in enumerate(turnos, start=1):
            cursor.execute(
                "INSERT INTO turnos_orden (posicion, nombre_real, alias, activo) VALUES (?, ?, ?, ?)",
                (idx, t[1], t[2], t[3])
            )
        conn.commit()

init_db()

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

    if "df_horario_cargado" in st.session_state and st.session_state.get("usar_horario_auto", True):
        actualizar_estados_segun_horario(st.session_state.df_horario_cargado)

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
        st.error("⚠️ Todos los agentes se encuentran marcados como Ausentes. Contacta al Administrador.")

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

                st.session_state.df_horario_cargado = df_excel
                st.success("✅ Archivo de horarios cargado exitosamente.")
                with st.expander("Ver Vista Previa del Horario Cargado"):
                    st.dataframe(df_excel.head(10), use_container_width=True)
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")

        st.markdown("---")
        st.subheader("⚙️ Modo de Activación de Agentes")
        
        modo_auto = st.toggle(
            "Usar Activación Automática por Horario (Hora Colombia)",
            value=st.session_state.get("usar_horario_auto", True),
            key="usar_horario_auto"
        )

        if modo_auto:
            st.info("ℹ️ La activación automática según el Excel está **ACTIVADA**. El sistema cambiará el estado según la hora de Colombia.")
            if "df_horario_cargado" in st.session_state:
                if st.button("🔄 Sincronizar Horario Ahora"):
                    actualizar_estados_segun_horario(st.session_state.df_horario_cargado)
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