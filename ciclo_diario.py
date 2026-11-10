"""
Ciclo diario de estados del turnero (hora Colombia):
- 00:00 -> todos los asesores quedan INACTIVOS.
- 03:00 -> todos los asesores quedan ACTIVOS (activación automática).

Lo usan la app (respaldo: lo aplica la primera carga si aún no se hizo) y la tarea programada de GitHub
(.github/workflows/ciclo_diario.yml), que lo ejecuta aunque nadie abra la app:
    python ciclo_diario.py                          # aplica lo que corresponda ahora
    python ciclo_diario.py --ahora "2026-11-10 03:00"  # prueba con otra hora
"""
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Bogota")
HORA_ACTIVACION = 3          # 03:00 hora Colombia
ARCHIVO = "turnos_orden.json"


def aplicar_ciclo_diario(data: dict, ahora: datetime) -> list:
    """
    Aplica (una sola vez por día) el reset de las 00:00 y la activación de las 03:00 sobre `data`.
    Devuelve las acciones hechas: [], ["reset"], ["activacion"], ["reset", "activacion"] o ["inicializar"].
    La activación solo enciende a quien está inactivo: si un admin ya activó a alguien antes de las 03:00,
    conserva su hora de activación; y si después de las 03:00 un admin inactiva a alguien, no se reactiva.
    """
    hoy = ahora.strftime("%Y-%m-%d")
    marca = ahora.strftime("%Y-%m-%d %H:%M:%S")
    turnos = data.get("turnos", [])
    cambios = data.setdefault("cambios_estado", [])
    acciones = []

    if (data.get("ultimo_reset_diario") or "") < hoy:
        for t in turnos:
            t["activo"] = False
        data["ultimo_reset_diario"] = hoy
        cambios.insert(0, {
            "fecha_hora": marca, "tipo": "RESET_DIARIO", "nombre_real": "TODOS", "alias": "TODOS",
            "posicion_previa": "", "motivo": "Reset automático 00:00 (hora Colombia)", "registrado_por": "Sistema",
        })
        acciones.append("reset")

    if ahora.hour >= HORA_ACTIVACION and (data.get("ultima_activacion_automatica") or "") < hoy:
        if "ultima_activacion_automatica" not in data and not acciones:
            # Primera vez con la activación automática y el día ya está en curso: no se toca a nadie hoy,
            # la activación empieza mañana a las 03:00.
            data["ultima_activacion_automatica"] = hoy
            return ["inicializar"]
        for t in turnos:
            if not t.get("activo", True):
                t["activo"] = True
                cambios.insert(0, {
                    "fecha_hora": marca, "tipo": "REACTIVADO", "nombre_real": t["real"], "alias": t.get("alias", ""),
                    "posicion_previa": t.get("posicion", ""),
                    "motivo": f"Activación automática {HORA_ACTIVACION:02d}:00 (hora Colombia)",
                    "registrado_por": "Sistema",
                })
        data["ultima_activacion_automatica"] = hoy
        acciones.append("activacion")
    return acciones


def main(argv: list) -> int:
    ahora = datetime.now(TZ)
    if "--ahora" in argv:
        ahora = datetime.strptime(argv[argv.index("--ahora") + 1], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    with open(ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)
    acciones = aplicar_ciclo_diario(data, ahora)
    if acciones:
        with open(ARCHIVO, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))  # mismo formato que guarda la app
    print(f"{ahora:%Y-%m-%d %H:%M} -> {', '.join(acciones) or 'nada que hacer'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
