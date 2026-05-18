import sqlite3
import unittest
import os

# RUTA ABSOLUTA de tu base de datos
RUTA_BD = r"sabor_himalaya.db"

class TestSaborHimalayaDB(unittest.TestCase):
    # Lista global para guardar los resultados en el formato solicitado
    resultados_visuales = []

    def setUp(self):
        self.conexion = sqlite3.connect(RUTA_BD)
        self.cursor = self.conexion.cursor()
        # Activar la comprobación de claves foráneas (muy importante en SQLite)
        self.cursor.execute("PRAGMA foreign_keys = ON;")

    def tearDown(self):
        """Limpieza profunda de todo lo que contenga la palabra TEST o fechas/correos falsos."""
        self.cursor.execute("DELETE FROM Detalle_Pedido WHERE id_pedido IN (SELECT id_pedido FROM Pedido WHERE dir_envio LIKE '%TEST%')")
        self.cursor.execute("DELETE FROM Pedido WHERE dir_envio LIKE '%TEST%'")
        self.cursor.execute("DELETE FROM Usuarios WHERE correo_electronico LIKE '%@test.com'")
        self.cursor.execute("DELETE FROM Plato WHERE nombre LIKE '%TEST%'")
        self.cursor.execute("DELETE FROM Menu_Diario WHERE fecha LIKE '2099-%'")
        self.conexion.commit()
        self.conexion.close()

    def registrar_resultado(self, nombre_test, exito):
        """Formatea y guarda el resultado del test."""
        status = "ok" if exito else "ko"
        # Ajustamos el número del test basándonos en cuántos llevamos
        self.resultados_visuales.append(f"Test {len(self.resultados_visuales)+1}: {nombre_test}: {status}")

    # ==========================================
    # TESTS POSITIVOS (Operaciones que DEBEN funcionar)
    # ==========================================

    def test_01_insertar_usuario(self):
        try:
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena) VALUES (?,?,?,?)", 
                                ("Cliente TEST", "Calle TEST", "1@test.com", "pass123"))
            self.conexion.commit()
            self.registrar_resultado("Inserción de nuevo cliente válida", True)
        except Exception:
            self.registrar_resultado("Inserción de nuevo cliente válida", False)

    def test_02_insertar_plato(self):
        try:
            self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria) VALUES (?,?,?,?)", 
                                ("Plato TEST", "Desc TEST", 10.5, "Entrante"))
            self.conexion.commit()
            self.registrar_resultado("Inserción de nuevo plato válida", True)
        except Exception:
            self.registrar_resultado("Inserción de nuevo plato válida", False)

    def test_03_crear_pedido(self):
        try:
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena) VALUES (?,?,?,?)", 
                                ("TEST", "TEST", "2@test.com", "pass"))
            id_cliente = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO Pedido (id_cliente, fecha, hora, importe, estado, dir_envio) VALUES (?,?,?,?,?,?)", 
                                (id_cliente, "2026-05-01", "14:00", 20.0, "Pendiente", "Calle TEST"))
            self.conexion.commit()
            self.registrar_resultado("Creación de un pedido válido", True)
        except Exception:
            self.registrar_resultado("Creación de un pedido válido", False)

    def test_04_crear_detalle_pedido(self):
        try:
            # Reutilizamos un plato real (ID 1)
            self.cursor.execute("INSERT INTO Pedido (fecha, hora, importe, estado, dir_envio) VALUES (?,?,?,?,?)", 
                                ("2026-05-01", "14:00", 20.0, "Pendiente", "Calle TEST"))
            id_pedido = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO Detalle_Pedido (id_pedido, id_plato, cantidad) VALUES (?,?,?)", 
                                (id_pedido, 1, 2))
            self.conexion.commit()
            self.registrar_resultado("Añadir detalle a un pedido", True)
        except Exception:
            self.registrar_resultado("Añadir detalle a un pedido", False)

    def test_05_crear_menu_diario(self):
        try:
            self.cursor.execute("INSERT INTO Menu_Diario (fecha, id_entrante, id_principal, id_postre) VALUES (?,?,?,?)", 
                                ("2099-01-01", 1, 9, 21))
            self.conexion.commit()
            self.registrar_resultado("Creación de un menú diario válido", True)
        except Exception:
            self.registrar_resultado("Creación de un menú diario válido", False)

    def test_06_actualizar_saldo_cliente(self):
        try:
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena, saldo) VALUES (?,?,?,?,?)", 
                                ("TEST", "TEST", "3@test.com", "pass", 10.0))
            id_cliente = self.cursor.lastrowid
            self.cursor.execute("UPDATE Usuarios SET saldo = ? WHERE id_cliente = ?", (25.5, id_cliente))
            self.conexion.commit()
            self.registrar_resultado("Actualización de saldo de un cliente", True)
        except Exception:
            self.registrar_resultado("Actualización de saldo de un cliente", False)

    def test_07_actualizar_estado_pedido(self):
        try:
            self.cursor.execute("INSERT INTO Pedido (fecha, hora, importe, estado, dir_envio) VALUES (?,?,?,?,?)", 
                                ("2026-05-01", "14:00", 20.0, "Pendiente", "Calle TEST"))
            id_pedido = self.cursor.lastrowid
            self.cursor.execute("UPDATE Pedido SET estado = ? WHERE id_pedido = ?", ("Entregado", id_pedido))
            self.conexion.commit()
            self.registrar_resultado("Actualización de estado de un pedido", True)
        except Exception:
            self.registrar_resultado("Actualización de estado de un pedido", False)

    def test_08_eliminar_plato(self):
        try:
            self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria) VALUES (?,?,?,?)", 
                                ("Plato TEST Borrar", "Desc", 5.0, "Postre"))
            id_plato = self.cursor.lastrowid
            self.cursor.execute("DELETE FROM Plato WHERE id_plato = ?", (id_plato,))
            self.conexion.commit()
            self.registrar_resultado("Eliminación de un plato", True)
        except Exception:
            self.registrar_resultado("Eliminación de un plato", False)


    # ==========================================
    # TESTS NEGATIVOS (Operaciones que DEBEN dar error)
    # ==========================================

    def test_09_error_usuario_sin_correo(self):
        try:
            # Correo electrónico es NULL
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena) VALUES (?,?,?,?)", 
                                ("TEST", "TEST", None, "pass"))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Usuario sin correo electrónico (NOT NULL)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Usuario sin correo electrónico (NOT NULL)", True)

    def test_10_error_correo_duplicado(self):
        try:
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena) VALUES (?,?,?,?)", 
                                ("TEST 1", "TEST", "duplicado@test.com", "pass"))
            # Intentamos insertar el mismo correo
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena) VALUES (?,?,?,?)", 
                                ("TEST 2", "TEST", "duplicado@test.com", "pass"))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Correos electrónicos duplicados (UNIQUE)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Correos electrónicos duplicados (UNIQUE)", True)

    def test_11_error_plato_sin_precio(self):
        try:
            # Precio es NULL
            self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria) VALUES (?,?,?,?)", 
                                ("TEST", "TEST", None, "Principal"))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Plato sin precio (NOT NULL)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Plato sin precio (NOT NULL)", True)

    def test_12_error_menu_fecha_duplicada(self):
        try:
            self.cursor.execute("INSERT INTO Menu_Diario (fecha, id_entrante, id_principal, id_postre) VALUES (?,?,?,?)", 
                                ("2099-12-31", 1, 9, 21))
            # Intentamos crear otro menú el mismo día
            self.cursor.execute("INSERT INTO Menu_Diario (fecha, id_entrante, id_principal, id_postre) VALUES (?,?,?,?)", 
                                ("2099-12-31", 2, 10, 22))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Múltiples menús en la misma fecha (UNIQUE)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Múltiples menús en la misma fecha (UNIQUE)", True)

    def test_13_error_pedido_sin_estado(self):
        try:
            # Estado es NULL
            self.cursor.execute("INSERT INTO Pedido (fecha, hora, importe, estado, dir_envio) VALUES (?,?,?,?,?)", 
                                ("2026-05-01", "14:00", 20.0, None, "Calle TEST"))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Pedido sin estado definido (NOT NULL)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Pedido sin estado definido (NOT NULL)", True)

    def test_14_error_pedido_cliente_falso(self):
        try:
            # Intentamos asignar un pedido al cliente ID 999999 (que no existe)
            self.cursor.execute("INSERT INTO Pedido (id_cliente, fecha, hora, importe, estado, dir_envio) VALUES (?,?,?,?,?,?)", 
                                (999999, "2026-05-01", "14:00", 20.0, "Pendiente", "Calle TEST"))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Pedido asignado a un cliente inexistente (FOREIGN KEY)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Pedido asignado a un cliente inexistente (FOREIGN KEY)", True)

    def test_15_error_plato_sin_nombre(self):
        try:
            # Nombre es NULL
            self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria) VALUES (?,?,?,?)", 
                                (None, "Desc", 10.0, "Entrante"))
            self.conexion.commit()
            self.registrar_resultado("Bloqueo: Plato sin nombre (NOT NULL)", False)
        except sqlite3.IntegrityError:
            self.registrar_resultado("Bloqueo: Plato sin nombre (NOT NULL)", True)


if __name__ == '__main__':
    # Ejecutamos las pruebas silenciando la salida por defecto de unittest
    with open(os.devnull, 'w') as f:
        runner = unittest.TextTestRunner(stream=f)
        unittest.main(testRunner=runner, exit=False)

    # Imprimimos la salida visual exacta que has solicitado
    print("\n" + "="*50)
    print(" RESULTADOS DE LAS PRUEBAS DE LA BASE DE DATOS")
    print("="*50 + "\n")
    
    # Ordenamos la lista alfabéticamente por el nombre del método (Test 01, Test 02...)
    # ya que unittest a veces los ejecuta en un orden ligeramente distinto
    resultados_ordenados = sorted(TestSaborHimalayaDB.resultados_visuales)
    
    for resultado in resultados_ordenados:
        print(resultado)
        
    print("\n" + "="*50 + "\n")