from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import re
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import plotly.io as pio


app = Flask(__name__)
app.secret_key = "clave_secreta"


# ---------------------------
# BASE DE DATOS Y HELPERS
# ---------------------------
def get_db_connection():
    conn = sqlite3.connect('sabor_himalaya.db')
    # Esto permite acceder a las columnas por su nombre (ej. usuario['nombre'])
    conn.row_factory = sqlite3.Row 
    return conn

MENU_PRECIO = 15.0
MENU_SLOTS = {
    "entrantes": 3,
    "principales": 3,
    "postres": 2,
}

def ensure_menu_schema():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Menu_Diario_Opcion (
            id_opcion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_menu INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            posicion INTEGER NOT NULL,
            id_plato INTEGER NOT NULL,
            FOREIGN KEY (id_menu) REFERENCES Menu_Diario(id_menu),
            FOREIGN KEY (id_plato) REFERENCES Plato(id_plato),
            UNIQUE (id_menu, tipo, posicion)
        )
    ''')
    conn.commit()
    conn.close()

def formato_plato(row):
    return {
        "id_plato": row["id_plato"],
        "nombre": row["nombre"],
        "descripcion": row["descripción"] if "descripción" in row.keys() else row["descripcion"],
        "precio": row["precio"],
        "categoria": row["categoria"],
        "activo_en_carta": row["activo_en_carta"]
    }

def formato_fecha_es(fecha_iso):
    try:
        return datetime.strptime(fecha_iso, "%Y-%m-%d").strftime("%d/%m/%y")
    except (TypeError, ValueError):
        return fecha_iso or ""

def es_categoria_menu_valida(tipo, categoria):
    if tipo == "entrantes":
        return categoria in ("Entrante", "Ensalada")
    if tipo == "postres":
        return categoria == "Postre"
    if tipo == "principales":
        return categoria not in ("Entrante", "Ensalada", "Postre", "Bebida")
    return False

def get_menu_dia(fecha=None):
    fecha = fecha or date.today().isoformat()
    conn = get_db_connection()
    menu = conn.execute(
        "SELECT * FROM Menu_Diario WHERE fecha = ?",
        (fecha,)
    ).fetchone()

    if not menu:
        conn.close()
        return None

    opciones = conn.execute('''
        SELECT mo.tipo, mo.posicion, p.id_plato, p.nombre
        FROM Menu_Diario_Opcion mo
        JOIN Plato p ON p.id_plato = mo.id_plato
        WHERE mo.id_menu = ?
        ORDER BY mo.tipo, mo.posicion
    ''', (menu["id_menu"],)).fetchall()
    bebidas = conn.execute('''
        SELECT MIN(id_plato) AS id_plato, nombre
        FROM Plato
        WHERE categoria = 'Bebida' AND activo_en_carta = 1
        GROUP BY nombre
        ORDER BY nombre
    ''').fetchall()
    conn.close()

    resultado = {
        "id_menu": menu["id_menu"],
        "fecha": menu["fecha"],
        "precio_menu": menu["precio_menu"] if "precio_menu" in menu.keys() else MENU_PRECIO,
        "entrantes": [],
        "principales": [],
        "postres": [],
        "bebidas": [],
    }

    for opcion in opciones:
        if opcion["tipo"] in resultado:
            resultado[opcion["tipo"]].append({
                "id_plato": opcion["id_plato"],
                "nombre": opcion["nombre"],
            })

    resultado["bebidas"] = [
        {"id_plato": bebida["id_plato"], "nombre": bebida["nombre"]}
        for bebida in bebidas
    ]

    if any(len(resultado[tipo]) != cantidad for tipo, cantidad in MENU_SLOTS.items()):
        return None

    return resultado

def get_menu_candidate_platos(platos):
    return {
        "entrantes": [p for p in platos if es_categoria_menu_valida("entrantes", p["categoria"])],
        "principales": [p for p in platos if es_categoria_menu_valida("principales", p["categoria"])],
        "postres": [p for p in platos if es_categoria_menu_valida("postres", p["categoria"])],
    }

def validar_ids_menu(conn, tipo, ids):
    if len(ids) != MENU_SLOTS[tipo] or len(set(ids)) != len(ids):
        raise ValueError("El menú no tiene el número correcto de opciones o contiene duplicados.")

    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id_plato, categoria FROM Plato WHERE id_plato IN ({placeholders})",
        ids
    ).fetchall()

    if len(rows) != len(ids):
        raise ValueError("Alguna opción del menú no existe.")

    categorias = {row["id_plato"]: row["categoria"] for row in rows}
    for id_plato in ids:
        if not es_categoria_menu_valida(tipo, categorias[id_plato]):
            raise ValueError("Alguna opción no pertenece a una categoría válida para esa sección del menú.")

def guardar_menu_dia(fecha, entrantes, principales, postres):
    conn = get_db_connection()
    try:
        validar_ids_menu(conn, "entrantes", entrantes)
        validar_ids_menu(conn, "principales", principales)
        validar_ids_menu(conn, "postres", postres)

        existente = conn.execute(
            "SELECT id_menu FROM Menu_Diario WHERE fecha = ?",
            (fecha,)
        ).fetchone()

        if existente:
            id_menu = existente["id_menu"]
            conn.execute('''
                UPDATE Menu_Diario
                SET id_entrante = ?, id_principal = ?, id_postre = ?, precio_menu = ?
                WHERE id_menu = ?
            ''', (entrantes[0], principales[0], postres[0], MENU_PRECIO, id_menu))
            conn.execute("DELETE FROM Menu_Diario_Opcion WHERE id_menu = ?", (id_menu,))
        else:
            cursor = conn.execute('''
                INSERT INTO Menu_Diario (fecha, id_entrante, id_principal, id_postre, precio_menu)
                VALUES (?, ?, ?, ?, ?)
            ''', (fecha, entrantes[0], principales[0], postres[0], MENU_PRECIO))
            id_menu = cursor.lastrowid

        for tipo, ids in (
            ("entrantes", entrantes),
            ("principales", principales),
            ("postres", postres),
        ):
            for posicion, id_plato in enumerate(ids, start=1):
                conn.execute('''
                    INSERT INTO Menu_Diario_Opcion (id_menu, tipo, posicion, id_plato)
                    VALUES (?, ?, ?, ?)
                ''', (id_menu, tipo, posicion, id_plato))

        conn.commit()
        return id_menu
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def normalizar_carrito(carrito):
    conn = get_db_connection()
    normalizado = []
    try:
        for item in carrito:
            cantidad = max(1, int(item.get("cantidad", 1)))

            if item.get("tipo") == "menu":
                fecha_menu = item.get("fecha") or date.today().isoformat()
                menu = get_menu_dia(fecha_menu)
                if not menu or int(item.get("id_menu", 0)) != int(menu["id_menu"]):
                    raise ValueError("El menú del día seleccionado no está disponible.")

                seleccion = item.get("seleccion", {})
                ids_seleccion = {
                    "entrantes": int(seleccion.get("entrante", {}).get("id", 0)),
                    "principales": int(seleccion.get("principal", {}).get("id", 0)),
                    "postres": int(seleccion.get("postre", {}).get("id", 0)),
                    "bebidas": int(seleccion.get("bebida", {}).get("id", 0)),
                }
                ids_validos = {
                    tipo: {opcion["id_plato"] for opcion in menu[tipo]}
                    for tipo in MENU_SLOTS
                }
                if any(ids_seleccion[tipo] not in ids_validos[tipo] for tipo in MENU_SLOTS):
                    raise ValueError("La selección no pertenece al menú del día configurado.")

                bebidas_validas = {bebida["id_plato"] for bebida in menu["bebidas"]}
                if ids_seleccion["bebidas"] not in bebidas_validas:
                    raise ValueError("La bebida seleccionada no está disponible.")

                nombres = {}
                for tipo, campo in (("entrantes", "entrante"), ("principales", "principal"), ("postres", "postre")):
                    nombres[campo] = next(
                        opcion["nombre"] for opcion in menu[tipo]
                        if opcion["id_plato"] == ids_seleccion[tipo]
                    )
                nombres["bebida"] = next(
                    bebida["nombre"] for bebida in menu["bebidas"]
                    if bebida["id_plato"] == ids_seleccion["bebidas"]
                )

                normalizado.append({
                    "tipo": "menu",
                    "id_menu": menu["id_menu"],
                    "fecha": menu["fecha"],
                    "nombre": "Menú del día",
                    "precio": MENU_PRECIO,
                    "cantidad": cantidad,
                    "bebida": nombres["bebida"],
                    "seleccion": {
                        "entrante": {"id": ids_seleccion["entrantes"], "nombre": nombres["entrante"]},
                        "principal": {"id": ids_seleccion["principales"], "nombre": nombres["principal"]},
                        "postre": {"id": ids_seleccion["postres"], "nombre": nombres["postre"]},
                        "bebida": {"id": ids_seleccion["bebidas"], "nombre": nombres["bebida"]},
                    }
                })
            else:
                id_plato = int(item.get("id_plato", 0))
                plato = conn.execute(
                    "SELECT id_plato, nombre, precio FROM Plato WHERE id_plato = ? AND activo_en_carta = 1",
                    (id_plato,)
                ).fetchone()
                if not plato:
                    raise ValueError("Algún plato del carrito ya no está disponible.")

                normalizado.append({
                    "id_plato": plato["id_plato"],
                    "nombre": plato["nombre"],
                    "precio": float(plato["precio"]),
                    "cantidad": cantidad,
                })

        return normalizado
    finally:
        conn.close()

ensure_menu_schema()

def es_cliente(email):
    """Función para comprobar si el usuario es cliente (es_cliente = 1) o gerente (0)"""
    conexion = get_db_connection()
    user = conexion.execute('SELECT es_cliente FROM Usuarios WHERE correo_electronico = ?', (email,)).fetchone()
    conexion.close()
    if user and user['es_cliente'] == 1:
        return True
    return False

def get_facturación(origin, end):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT importe, fecha FROM Pedido WHERE  fecha >= ? AND fecha <= ?
        
    ''', (origin, end))

    raw_data = cursor.fetchall()
    conn.close()

    # Creamos un diccionario de totales por fecha para búsqueda rápida O(1)
    # Convertimos el string de la DB a objeto date
    ventas_por_dia = {}
    for row in raw_data:
        f_obj = datetime.strptime(row['fecha'], "%Y-%m-%d").date()
        ventas_por_dia[f_obj] = ventas_por_dia.get(f_obj, 0) + row['importe']

    # Generamos el rango completo de fechas (como objetos date)
    fecha_inicio = datetime.strptime(origin, "%Y-%m-%d").date()
    fecha_fin = datetime.strptime(end, "%Y-%m-%d").date()
    
    lista_fechas = []
    lista_importes = []
    fecha_actual = fecha_inicio

    while fecha_actual <= fecha_fin:
        lista_fechas.append(fecha_actual)
        # Buscamos la fecha en nuestro diccionario, si no existe, el total es 0
        lista_importes.append(ventas_por_dia.get(fecha_actual, 0.0))
        fecha_actual += timedelta(days=1)

    # Total general
    total_periodo = sum(lista_importes)

    print( total_periodo, lista_fechas, lista_importes)
    conn.close()
    return  lista_fechas, lista_importes, total_periodo


def generar_poligono_frecuencias(origin, end):
# Obtener datos
    fechas, totales, total_global = get_facturación(origin, end)
    
    if not fechas:
        return "<p>No hay datos para el rango seleccionado</p>"

    # Crear el gráfico de líneas
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=fechas, 
        y=totales, 
        mode='lines+markers', # Líneas y puntos
        fill='tozeroy',       # Rellena el área hasta el eje X (efecto polígono)
        line=dict(color='#E67E22', width=3), # Color naranja Himalaya
        marker=dict(size=8),
        name='Facturación (€)'
    ))

    fig.update_xaxes(
        tickformat="%d/%m/%Y", # Formato español: día/mes/año
        dtick="D1",            # Fuerza a que aparezca una marca por cada día
        tickangle=45           # Rota las fechas para que no se amontonen
    )   
    
    # Personalizar el diseño
    fig.update_layout(
        title='',
        xaxis_title='Fecha',
        yaxis_title='Total (€)',
        template='plotly_white', # Fondo limpio y profesional
        hovermode='x unified',   # Muestra info de todos los puntos en esa fecha
        margin=dict(l=40, r=40, t=60, b=40)
    )

    # Convertir a HTML 
    # include_plotlyjs='cdn' hace que el gráfico pese poco al no incluir la librería entera
    div_grafico = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    
    return div_grafico

def generate_menu():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Definimos las categorías que queremos buscar
    categorias = ['entrante', 'principal', 'postre']
    seleccion = {}

    try:
        # Obtenemos un plato aleatorio para cada categoría
        for cat in categorias:
            cursor.execute(
                "SELECT id_plato, nombre FROM Plato WHERE categoria = ? ORDER BY RANDOM() LIMIT 1", 
                (cat,)
            )
            plato = cursor.fetchone()
            if plato:
                seleccion[cat] = plato['id_plato']
            else:
                print(f"Error: No se encontraron platos en la categoría {cat}")
                return None

        # Insertamos el menú generado en Menu_Diario
        # Usamos la fecha de hoy en formato YYYY-MM-DD
        fecha_hoy = date.today().isoformat()
        
        cursor.execute('''
            INSERT INTO Menu_Diario (fecha, id_entrante, id_principal, id_postre)
            VALUES (?, ?, ?, ?)
        ''', (fecha_hoy, seleccion['entrante'], seleccion['principal'], seleccion['postre']))
        
        conn.commit()
        print(f"Menú del día ({fecha_hoy}) guardado correctamente.")
        return seleccion

    except sqlite3.IntegrityError:
        print(f"Aviso: Ya existe un menú registrado para la fecha {fecha_hoy}.")
    except sqlite3.Error as e:
        print(f"Error de base de datos: {e}")
    finally:
        conn.close()

# ---------------------------
# RUTAS PÚBLICAS Y AUTENTICACIÓN
# ---------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("profile"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM Usuarios WHERE correo_electronico = ?', (email,)).fetchone()
        conn.close()

        if not usuario or usuario["contrasena"] != password:
            error = "Email o contraseña incorrectos"
        else:
            session["user"] = email
            # Redirigimos al perfil como en el archivo 2 (puedes cambiarlo a 'home' si prefieres)
            return redirect(url_for("profile"))
            
    return render_template("login.html", error=error)

@app.route("/registro")
def registro():
    return redirect(url_for("register"))

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if "user" in session:
        return redirect(url_for("profile"))
    if request.method == "POST":
        nombre = request.form["nombre"]
        apellidos = request.form["apellidos"]
        email = request.form["email"]
        direccion = request.form["direccion"]
        password = request.form["password"]

        if not nombre or not apellidos or not email or not direccion or not password:
            error = "Todos los campos son obligatorios"
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            error = "Email no válido"
        else:
            conn = get_db_connection()
            usuario_existente = conn.execute('SELECT id_cliente FROM Usuarios WHERE correo_electronico = ?', (email,)).fetchone()
            
            if usuario_existente:
                error = "El email ya está registrado"
            else:
                nombre_completo = f"{nombre} {apellidos}"
                # Asumimos que la BD tiene un valor por defecto para 'es_cliente' (ej. 1)
                conn.execute('''
                    INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena, saldo) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (nombre_completo, direccion, email, password, 0.0))
                conn.commit()
                
                session["user"] = email
                session["direccion"] = direccion
                conn.close()
                return redirect(url_for("profile"))
            conn.close()

    return render_template("register.html", error=error)

@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("home"))

# ---------------------------
# PERFIL
# ---------------------------
@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM Usuarios WHERE correo_electronico = ?', (session["user"],)).fetchone()
    conn.close()

    if not user_row:
        session.pop("user", None)
        return redirect(url_for("login"))

    # Separar nombre y apellidos para el formulario de edición (Lógica del Archivo 2)
    nombre_completo = user_row["nombre"] or ""
    partes = nombre_completo.split(" ", 1)
    nombre = partes[0] if partes else ""
    apellidos = partes[1] if len(partes) > 1 else ""

    return render_template("profile.html", user={
        "email": user_row["correo_electronico"],
        "nombre": nombre,
        "apellidos": apellidos,
        "direccion": user_row["direccion"],
        "saldo": user_row["saldo"]
    })

@app.route("/update", methods=["POST"])
def update():
    if "user" not in session:
        return redirect(url_for("register"))

    email = session["user"]
    nombre = request.form["nombre"]
    apellidos = request.form["apellidos"]
    direccion = request.form["direccion"]
    nombre_completo = f"{nombre} {apellidos}"

    conn = get_db_connection()
    conn.execute('''
        UPDATE Usuarios
        SET nombre = ?, direccion = ? 
        WHERE correo_electronico = ?
    ''', (nombre_completo, direccion, email))
    conn.commit()
    conn.close()

    return redirect(url_for("profile"))

# ---------------------------
# GESTIÓN DE CARTA Y PLATOS
# ---------------------------
@app.route("/carta")
def carta():
    if "user"  in session :
        email = session["user"]
        es_usu_cliente = es_cliente(email)
    else:
        return  render_template("login.html", error="Debes iniciar sesión para ver la carta")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Plato")
    if   es_usu_cliente:
        # El cliente ve la carta
        template = "carta.html"
    else:
        # El superusuario ve la carta con opcioens de modificar
        template = "carta_superuser.html"
        
    platos = cursor.fetchall()
    conn.close()

    # Formateamos la lista de platos para enviarla al template
    platos_formateados = [formato_plato(p) for p in platos]
    menu_fecha = date.today().isoformat()
    menu_dia = get_menu_dia(menu_fecha)
    menu_candidates = get_menu_candidate_platos(platos_formateados)

    return render_template(
        template,
        platos=platos_formateados,
        menu_dia=menu_dia,
        menu_fecha=menu_fecha,
        menu_fecha_es=formato_fecha_es(menu_fecha),
        menu_candidates=menu_candidates
    )
#Carrito
@app.route("/carrito", methods=["POST"])
def carrito():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Debes iniciar sesión"}), 401

    data = request.get_json()
    carrito = data.get("restaurante_carrito", [])
    try:
        carrito = normalizar_carrito(carrito)
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    session["carrito"] = carrito
    session["precio"] = sum(float(item["precio"]) * float(item["cantidad"]) for item in carrito)

    conn = get_db_connection()
    resultado = conn.execute("SELECT saldo FROM Usuarios WHERE correo_electronico=?", (session["user"],)).fetchone()
    conn.close()

    session["saldo"] = float(resultado[0]) if resultado else 0.0

    return jsonify({"status": "success"})

@app.route("/pago")
def pago():
    if "user" not in session:
        return redirect(url_for("login"))

    carrito = session.get("carrito", [])
    if not carrito:
        flash("No tienes artículos en el carrito.")
        return redirect(url_for("carta"))

    # Obtenemos el precio base original de la sesión
    total = float(session.get("precio", 0.0))

    # CORRECCIÓN 1: Consultar el saldo REAL y actualizado desde la Base de Datos
    conn = get_db_connection()
    usuario = conn.execute(
        "SELECT saldo FROM Usuarios WHERE correo_electronico = ?",
        (session["user"],)
    ).fetchone()
    conn.close()

    if not usuario:
        flash("Usuario no encontrado.")
        return redirect(url_for("carta"))
    
    saldo = float(usuario["saldo"])

    # Tu lógica de negocio para calcular el descuento
    if saldo >= 100:
        descuento = (saldo // 100) * 5
    else:
        descuento = 0.0

    total_con_descuento = max(0.0, total - descuento)

    # CORRECCIÓN 2: Guardar el precio final con descuento en la sesión 
    # para que /confirmar_pago pueda aplicarlo de verdad en la Base de Datos
    session["precio_final"] = total_con_descuento

    return render_template(
        "pago.html",
        cart_items=carrito,
        total=total,
        saldo=saldo,
        descuento=descuento,
        final_total=total_con_descuento
    )

@app.route("/confirmar_pago", methods=["POST"])
def confirmar_pago():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Debes iniciar sesión."}), 401

    carrito = session.get("carrito", [])
    if not carrito:
        return jsonify({"status": "error", "message": "No tienes artículos en el carrito."}), 400

    importe_total = float(session.get("precio_final", session.get("precio", 0.0)))
    saldo = float(session.get('saldo', 0.0))
    if importe_total < 15:
        return jsonify({"status": "error", "message": "El pedido mínimo es de 15€."}), 400

    conn = get_db_connection()
    try:
        usuario = conn.execute(
            "SELECT id_cliente, direccion FROM Usuarios WHERE correo_electronico = ?",
            (session["user"],)
        ).fetchone()
        if not usuario:
            return jsonify({"status": "error", "message": "Usuario no encontrado."}), 400

        ahora = datetime.now()
        cursor = conn.execute('''
            INSERT INTO Pedido (id_cliente, fecha, hora, importe, estado, dir_envio)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            usuario["id_cliente"],
            ahora.strftime("%Y-%m-%d"),
            ahora.strftime("%H:%M:%S"),
            importe_total,
            "Recibido",
            usuario["direccion"]
        ))
        id_pedido = cursor.lastrowid

        for item in carrito:
            if item.get("tipo") == "menu":
                conn.execute('''
                    INSERT INTO Detalle_Pedido (id_pedido, id_menu, cantidad)
                    VALUES (?, ?, ?)
                ''', (id_pedido, item["id_menu"], item["cantidad"]))
            else:
                conn.execute('''
                    INSERT INTO Detalle_Pedido (id_pedido, id_plato, cantidad)
                    VALUES (?, ?, ?)
                ''', (id_pedido, item["id_plato"], item["cantidad"]))


        conn.execute('''
            UPDATE Usuarios 
            SET saldo = saldo + ? 
            WHERE id_cliente = ?
        ''', (importe_total, usuario["id_cliente"]))


        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        return jsonify({"status": "error", "message": f"No se pudo registrar el pedido: {exc}"}), 500
    finally:
        conn.close()

    session.pop("precio_final", None)
    session.pop("carrito", None)
    session.pop("precio", None)
    session.pop("saldo", None)

    return jsonify({"status": "success", "message": "Pago confirmado."})

@app.route("/platos")
def platos_totales():
    """Ruta del archivo 1 para ver todos los platos con su estado"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Plato")
    platos = cursor.fetchall()
    conn.close()

    return render_template("platos.html", platos=[
        {
            "id_plato": p["id_plato"],
            "nombre": p["nombre"],
            "descripcion": p["descripción"] if "descripción" in p.keys() else p["descripcion"],
            "precio": p["precio"],
            "categoria": p["categoria"],
            "activo_en_carta" : p["activo_en_carta"]
        } for p in platos
    ])

@app.route("/quitar_de_carta", methods=["POST"])
def quitar_de_carta():
    id_plato = request.form.get("id_plato")
    if id_plato and "user" in session:
        if not es_cliente(session["user"]): # Comprobación superusuario
            conn = get_db_connection()
            conn.execute("UPDATE Plato SET activo_en_carta = 0 WHERE id_plato = ?", (id_plato,))
            conn.commit()
            conn.close()
    return redirect(url_for("carta"))

@app.route("/añadir_en_carta", methods=["POST"])
def anadir_en_carta():
    id_plato = request.form.get("id_plato")
    if id_plato and "user" in session:
        if not es_cliente(session["user"]): # Comprobación superusuario
            conn = get_db_connection()
            # Corrección de bug: Aquí debe ser 1 para añadirlo a la carta
            conn.execute("UPDATE Plato SET activo_en_carta = 1 WHERE id_plato = ?", (id_plato,))
            conn.commit()
            conn.close()
    return redirect(url_for("carta"))

@app.route("/nuevo_plato", methods=["POST"])
def nuevo_plato():
    if "user" not in session or es_cliente(session["user"]):
        return redirect(url_for("carta"))

    nombre = request.form["nombre"]
    descripción = request.form["descripción"]
    precio = float(request.form["precio"]) # Mejor float para precios
    categoria = request.form["categoría"]
    activo_en_carta = request.form["carta"] == "on" # Checkbox devuelve "on" si está marcado

    conn = get_db_connection()
    conn.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta) VALUES (?, ?, ?, ?, ?)", 
                (nombre, descripción, precio, categoria, activo_en_carta))
    conn.commit()
    conn.close()
    
    return redirect(url_for("carta"))

@app.route("/admin/menu_dia", methods=["POST"])
def admin_menu_dia():
    if "user" not in session or es_cliente(session["user"]):
        return redirect(url_for("carta"))

    fecha = date.today().isoformat()
    try:
        entrantes = [int(request.form[f"entrante_{i}"]) for i in range(1, 4)]
        principales = [int(request.form[f"principal_{i}"]) for i in range(1, 4)]
        postres = [int(request.form[f"postre_{i}"]) for i in range(1, 3)]
        guardar_menu_dia(fecha, entrantes, principales, postres)
        flash("Menú del día guardado correctamente.")
    except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        flash(f"No se pudo guardar el menú del día: {exc}")

    return redirect(url_for("carta"))

#-------------------------------
# PAGO EXTERNO
#------------------------------

# La ruta /pago ya está definida más arriba y muestra la pantalla de pago.

#--------------------------------
# MENÚ DEL DÍA
#--------------------------------


#------------------------------------
# FACTURACIÓN
#------------------------------------

@app.route('/facturación', methods=['GET', 'POST'])
def facturación():
    conn = get_db_connection() # Mantienes tu conexión por si la usas en la ruta
    
    # Inicializamos las variables
    origin = None
    end = None
    div_grafico = None

    # Detectamos si el usuario ha enviado el formulario con las fechas
    if request.method == 'POST':
        origin = request.form.get('fecha_inicio')
        end = request.form.get('fecha_fin')
    else:
        # Por si acaso acceden directamente pasando parámetros por la URL
        origin = request.args.get('fecha_inicio')
        end = request.args.get('fecha_fin')

    # Si ambas fechas están presentes, llamamos a tu función para crear el gráfico
    if origin and end:
        div_grafico = generar_poligono_frecuencias(origin, end)

    # Pasamos el gráfico y las fechas seleccionadas de vuelta a la plantilla
    return render_template(
        'facturación.html', 
        grafico=div_grafico, 
        origin=origin, 
        end=end
    )

if __name__ == "__main__":
    #get_facturación("2026-04-20", "2026-04-23")
    #generar_poligono_frecuencias("2026-04-20", "2026-04-23")
    app.run(debug=True)
