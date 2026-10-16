import sqlite3
from datetime import datetime
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
# DATOS INICIALES DE USUARIOS
# ==========================================
USUARIOS_INICIALES = [
    {"real": "Alisson Correa", "alias": "Alisson"},
    {"real": "Ana María Sánchez", "alias": "Maria Sanchez"},
    {"real": "Andrea Londoño", "alias": "Andrea Valverde"},
    {"real": "Angie Valeria Quirama", "alias": "Valeria Hernandez"},
    {"real": "Angie Vanessa García", "alias": "Maria Antonia García"},
    {"real": "Brayan Andrey Bustamante", "alias": "Marcos Garcia"},
    {"real": "Carlos Alberto Herrera", "alias": "Carlos Herrera / Alberto Fernandez"},
    {"real": "Claudia Marcela Manco", "alias": "Marcela"},
    {"real": "Cristian David Acosta", "alias": "Manuel Vasquez"},
    {"real": "Dayana Botero", "alias": "Isabel Botero"},
    {"real": "Edisson Andrés Díaz", "alias": "Andres"},
    {"real": "Evelin Acevedo", "alias": "Gabriela"},
    {"real": "Gustavo Adolfo Barrientos", "alias": "Gustavo"},
    {"real": "Iris Sabiana Cano", "alias": "Maria Cano"},
    {"real": "Janis Henao", "alias": "María José"},
    {"real": "Johana Osorio", "alias": "Johana Sanchez"},
    {"real": "Juan Esteban Acevedo", "alias": "Juan Esteban"},
    {"real": "Juan Sebastián Serna", "alias": "Juan Sebastian"},
    {"real": "Julián Andrés Osorio", "alias": "Andrés Aristizábal"},
    {"real": "Karen Herrera", "alias": "Karen"},
    {"real": "Kelly Jhoana Salas", "alias": "Kelly Salas"},
    {"real": "Libia Paola Romero", "alias": "Paola Romero"},
    {"real": "Linda Liceth Pérez", "alias": "Linda Pérez / Elena Pérez"},
    {"real": "Luis Alberto Lozano", "alias": "Luis Lozano"},
    {"real": "Manuela Villegas", "alias": "Manuela Villegas"},
    {"real": "María Karolina Viana", "alias": "Karolina"},
    {"real": "Mateo Cano", "alias": "Antonio de la villa"},
    {"real": "Omar David Barboza", "alias": "Omar"},
    {"real": "Oscar Jose Llanos", "alias": "Oscar"},
    {"real": "Paula Andrea Guzman", "alias": "Paula"},
    {"real": "Rosa Agamez", "alias": "Flor Lopez"},
    {"real": "Sara Gómez", "alias": "Sara Gómez"},
    {"real": "Stefany Vanegas", "alias": "Stefany Vanegas"},
    {"real": "Tatiana Magreth Acevedo", "alias": "Tatiana"},
    {"real": "Tomas Castaño", "alias": "Tomas"},
    {"real": "Viviana Pacheco", "alias": "Viviana Gómez"},
    {"real": "Yarlen Biviana Son", "alias": "Maria Rodriguez"},
    {"real": "Yarnedis Cecilia Urruta", "alias": "Cecilia López"},
    {"real": "Yeismer Miranda", "alias": "Leo Miranda"},
    {"real": "Yesica Paola Lopez", "alias": "Yesica López"},
    {"real": "Michelle Dayanna Villacrez", "alias": "Michelle"},
    {"real": "Maria Fernanda Ramirez", "alias": "Maria Fernanda"},
    {"real": "Yesly Marilyn Carrero", "alias": "Marilyn Carrero"},
]

def obtener_hora_colombia() -> str:
    """Retorna la fecha y hora actual formateada en hora de Colombia (America/Bogota)."""
    return datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# BASE DE DATOS Y PERSISTENCIA
# ==========================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Tabla de orden actual de turnos
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS turnos_orden (
                posicion INTEGER PRIMARY KEY,
                nombre_real TEXT NOT NULL,
                alias TEXT NOT NULL
            )
            """
        )
        
        # Tabla de historial de saltos / registros de llamadas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historial_saltos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL UNIQUE,
                nombre_real TEXT NOT NULL,
                alias TEXT NOT NULL,
                fecha_hora TEXT NOT NULL
            )
            """
        )
        
        # Cargar usuarios por defecto si la tabla de turnos está vacía
        cursor.execute("SELECT COUNT(*) FROM turnos_orden")
        if cursor.fetchone()[0] == 0:
            for idx, user in enumerate(USUARIOS_INICIALES, start=1):
                cursor.execute(
                    "INSERT INTO turnos_orden (posicion, nombre_real, alias) VALUES (?, ?, ?)",
                    (idx, user["real"], user["alias"])
                )
        conn.commit()

def obtener_lista_turnos() -> list:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT posicion, nombre_real, alias FROM turnos_orden ORDER BY posicion ASC")
        rows = cursor.fetchall()
        return [{"posicion": r[0], "real": r[1], "alias": r[2]} for r in rows]

def registrar_salto_turno(call_id: str) -> tuple[bool, str]:
    """Avanza el turno si la ID de llamada es válida y no ha sido usada."""
    call_id_clean = call_id.strip()
    if not call_id_clean:
        return False, "⚠️ Debes ingresar un ID de llamada válido."

    now_col = obtener_hora_colombia()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # 1. Validar si la ID ya fue utilizada
        cursor.execute("SELECT COUNT(*) FROM historial_saltos WHERE call_id = ?", (call_id_clean,))
        if cursor.fetchone()[0] > 0:
            return False, f"❌ El ID de llamada '{call_id_clean}' ya fue utilizado previamente. Ingrese uno nuevo."

        # 2. Obtener la lista actual de turnos
        cursor.execute("SELECT posicion, nombre_real, alias FROM turnos_orden ORDER BY posicion ASC")
        turnos = cursor.fetchall()

        if not turnos:
            return False, "❌ No hay usuarios en la lista de turnos."

        # Usuario actual (Turno 1)
        primer_usuario = turnos[0]
        nombre_real = primer_usuario[1]
        alias = primer_usuario[2]

        # 3. Guardar en el historial de registros
        cursor.execute(
            "INSERT INTO historial_saltos (call_id, nombre_real, alias, fecha_hora) VALUES (?, ?, ?, ?)",
            (call_id_clean, nombre_real, alias, now_col)
        )

        # 4. Mover al usuario actual al final de la fila
        # Eliminamos el primer elemento y lo reinsertamos con nueva posición al final
        nuevos_turnos = turnos[1:] + [primer_usuario]

        cursor.execute("DELETE FROM turnos_orden")
        for new_pos, t in enumerate(nuevos_turnos, start=1):
            cursor.execute(
                "INSERT INTO turnos_orden (posicion, nombre_real, alias) VALUES (?, ?, ?)",
                (new_pos, t[1], t[2])
            )

        conn.commit()
        return True, f"✅ ¡Turno completado por **{alias}** ({nombre_real})! ID: `{call_id_clean}` guardado con éxito."

def obtener_historial_saltos() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT id AS 'ID Reg', call_id AS 'ID Llamada', alias AS 'Alias', nombre_real AS 'Nombre Real', fecha_hora AS 'Fecha / Hora (Colombia)' FROM historial_saltos ORDER BY id DESC",
            conn,
        )
    return df

def reiniciar_turnos_originales():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM turnos_orden")
        for idx, user in enumerate(USUARIOS_INICIALES, start=1):
            cursor.execute(
                "INSERT INTO turnos_orden (posicion, nombre_real, alias) VALUES (?, ?, ?)",
                (idx, user["real"], user["alias"])
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
    st.caption("Ingresa el ID de la llamada para completar tu turno y ceder el lugar al siguiente agente.")

    turnos_actuales = obtener_lista_turnos()

    if turnos_actuales:
        actual = turnos_actuales[0]
        
        # Tarjeta destacada del Turno Actual
        st.markdown("---")
        col_turn_1, col_turn_2 = st.columns([2, 3])

        with col_turn_1:
            st.metric(label="🎯 TURNO ACTUAL (#1)", value=actual["alias"])
            st.write(f"👤 **Nombre Real:** {actual['real']}")

        with col_turn_2:
            st.subheader("📞 Completar Turno Actual")
            with st.form("form_avanzar_turno", clear_on_submit=True):
                call_id_input = st.text_input("Ingresa el ID de la Llamada:", placeholder="Ej: CALL-9876543")
                submit_salto = st.form_submit_button("Avanzar Turno ➡️", use_container_width=True, type="primary")

            if submit_salto:
                exito, mensaje = registrar_salto_turno(call_id_input)
                if exito:
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error(mensaje)

        st.markdown("---")
        
        # Visualización de la Fila Completa de Turnos
        st.subheader("📋 Fila Actual de Posiciones")
        
        df_turnos = pd.DataFrame(turnos_actuales)
        df_turnos.columns = ["Posición", "Nombre Real", "Alias / Nombre en Sistema"]
        
        st.dataframe(df_turnos, use_container_width=True, hide_index=True)

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
            if admin_pass == st.secrets["passwords"]["admin_password"]:
                st.session_state.admin_logged = True
                st.success("✅ Acceso concedido.")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")

    else:
        if st.sidebar.button("Cerrar Sesión Admin", use_container_width=True):
            st.session_state.admin_logged = False
            st.rerun()

        st.subheader("📊 Historial de Registro de Llamadas y Saltos")
        df_historial = obtener_historial_saltos()

        if df_historial.empty:
            st.info("Aún no se han registrado saltos de turno.")
        else:
            st.dataframe(df_historial, use_container_width=True, hide_index=True)

            # Botón de Descarga en CSV
            csv_data = df_historial.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Descargar Reporte CSV (Hora Colombia)",
                data=csv_data,
                file_name=f"reporte_saltos_turnos_{datetime.now(ZoneInfo('America/Bogota')).strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )

        st.markdown("---")
        st.subheader("⚙️ Opciones de Reordenamiento de Fila")
        st.warning("⚠️ **Atención:** Esto reajustará el orden de la fila al estado original de la lista.")

        confirm_reset = st.checkbox("Confirmo que deseo reiniciar el orden de la fila de turnos.")
        if st.button("Restablecer Fila a Estado Inicial", disabled=not confirm_reset, type="primary"):
            reiniciar_turnos_originales()
            st.success("✅ Fila de turnos restablecida con éxito.")
            st.rerun()