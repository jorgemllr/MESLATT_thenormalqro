import hashlib
import os
import openai
import qrcode
import io
import base64
import json
import re  # noqa: F401
from flask import Flask, request, jsonify, render_template, url_for
import sqlite3
import mysql.connector
from datetime import datetime
from PIL import Image
import pymysql
import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Clave de API de OpenAI
openai.api_key = "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"

# Variables globales para el historial de conversación y el ID de sesión
conversation_history_2 = []
session_id = None

# Conexión a la base de datos unificada
def conectar_db():
    return mysql.connector.connect(
        host="roundhouse.proxy.rlwy.net",
        user="root",
        password="PftmussYrgKSEkMxNpktZlPpoVICGEDv",
        database="meslatt_data",
        port=50455
    )

# Función para generar el hash único
def generar_hash(nombre, id):
    """
    Genera un hash único basado en el nombre del usuario, su ID y una sal aleatoria.
    
    Args:
        nombre_usuario (str): El nombre del usuario.
        id_usuario (int): El ID del usuario.
    
    Returns:
        str: El hash único generado en formato hexadecimal.
    """
    # Agrega una sal aleatoria de 16 bytes para mayor seguridad
    salt = os.urandom(16)

    # Crea el mensaje a hashear combinando el nombre del usuario, ID y la sal
    mensaje = f"{nombre}{id}".encode('utf-8') + salt

    # Genera el hash usando el algoritmo SHA-256
    hash_obj = hashlib.sha256(mensaje)
    
    # Convierte el hash en una cadena hexadecimal
    hash_hex = hash_obj.hexdigest()
    
    return hash_hex

# Iniciar una nueva sesión y crear un nuevo session_id
def iniciar_nueva_sesion():
    global session_id
    db_connection = conectar_db()
    cursor = db_connection.cursor()

    # Insertar una nueva fila para el session_id actual
    query = "INSERT INTO conversation_history_2 (conversation) VALUES (%s)"
    cursor.execute(query, ("",))  # Crear fila vacía para la sesión
    db_connection.commit()

    # Obtener el session_id recién creado
    session_id = cursor.lastrowid

    cursor.close()
    db_connection.close()

# Función para actualizar el historial en la base de datos del chatbot y sincronizar con reservations_db
def guardar_historial_db():
    db_connection = conectar_db()
    cursor = db_connection.cursor()

    # Concatenar todo el historial de interacciones (sin el contexto inicial de Data.txt)
    historial_texto = "\n".join([f"{entry['role']}: {entry['content']}" for entry in conversation_history_2 if entry['role'] != 'system'])
    
    # Actualizar la fila con el session_id actual con el historial completo
    query = "UPDATE conversation_history_2 SET conversation = %s WHERE session_id = %s"
    cursor.execute(query, (historial_texto, session_id))
    db_connection.commit()

    cursor.close()
    db_connection.close()

    # Llamar a actualizar_reservacion para sincronizar los datos en reservations_db
    actualizar_reservacion(session_id)

# Cargar contexto desde un archivo
def load_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# Generar respuesta del chatbot usando OpenAI API
def chatbot_response(prompt, context):
    if len(conversation_history_2) == 0:
        conversation_history_2.append({"role": "system", "content": context})

    conversation_history_2.append({"role": "user", "content": prompt})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=conversation_history_2
    )

    assistant_response = response['choices'][0]['message']['content']
    conversation_history_2.append({"role": "assistant", "content": assistant_response})

    guardar_historial_db()  # Guardar el historial en la base de datos y sincronizar reservations_db

    return assistant_response

# Función para actualizar automáticamente la base de datos de reservaciones
def actualizar_reservacion(session_id): 
    chatbot_conn = conectar_db()
    cursor = chatbot_conn.cursor()
    
    cursor.execute("SELECT conversation FROM conversation_history_2 WHERE session_id = %s", (session_id,))
    texto_reservacion = " ".join([fila[0] for fila in cursor.fetchall()])
    
    cursor.close()
    chatbot_conn.close()

    datos_reservacion = interpretar_reservacion(texto_reservacion)
    
    if datos_reservacion and campos_obligatorios_completos(datos_reservacion):
        hash_reservacion = generar_hash(datos_reservacion['nombre'], session_id)
        
        # Verificar si la reservación ya existe
        db_connection = conectar_db()
        cursor = db_connection.cursor()
        cursor.execute("SELECT id FROM reservations_2 WHERE id = %s", (session_id,))
        existe_reservacion = cursor.fetchone()
        cursor.close()
        db_connection.close()

        # Solo proceder si la reservación no existe
        if not existe_reservacion:
            sql_generado = generar_sql(datos_reservacion, hash_reservacion)
            if sql_generado and ejecutar_sql_en_reservations(sql_generado):
                enlace_invitacion = f"https://www.meslatt.com/thenormalqro/tarjeta/{hash_reservacion}"
                ruta_imagen = url_for('static', filename='images/Imagen.jpg')
                
                # Obtener el nombre del usuario
                nombre_usuario = datos_reservacion['nombre']  # Asegúrate de que este campo contiene el nombre

                # Construir el mensaje de invitación personalizado
                mensaje_invitacion = f"""
                <div style="display: flex; flex-direction: column; align-items: center; text-align: center; 
                border: 5px solid #c70000; padding: 10px; border-radius: 5px; max-width: 300px; margin: auto;">
                    <a href="{enlace_invitacion}" target="_blank" style="text-decoration: none;">
                        <img src="{ruta_imagen}" alt="Reservación" style="width: 200px; margin-bottom: 10px;">
                    </a>
                    <p style="margin: 0; font-size: 14px; color: #fff;">
                        Tu reservación está lista, {nombre_usuario}, <a href="{enlace_invitacion}" target="_blank" style="color:#c70000; font-weight:bold; text-decoration:underline;">haz clic aquí</a> para verla.
                    </p>
                </div>
                """
                conversation_history_2.append({"role": "assistant", "content": mensaje_invitacion})
                guardar_historial_db()

# Interpretar el texto de reservación usando OpenAI
def interpretar_reservacion(texto):
    fecha_actual = datetime.now()
    fecha_str = fecha_actual.strftime('%Y-%m-%d')
    hora_actual = fecha_actual.strftime('%H:%M')

    prompt = f"""
    Eres un asistente que extrae datos de reservaciones. 
    Te doy los datos de la fecha actual para que puedas interpretar en qué semana estamos, por si el usuario solo menciona un día y hora sin especificar la fecha exacta.
    Asume que cualquier hora mencionada en el texto es en formato PM.
    La fecha y hora actual es {fecha_str} {hora_actual}. 
    Si el usuario menciona un día de la semana, interpreta ese día en función de la fecha actual. Por ejemplo, si el usuario menciona 'próximo sábado', interpreta esa fecha en relación con el día de hoy.
    Extrae la siguiente información de la siguiente reservación en lenguaje natural: {texto}.
    El nombre debe incluir nombre y apellido. Si el usuario no proporciona ambos, no continúes con el flujo hasta obtenerlos.
    Devuelve los datos como un objetaso JSON con las claves: nombre, usuario_instagram, telefono_contacto, fecha_reservacion, 
    numero_personas, mesa, consumo_minimo, motivo, notas, estado. 
    Asegúrate de que la fecha de la reservación esté en formato SQL: YYYY-MM-DD HH:MM.
    Si el usuario no proporciona toda la información obligatoria (nombre, fecha_reservacion, numero_personas, consumo_minimo), responde solo con un JSON vacío: {{}}.
    Sin embargo, aunque el usuario proporcione todos los datos obligatorios, no generes el JSON hasta obtener respuestas para todos los campos, incluidos los opcionales (usuario_instagram, telefono_contacto, mesa, motivo, notas, estado).
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Eres un asistente que extrae datos de reservaciones."},
                  {"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.7
    )

    texto_respuesta = response['choices'][0]['message']['content'].strip()

    try:
        datos = json.loads(texto_respuesta)
    except json.JSONDecodeError:
        print("Error al procesar la respuesta de la API")
        return None

    return datos

# Verificar campos obligatorios
def campos_obligatorios_completos(datos):
    campos_requeridos = ['nombre', 'fecha_reservacion', 'numero_personas', 'consumo_minimo']
    for campo in campos_requeridos:
        if not datos.get(campo):
            print(f"Error: El campo obligatorio '{campo}' está vacío o falta.")
            return False
    return True

# Generar SQL para insertar en reservations_db
def generar_sql(datos, hash_reservacion):
    if not datos:
        return None
    
    # Asignar valores vacíos o NULL si no están presentes
    usuario_instagram = datos.get('usuario_instagram', '')
    telefono_contacto = datos.get('telefono_contacto', '')
    mesa = datos.get('mesa', '')
    motivo = datos.get('motivo', '')
    notas = datos.get('notas', '')
    estado = 'Pendiente'  # Siempre 'Pendiente' para el estado
    
    sql = f"INSERT INTO reservations_2 (id, nombre, usuario_instagram, telefono_contacto, fecha_reservacion, numero_personas, mesa, consumo_minimo, motivo, notas, estado, reservation_hash) " \
          f"VALUES ({session_id}, '{datos['nombre']}', '{usuario_instagram}', '{telefono_contacto}', '{datos['fecha_reservacion']}', " \
          f"{datos['numero_personas']}, '{mesa}', {datos['consumo_minimo']}, '{motivo}', '{notas}', " \
          f"'{estado}', '{hash_reservacion}')"
    
    return sql

# Ejecutar SQL en reservations_db
def ejecutar_sql_en_reservations(sql):
    db_connection = conectar_db()
    cursor = db_connection.cursor()
    try:
        cursor.execute(sql)
        db_connection.commit()
        print("Consulta SQL ejecutada y datos insertados en la base de datos con éxito.")
        return True
    except mysql.connector.Error as err:
        print(f"Error al insertar los datos: {err}")
        return False
    finally:
        cursor.close()
        db_connection.close()

def transfer_conversations():
    # Conexión a la base de datos
    connection = pymysql.connect(
        host="roundhouse.proxy.rlwy.net",
        user="root",
        password="PftmussYrgKSEkMxNpktZlPpoVICGEDv",
        database="meslatt_data",
        port=50455
    )

    cursor = connection.cursor()
    try:
        # Copiar datos a la tabla global
        cursor.execute("""
            INSERT INTO global_conversation_history_2 (conversation)
            SELECT conversation
            FROM conversation_history_2
            ORDER BY session_id;
        """)
        # Eliminar los datos de la tabla original
        cursor.execute("DELETE FROM conversation_history_2;")
        connection.commit()
    except Exception as e:
        print(f"Error al transferir datos: {e}")
    finally:
        cursor.close()
        connection.close()

# Configurar el programador para ejecutar la tarea cada 10 dias
scheduler = BackgroundScheduler()
scheduler.add_job(func=transfer_conversations, trigger="interval", hours=240)
scheduler.start()

# Configuración del logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Función para transferir reservaciones con estado "confirmado"
def transfer_confirmed_reservations():
    logging.info("Iniciando transferencia de reservaciones confirmadas...")
    connection = pymysql.connect(
        host="roundhouse.proxy.rlwy.net",
        user="root",
        password="PftmussYrgKSEkMxNpktZlPpoVICGEDv",
        database="meslatt_data",
        port=50455
    )

    cursor = connection.cursor()

    try:
        # Seleccionar reservaciones confirmadas ordenadas por fecha_creacion
        cursor.execute("""
            SELECT * FROM reservations_2
            WHERE estado = 'Confirmado'
            ORDER BY fecha_creacion ASC
        """)
        confirmed_reservations = cursor.fetchall()

        # Insertar en global_reservations_2 y eliminar de reservations_2
        for reservation in confirmed_reservations:
            cursor.execute("""
                INSERT INTO global_reservations_2 (
                    nombre, usuario_instagram, telefono_contacto, fecha_creacion,
                    fecha_reservacion, numero_personas, mesa, consumo_minimo,
                    motivo, notas, estado, reservation_hash, invitacion_enviada
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, reservation[1:])  # Excluir el campo id de la inserción
            cursor.execute("DELETE FROM reservations_2 WHERE id = %s", (reservation[0],))

        connection.commit()
        logging.info("Transferencia de reservaciones confirmadas completada.")
    except Exception as e:
        logging.error(f"Error durante la transferencia de confirmados: {e}")
    finally:
        cursor.close()
        connection.close()

# Función para transferir reservaciones con estado "pendiente"
def transfer_pending_reservations():
    logging.info("Iniciando transferencia de reservaciones pendientes...")
    connection = pymysql.connect(
        host="roundhouse.proxy.rlwy.net",
        user="root",
        password="PftmussYrgKSEkMxNpktZlPpoVICGEDv",
        database="meslatt_data",
        port=50455
    )
    cursor = connection.cursor()

    try:
        # Seleccionar reservaciones pendientes ordenadas por fecha_creacion
        cursor.execute("""
            SELECT * FROM reservations_2
            WHERE estado = 'Pendiente'
            ORDER BY fecha_creacion ASC
        """)
        pending_reservations = cursor.fetchall()

        # Insertar en global_reservations_2 y eliminar de reservations_2
        for reservation in pending_reservations:
            cursor.execute("""
                INSERT INTO global_reservations_2 (
                    nombre, usuario_instagram, telefono_contacto, fecha_creacion,
                    fecha_reservacion, numero_personas, mesa, consumo_minimo,
                    motivo, notas, estado, reservation_hash, invitacion_enviada
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, reservation[1:])  # Excluir el campo id de la inserción
            cursor.execute("DELETE FROM reservations_2 WHERE id = %s", (reservation[0],))

        connection.commit()
        logging.info("Transferencia de reservaciones pendientes completada.")
    except Exception as e:
        logging.error(f"Error durante la transferencia de pendientes: {e}")
    finally:
        cursor.close()
        connection.close()

# Configurar el programador
scheduler = BackgroundScheduler()
scheduler.add_job(func=transfer_confirmed_reservations, trigger="interval", hours=3)  # Cada 3 horas
scheduler.add_job(func=transfer_pending_reservations, trigger="interval", hours=18)    # Cada 18 horas
scheduler.start()
logging.info("Programador iniciado. Las tareas se ejecutarán según lo programado.")

# No es necesario el bucle infinito. El programador mantiene el script en ejecución.

# Configuración del logger
def configure_logging():
    log_file = "app_logs.log"
    max_log_size = 100 * 1024  # 100 KB
    backup_count = 5  # Mantener hasta 5 archivos de respaldo

    # Crear un RotatingFileHandler
    handler = RotatingFileHandler(log_file, maxBytes=max_log_size, backupCount=backup_count)
    handler.setLevel(logging.INFO)  # Nivel de los logs (INFO, DEBUG, etc.)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Agregar el handler al logger
    app.logger.addHandler(handler)

# Llamar la función de configuración antes de que arranque la aplicación
configure_logging()

@app.route('/thenormalqro/logs')
def index():
    app.logger.info("Página principal cargada.")
    return "Hola, Flask con logs rotados!"

# Rutas de Flask
@app.route('/thenormalqro/chatbot')
def home():
    iniciar_nueva_sesion()
    conversation_history_2.clear()  # Limpiar el historial de la sesión anterior
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_input = request.form.get('message')
    context = load_data('Data.txt')

    # Si ya se ha enviado la invitación, verifica si contiene un enlace HTML
    if conversation_history_2 and "href=" in conversation_history_2[-1]["content"]:
        # Envía el mensaje existente interpretado como HTML
        return jsonify({'bot_response': conversation_history_2[-1]["content"], 'html_response': True})

    # Si no, generar la respuesta normal del chatbot
    response = chatbot_response(user_input, context)
    return jsonify({'bot_response': response, 'html_response': True})

@app.route('/api/e5b0928f8e8028fe7581a26a905832293f7f2320afc4f6ef5690c67d9ec68a28')
def api_reservations_2():
    db_connection = conectar_db()
    cursor = db_connection.cursor()
    cursor.execute("SELECT * FROM reservations_2 ORDER BY fecha_reservacion DESC")
    reservations = cursor.fetchall()
    cursor.close()
    db_connection.close()

    reservations_data = [
        {
            "id": row[0],
            "name": row[1],
            "instagram_username": row[2] if row[2] else '',
            "contact_phone": row[3] if row[3] else '',
            "creation_date": row[4],
            "reservation_date": row[5],
            "number_of_people": row[6],
            "table": row[7] if row[7] else '',
            "minimum_spend": row[8],
            "reservation_reason": row[9] if row[9] else '',
            "special_notes": row[10] if row[10] else '',
            "status": row[11] if row[11] else 'Pendiente'  # Si no tiene estado, poner 'Pendiente'
        } for row in reservations
    ]
    
    return jsonify(reservations_data)

@app.route('/api/update-status', methods=['POST'])
def update_status():
    data = request.get_json()
    reservation_id = data.get('id')
    new_status = data.get('status')

    if not reservation_id or not new_status:
        return jsonify({"error": "Datos inválidos"}), 400

    db_connection = conectar_db()
    cursor = db_connection.cursor()

    try:
        query = "UPDATE reservations_2 SET estado = %s WHERE id = %s"
        cursor.execute(query, (new_status, reservation_id))
        db_connection.commit()
        return jsonify({"message": "Estado actualizado con éxito"})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        db_connection.close()

@app.route('/thenormalqro/e5b0928f8e8028fe7581a26a905832293f7f2320afc4f6ef5690c67d9ec68a28')
def show_reservations():
    return render_template('reservations.html')

@app.route('/thenormalqro/tarjeta/<hash>')
def invitacion(hash):
    try:
        # Conexión a la base de datos
        db = mysql.connector.connect(
            host="roundhouse.proxy.rlwy.net",
            user="root",
            password="PftmussYrgKSEkMxNpktZlPpoVICGEDv",
            database="meslatt_data",
            port=50455
        )
        cursor = db.cursor()
        
        # Consulta para obtener el ID, hash y nombre
        cursor.execute("SELECT id, reservation_hash, nombre FROM reservations_2 WHERE reservation_hash = %s", (hash,))
        result = cursor.fetchone()
        
        if result:
            id, reservation_hash, nombre = result

            # Crear el objeto QRCode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(reservation_hash)
            qr.make(fit=True)

            # Crear la imagen con el color hexadecimal personalizado
            img = qr.make_image(fill_color='#c70000', back_color='black')  # Color personalizado #c70000
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        else:
            reservation_hash = "Hash no encontrado"
            nombre = "User name"
            qr_base64 = None

        # Asegurarse de que el ID tenga siempre 4 cifras (zero-fill)
        formatted_id = str(id).zfill(4)

        # Renderizar la plantilla con el ID, hash, QR en base64 y nombre
        return render_template(
            'Einladung.html',
            id=formatted_id,  # Pasar el ID con 4 cifras para mostrar
            reservation_hash=reservation_hash,
            qr_base64=qr_base64,
            nombre=nombre
        )
    
    except mysql.connector.Error as err:
        print(f"Error al conectar con la base de datos: {err}")
        return "Error al procesar la invitación.", 500
    
    finally:
        if 'db' in locals() and db.is_connected():
            cursor.close()
            db.close()

@app.route('/thenormalqro/menu')
def menu():
    return render_template('Menu.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)