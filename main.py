from web import iniciar_web
import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, time, timedelta

import pytz
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

EVENTS_FILE = "eventos.json"
UPDATE_INTERVAL_MINUTES = 60
TOKEN = os.getenv('TOKEN')
if TOKEN is None:
    raise ValueError("El token no está definido. Asegúrate de configurar la variable de entorno 'TOKEN'.")


# ---------------- UTILIDADES ---------------- #

def cargar_eventos():
    try:
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
eventos = cargar_eventos()

def guardar_eventos(eventos):
    with open(EVENTS_FILE, "w") as f:
        json.dump(eventos, f, indent=4)

def guardar_fijado(canal_id, mensaje_id):
    with open("fijado.json", "w") as f:
        json.dump({"canal_id": canal_id, "fijado_id": mensaje_id}, f)

def cargar_fijado():
    try:
        with open("fijado.json", "r") as f:
            datos = json.load(f)
            return datos.get("canal_id"), datos.get("fijado_id")
    except FileNotFoundError:
        return None, None

# Cargar canal y mensaje fijado tras definir funciones
canal_id, fijado_id = cargar_fijado()


def formatear_tiempo_restante(final_str):
    final = datetime.fromisoformat(final_str)
    ahora = datetime.now() - timedelta(hours=4)
    delta = final - ahora
    if delta.total_seconds() <= 0:
        return None

    dias = delta.days
    horas = delta.seconds // 3600
    return f"{dias} días, {horas} horas"
EMOJIS_JUEGOS = {
    "Genshin": "<:Genshin_Primogen:1376706371642200154>",
    "StarRail": "<:Item_Star_Rail_Special_Pass72:1376706370253881474>",
    "Zenless": "<:Zenless_Zone_Zero_logo:1376706362687357000>",
    "WuWa": "<:asterite_wuwa:1376706358597910568>",
    "Strinova": "<:Strinova_logo:1376706359843885176>",
    "Honkai": "<:Honkai:1376706361064165438>",
    "GirlsFrontline": "<:Gfl_nibba_what:1376706357021114468>"
}
def construir_mensaje(eventos):
    mensaje = "📅 **Próximos eventos**\n\n"
    for juego, lista in eventos.items():
        emoji = EMOJIS_JUEGOS.get(juego, "🎮")
        mensaje += f"{emoji} **{juego}**:\n"
        for evento in lista:
            tiempo = formatear_tiempo_restante(evento["fecha"])
            if tiempo:
                mensaje += f"• {evento['nombre']}: {tiempo}\n"
        mensaje += "\n"
    return mensaje.strip()


# ---------------- COMANDOS ---------------- #


@bot.command()
async def crear(ctx, juego: str, nombre: str, fecha: str, hora: str):
    """
    Crear un evento. Formato: !crear "Juego" "Nombre" YYYY-MM-DD HH:MM (UTC)
    """
    try:
        fecha_completa = f"{fecha} {hora}"
        fecha_obj = datetime.strptime(fecha_completa, "%Y-%m-%d %H:%M")
        eventos = cargar_eventos()

        if juego not in eventos:
            eventos[juego] = []

        eventos[juego].append({
            "nombre": nombre,
            "fecha": fecha_obj.isoformat()
        })

        guardar_eventos(eventos)
        await ctx.send(f"✅ Evento **{nombre}** creado para **{juego}**.")
        await actualizar_mensaje_eventos()  # ✅ Solo si todo fue bien
    except ValueError:
        await ctx.send("❌ Formato incorrecto. Usa: !crear Genshin Evento1 2025-06-01 18:00")




@bot.command()
async def mostrar(ctx):
    global canal_id, fijado_id
    eventos = cargar_eventos()

    # Eliminar vencidos
    for juego in list(eventos.keys()):
        eventos[juego] = [e for e in eventos[juego] if formatear_tiempo_restante(e["fecha"])]
        if not eventos[juego]:
            del eventos[juego]
    guardar_eventos(eventos)

    # Intentar borrar mensaje fijado anterior
    if canal_id and fijado_id:
        try:
            canal = bot.get_channel(canal_id)
            if canal is None:
                canal = await bot.fetch_channel(canal_id)
            mensaje_antiguo = await canal.fetch_message(fijado_id)
            await mensaje_antiguo.unpin()
            await mensaje_antiguo.delete()
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el mensaje anterior: {e}")

    # Enviar y fijar nuevo mensaje
    texto = construir_mensaje(eventos)
    mensaje = await ctx.send(texto)
    await mensaje.pin()

    # Guardar el nuevo ID
    canal_id = ctx.channel.id
    fijado_id = mensaje.id
    guardar_fijado(canal_id, fijado_id)

    await ctx.send("📌 Mensaje actualizado y fijado.")



@bot.command(name="eliminar")
async def eliminar(ctx, juego: str, *, nombre_evento: str):
    eventos = cargar_eventos()  # ✅ Cargar eventos aquí directamente
    if juego in eventos:
        eventos[juego] = [e for e in eventos[juego] if e['nombre'].lower() != nombre_evento.lower()]
        if not eventos[juego]:
            del eventos[juego]
        guardar_eventos(eventos)
        await ctx.send(f"✅ Evento **{nombre_evento}** eliminado de **{juego}**.")
        await actualizar_mensaje_eventos()
    else:
        await ctx.send(f"⚠️ No se encontró el juego **{juego}** con ese evento.")

@bot.command()
async def editar(ctx, juego: str, nombre_viejo: str, nombre_nuevo: str, fecha: str, hora: str):
    """
    Editar un evento existente. Formato:
    !editar "Juego" "NombreAnterior" "NombreNuevo" YYYY-MM-DD HH:MM
    """
    try:
        fecha_completa = f"{fecha} {hora}"
        fecha_obj = datetime.strptime(fecha_completa, "%Y-%m-%d %H:%M")
        eventos = cargar_eventos()

        if juego not in eventos:
            await ctx.send(f"⚠️ No hay eventos registrados para **{juego}**.")
            return

        encontrado = False
        for evento in eventos[juego]:
            if evento["nombre"].lower() == nombre_viejo.lower():
                evento["nombre"] = nombre_nuevo
                evento["fecha"] = fecha_obj.isoformat()
                encontrado = True
                break

        if not encontrado:
            await ctx.send(f"❌ No se encontró el evento **{nombre_viejo}** en **{juego}**.")
            return

        guardar_eventos(eventos)
        await ctx.send(f"✏️ Evento **{nombre_viejo}** actualizado a **{nombre_nuevo}** el {fecha} {hora}.")
        await actualizar_mensaje_eventos()  # ✅ Solo si la edición fue exitosa

    except ValueError:
        await ctx.send("❌ Formato incorrecto. Usa: !editar Genshin Viejo Nuevo 2025-06-01 18:00")




# ---------------- ACTUALIZACIÓN AUTOMÁTICA ---------------- #

@tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)
async def actualizar_mensaje():
    await bot.wait_until_ready()
    global canal_id, fijado_id
    if canal_id is None or fijado_id is None:
        return

    canal = bot.get_channel(canal_id)
    if canal is None:
        return

    try:
        mensaje = await canal.fetch_message(fijado_id)
        eventos = cargar_eventos()
        for juego in list(eventos.keys()):
            eventos[juego] = [e for e in eventos[juego] if formatear_tiempo_restante(e["fecha"])]
            if not eventos[juego]:
                del eventos[juego]

        guardar_eventos(eventos)
        nuevo_contenido = construir_mensaje(eventos)
        await mensaje.edit(content=nuevo_contenido)
    except Exception as e:
        print("Error actualizando mensaje:", e)



async def actualizar_mensaje_eventos():
    global canal_id, fijado_id
    if canal_id and fijado_id:
        eventos = cargar_eventos()
        # Eliminar eventos vencidos
        for juego in list(eventos.keys()):
            eventos[juego] = [e for e in eventos[juego] if formatear_tiempo_restante(e["fecha"])]
            if not eventos[juego]:
                del eventos[juego]
        guardar_eventos(eventos)

        canal = bot.get_channel(canal_id)
        if canal:
            try:
                mensaje = await canal.fetch_message(fijado_id)
                await mensaje.edit(content=construir_mensaje(eventos))
            except discord.NotFound:
                print("Mensaje fijado no encontrado.")


@tasks.loop(minutes=60)
async def actualizar_eventos():
    await bot.wait_until_ready()
    await actualizar_mensaje_eventos()

async def esperar_hora_exacta():
    """Espera hasta la próxima hora exacta en UTC-4 antes de iniciar el loop."""
    tz = pytz.timezone("Etc/GMT+4")  # UTC-4 (sí, Discord usa el signo invertido para 'Etc/')
    ahora = datetime.now(tz)
    siguiente_hora = (ahora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    espera = (siguiente_hora - ahora).total_seconds()
    print(f"⏳ Esperando {int(espera)} segundos hasta la próxima hora exacta (UTC-4)...")
    await asyncio.sleep(espera)
    actualizar_eventos.start()

@tasks.loop(hours=1)
async def actualizar_eventos_loop():
    await actualizar_mensaje_eventos()

@bot.event
async def on_ready():
    print(f"Bot iniciado como {bot.user}")

    if canal_id and fijado_id:
        canal = bot.get_channel(canal_id)
        if canal:
            try:
                mensaje = await canal.fetch_message(fijado_id)
                eventos_actualizados = cargar_eventos()

                # Eliminar eventos vencidos
                for juego in list(eventos_actualizados.keys()):
                    eventos_actualizados[juego] = [
                        e for e in eventos_actualizados[juego]
                        if formatear_tiempo_restante(e["fecha"])
                    ]
                    if not eventos_actualizados[juego]:
                        del eventos_actualizados[juego]
                guardar_eventos(eventos_actualizados)

                nuevo_texto = construir_mensaje(eventos_actualizados)
                await mensaje.edit(content=nuevo_texto)
                print("✅ Mensaje fijado actualizado automáticamente al iniciar.")
                await esperar_hora_exacta()
                actualizar_eventos_loop.start()
            except discord.NotFound:
                print("⚠️ El mensaje fijado guardado ya no existe.")
            except Exception as e:
                print(f"❌ Error al actualizar mensaje al iniciar: {e}")

        else:
            print("⚠️ Canal no encontrado.")
    else:
        print("ℹ️ No hay mensaje fijado previo guardado.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Faltan argumentos. Revisa el formato del comando.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando no reconocido. ¿Lo escribiste bien?")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argumentos inválidos. Verifica el formato.")
    elif isinstance(error, commands.CommandInvokeError):
        await ctx.send("❌ Ocurrió un error interno al ejecutar el comando.")
        # También puedes imprimir el error en consola para depuración:
        print(f"Error interno: {error}")
    else:
        await ctx.send("❌ Error desconocido. Revisa la sintaxis.")
        print(f"Error desconocido: {error}")

async def apagar_si_fuera_de_horario():
    tz = pytz.timezone("America/Santiago")
    ahora = datetime.now(tz)  # ✅ Correcto  # UTC-4
    hora_actual = ahora.time()
    
    inicio = time(hour=14, minute=00)  # 05:30
    fin = time(hour=2, minute=00)     # 02:00

    if inicio <= hora_actual or hora_actual < fin:
        print("🛑 Bot fuera del horario permitido. Cerrando...")
        await asyncio.sleep(2)
        os._exit(0)

async def main():
    iniciar_web()
    await apagar_si_fuera_de_horario()
    bot.run(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
