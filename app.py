import sqlite3
import random
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
    {"real": "Tatiana Magreth Acevedo", "alias": "Tatiana"},
    {"real": "Tomas Castaño", "alias": "Tomas"},
    {"real": "Viviana Pacheco", "alias": "Viviana Gómez"},
    {"real": "Yarlen Biviana Son", "alias": "Maria Rodriguez"},
    {"real": "Yarnedis Cecilia Urruta", "alias": "Cecilia López"},
    {"real": "Yeismer Miranda", "alias": "Leo Miranda"},
    {"real": "Yesica Paola Lopez", "alias": "Yesica López"},
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
        
        # Verificar si la columna 'activo' existe en turnos_orden
        cursor.execute("PRAGMA table_info(turnos_orden)")
        columns_turnos = [column[1] for column in cursor.fetchall()]
        
        if columns_turnos and "activo" not in columns_turnos:
            cursor.execute("DROP TABLE turnos_orden")
        
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
        
        # Verificar tabla historial_saltos
        cursor.execute("PRAGMA table_info(historial_saltos)")
        columns_hist = [column[1] for column in cursor.fetchall()]
        
        if columns_hist and "telefono" not in columns_hist:
            cursor.execute("DROP TABLE historial_saltos")
        
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
        
        # Cargar usuarios por defecto si la tabla de turnos está vacía
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

def registrar_salto_turno(call_id: str, telefono: str) -> tuple[bool, str]:
    """Avanza el turno del primer agente ACTIVO en la fila."""
    call_id_clean = call_id.strip()
    telefono_clean = telefono.strip()
    
    if not call_id_clean:
        return False, "⚠️ Debes ingresar un ID de llamada válido."
    if not telefono_clean:
        return False, "⚠️ Debes ingresar un número de teléfono válido."

    now_col = obtener_hora_colombia()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # 1. Validar si el ID de llamada ya fue utilizado
        cursor.execute("SELECT COUNT(*) FROM historial_saltos WHERE call_id = ?", (call_id_clean,))
        if cursor.fetchone()[0] > 0:
            return False, f"❌ El ID de llamada '{call_id_clean}' ya fue registrado previamente."

        # 2. Validar si el Teléfono ya fue utilizado
        cursor.execute("SELECT COUNT(*) FROM historial_saltos WHERE telefono = ?", (telefono_clean,))
        if cursor.fetchone()[0] > 0:
            return False, f"❌ El número de teléfono '{telefono_clean}' ya fue atendido previamente."

        # 3. Obtener todos los turnos
        cursor.execute("SELECT posicion, nombre_real, alias, activo FROM turnos_orden ORDER BY posicion ASC")
        turnos = cursor.fetchall()

        # Buscar el primer agente que esté ACTIVO
        agente_atendiendo = None
        for t in turnos:
            if t[3] == 1:  # activo == 1
                agente_atendiendo = t
                break

        if not agente_atendiendo:
            return False, "❌ Todos los agentes están marcados como Ausentes en este momento."

        pos_atendiendo, nombre_real, alias, _ = agente_atendiendo

        # 4. Guardar en el historial de registros
        cursor.execute(
            "INSERT INTO historial_saltos (call_id, telefono, nombre_real, alias, fecha_hora) VALUES (?, ?, ?, ?, ?)",
            (call_id_clean, telefono_clean, nombre_real, alias, now_col)
        )

        # 5. Mover al agente que atendió al final de la fila de posiciones
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
    """Borra todos los registros del historial de llamadas."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historial_saltos")
        conn.commit()

def reiniciar_turnos_originales():
    """Restablece los turnos a su orden estático original y todos activos."""
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
    """Mezcla la fila de turnos al azar conservando los estados de actividad."""
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
    st.caption("Ingresa el ID de la llamada y el Teléfono para completar tu turno y ceder el lugar al siguiente agente.")

    turnos_actuales = obtener_lista_turnos()

    # Identificar al primer agente ACTIVO
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
                    
                submit_salto = st.form_submit_button("Avanzar Turno ➡️", use_container_width=True, type="primary")

            if submit_salto:
                exito, mensaje = registrar_salto_turno(call_id_input, telefono_input)
                if exito:
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error(mensaje)
    else:
        st.error("⚠️ Todos los agentes se encuentran marcados como Ausentes. Contacta al Administrador.")

    st.markdown("---")
    
    # Visualización de la Fila Completa de Turnos con etiqueta de estado
    st.subheader("📋 Fila Actual de Posiciones")
    
    tabla_display = []
    for t in turnos_actuales:
        tabla_display.append({
            "Posición": t["posicion"],
            "Estado": "🟢 Activo" if t["activo"] else "🔴 Ausente",
            "Nombre Real": t["real"],
            "Alias / Nombre en Sistema": t["alias"]
        })
    
    df_turnos = pd.DataFrame(tabla_display)
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

        st.subheader("👥 Control de Ausencias (Activar / Desactivar Agentes)")
        st.caption("Desactiva un agente cuando esté en descanso, reunión o ausente. El sistema lo saltará automáticamente sin alterar la fila.")

        turnos_admin = obtener_lista_turnos()
        
        # Grid para gestión interactiva de ausencias
        with st.expander("Ver y Gestionar Lista de Ausencias", expanded=True):
            for t in turnos_admin:
                col_name, col_status = st.columns([3, 1])
                with col_name:
                    st.write(f"#{t['posicion']} - **{t['alias']}** ({t['real']})")
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
                    file_name=f"reporte_saltos_turnos_{datetime.now(ZoneInfo('America/Bogota')).strftime('%Y%m%d_%H%M')}.csv",
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