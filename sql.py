import sqlite3

def crear_base_datos():
    conexion = sqlite3.connect('sabor_himalaya.db')
    cursor = conexion.cursor()

    # 1. TABLA PLATO (Con el campo para saber si está en la carta actual), por defecto no están en la carta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Plato (
            id_plato INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            precio REAL NOT NULL,
            categoria TEXT NOT NULL,
            activo_en_carta BOOLEAN DEFAULT 0
        )
    ''')

    # 2. TABLA MENÚ DIARIO (Cubre RQ4 y RQ5)
    # Enlaza con los platos específicos seleccionados por el chef
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Menu_Diario (
            id_menu INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT UNIQUE NOT NULL,
            id_entrante INTEGER NOT NULL,
            id_principal INTEGER NOT NULL,
            id_postre INTEGER NOT NULL,
            precio_menu REAL DEFAULT 15.0,
            FOREIGN KEY (id_entrante) REFERENCES Plato(id_plato),
            FOREIGN KEY (id_principal) REFERENCES Plato(id_plato),
            FOREIGN KEY (id_postre) REFERENCES Plato(id_plato)
        )
    ''')

    cursor.execute('''
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

    # 3. TABLA CLIENTE (Cubre RQ3) Diferecnia entre cliente y gerente
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Usuarios (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            direccion TEXT NOT NULL,
            telefono TEXT,
            correo_electronico TEXT UNIQUE NOT NULL,
            contrasena TEXT NOT NULL,
            tarjeta TEXT,
            saldo REAL DEFAULT 0.0,
            es_cliente BOOLEAN DEFAULT 1
        )
    ''')

    # 4. TABLA PEDIDO (Cubre RQ6)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Pedido (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            importe REAL NOT NULL,
            estado TEXT NOT NULL,
            dir_envio TEXT NOT NULL,
            FOREIGN KEY (id_cliente) REFERENCES Usuarios(id_cliente)
        )
    ''')

    # 5. TABLA DETALLE_PEDIDO (Para manejar múltiples productos en un pedido)
    # Permite registrar si el cliente pidió un plato suelto o un menú entero
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Detalle_Pedido (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER,
            id_plato INTEGER,
            id_menu INTEGER,
            cantidad INTEGER DEFAULT 1,
            FOREIGN KEY (id_pedido) REFERENCES Pedido(id_pedido),
            FOREIGN KEY (id_plato) REFERENCES Plato(id_plato),
            FOREIGN KEY (id_menu) REFERENCES Menu_Diario(id_menu)
        )
    ''')


    conexion.commit()

    print("✅ Base de datos 'sabor_himalaya.db' creada con éxito y adaptada a la estrategia.")
    
    conexion.close()

    # platos = [
    #     # --- ENTRANTES ---
    #     ("Samosas de verduras", "Empanadillas crujientes rellenas de patata y especias", 5.50, "Entrante", 1),
    #     ("Pakoras de cebolla", "Cebolla rebozada en harina de garbanzo", 4.90, "Entrante", 1),
    #     ("Momos vegetarianos", "Empanadillas al vapor rellenas de verduras", 6.20, "Entrante", 1),
    #     ("Momos de pollo", "Empanadillas al vapor rellenas de pollo especiado", 6.80, "Entrante", 1),
    #     ("Dal Tadka", "Lentejas amarillas con especias y mantequilla", 6.50, "Entrante", 1),
    #     ("Aloo Chaat", "Patatas fritas con salsa picante y especias", 5.80, "Entrante", 1),
    #     ("Chatamari", "Crepe nepalí con verduras y especias", 7.20, "Entrante", 1),
    #     ("Sekuwa de pollo", "Brochetas de pollo marinadas a la parrilla", 7.50, "Entrante", 1),

    #     # --- PRINCIPALES ---
    #     ("Pollo Tikka Masala", "Pollo en salsa cremosa de tomate y especias", 11.90, "Principal", 1),
    #     ("Butter Chicken", "Pollo en salsa de mantequilla y tomate", 12.50, "Principal", 1),
    #     ("Cordero Korma", "Cordero con salsa suave de frutos secos", 13.50, "Principal", 1),
    #     ("Chana Masala", "Garbanzos especiados al estilo tradicional", 9.50, "Principal", 1),
    #     ("Biryani de verduras", "Arroz basmati con verduras y especias", 10.20, "Principal", 1),
    #     ("Biryani de pollo", "Arroz basmati con pollo y especias aromáticas", 11.80, "Principal", 1),
    #     ("Thukpa", "Sopa nepalí de fideos con verduras o carne", 9.00, "Principal", 1),
    #     ("Chow Mein", "Fideos salteados con verduras y salsa de soja", 9.50, "Principal", 1),
    #     ("Paneer Butter Masala", "Queso fresco en salsa cremosa especiada", 10.50, "Principal", 1),
    #     ("Vegetable Curry", "Curry mixto de verduras con especias", 9.80, "Principal", 1),
    #     ("Arroz basmati", "Arroz blanco aromático", 3.50, "Acompañamiento", 1),
    #     ("Pan Naan", "Pan tradicional al horno tandoor", 2.20, "Acompañamiento", 1),

    #     # --- POSTRES ---
    #     ("Gulab Jamun", "Bolitas dulces en almíbar", 4.50, "Postre", 1),
    #     ("Kheer", "Arroz con leche y cardamomo", 4.20, "Postre", 1),
    #     ("Helado de mango", "Helado cremoso de mango natural", 3.90, "Postre", 1),
    #     ("Barfi", "Dulce de leche con coco y frutos secos", 4.80, "Postre", 1),
    #     ("Laddu", "Dulce tradicional de harina y azúcar", 4.30, "Postre", 1),

    #     # --- BEBIDAS ---
    #     ("Lassi de mango", "Bebida fría de yogur y mango", 3.80, "Bebida", 1),
    #     ("Lassi de banana", "Bebida de yogur con plátano", 3.80, "Bebida", 1),
    #     ("Té Chai", "Té especiado con leche", 2.50, "Bebida", 1),
    #     ("Agua mineral", "Botella de agua", 1.80, "Bebida", 1),
    #     ("Refresco", "Coca-Cola, Fanta o similar", 2.20, "Bebida", 1)
    # ]



    # cursor.executemany('''
    #     INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta)
    #     VALUES (?, ?, ?, ?, ?)
    # ''', platos)

    # conexion.commit()
    # conexion.close()


def mostrar_datos():
    conexion = sqlite3.connect('sabor_himalaya.db')
    cursor = conexion.cursor()

    print("\n--- PLATOS ---")
    for fila in cursor.execute("SELECT * FROM Plato"):
        print(fila)

    print("\n--- USUARIOS ---")
    for fila in cursor.execute("SELECT * FROM Usuarios"):
        print(fila)

    print("\n--- MENÚS DIARIOS ---")
    for fila in cursor.execute("SELECT * FROM Menu_Diario"):
        print(fila)

    print("\n--- PEDIDOS ---")
    for fila in cursor.execute("SELECT * FROM Pedido"):
        print(fila)

    print("\n--- DETALLES PEDIDO ---")
    for fila in cursor.execute("SELECT * FROM Detalle_Pedido"):
        print(fila)

    conexion.close()

def añadir_user(nombre, direccion, telefono, correo_electronico, contrasena, tarjeta, saldo, es_cliente):
    conexion = sqlite3.connect('sabor_himalaya.db')
    cursor = conexion.cursor()
    cursor.execute('''
            INSERT INTO Usuarios (nombre, direccion, telefono, correo_electronico, contrasena, tarjeta, saldo, es_cliente)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, direccion, telefono, correo_electronico, contrasena, tarjeta, saldo, es_cliente))
    conexion.commit()
    conexion.close()

def query(sql, params=()):
    conexion = sqlite3.connect('sabor_himalaya.db')
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute(sql, params)
    resultado = cursor.fetchone()
    conexion.commit()
    conexion.close()
    return resultado

def añadir_plato(nombre, descripcion, precio, categoria, activo_en_carta=1):
    """Inserta un nuevo plato en la base de datos (RQ1 y RQ2)."""
    conexion = sqlite3.connect('sabor_himalaya.db')
    cursor = conexion.cursor()
    cursor.execute('''
        INSERT INTO Plato (Nombre, Desc, Precio, Categoria, activo_en_carta)
        VALUES (?, ?, ?, ?, ?)
    ''', (nombre, descripcion, precio, categoria, activo_en_carta))
    conexion.commit()
    conexion.close()

def modificar_plato(id_plato, nueva_categoria, nueva_descripcion, nuevo_precio):
    """Modifica la categoría, descripción y precio de un plato existente (RQ2)."""
    conexion = sqlite3.connect('sabor_himalaya.db')
    cursor = conexion.cursor()
    cursor.execute('''
        UPDATE Plato 
        SET Categoria = ?, Desc = ?, Precio = ?
        WHERE ID_Plato = ?
    ''', (nueva_categoria, nueva_descripcion, nuevo_precio, id_plato))
    conexion.commit()
    conexion.close()

def eliminar_plato(id_plato):
    """Elimina definitivamente un plato del sistema (RQ2)."""
    conexion = sqlite3.connect('sabor_himalaya.db')
    cursor = conexion.cursor()
    cursor.execute('''
        DELETE FROM Plato WHERE ID_Plato = ?
    ''', (id_plato,))
    conexion.commit()
    conexion.close()

if __name__ == '__main__':
    # crear_base_datos()
    mostrar_datos()
    # añadir_user("Juan Pérez", "Calle Falsa 123", "555-1234", "alejandro@example.com", "123123123", "1234567890123456", 0.0, 0)
    # if user and user['es_cliente'] == 1:
    #     print("Es cliente")
    # else:      
    #     print("No es cliente")
    query("UPDATE Usuarios SET saldo = 0 WHERE correo_electronico = ?", ("midiro2004@gmail.com",))
    # query ("DELETE FROM Usuarios WHERE correo_electronico = ?", ("alejandro@example.com",))
