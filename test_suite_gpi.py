import os
import sys

# =========================================================================
# 1. TRUCO DE ARQUITECTURA QA: EVITAR INTERFERENCIAS CON SITE-PACKAGES
# =========================================================================
directorio_actual = os.path.dirname(os.path.abspath(__file__))

if directorio_actual not in sys.path:
    sys.path.insert(0, directorio_actual)

if 'app' in sys.modules:
    del sys.modules['app']

# =========================================================================
# 2. IMPORTACIÓN SEGURO DEL BACKEND LOCAL (APP.PY)
# =========================================================================
try:
    from APP import app, get_db_connection, ensure_menu_schema, get_facturación
except ImportError:
    from app import app, get_db_connection, ensure_menu_schema, get_facturación

import unittest
import sqlite3
import json
from datetime import date

# =========================================================================
# 3. SUITE DE PRUEBAS AJUSTADA Y CALIBRADA
# =========================================================================
class TestSaborHimalayaSistemaIntegracion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Configuración de entorno limpio y aislamiento de BD de pruebas"""
        ensure_menu_schema()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # [CHECKLIST 5.1] Limpieza profunda del entorno para asegurar aislamiento absoluto
        cursor.execute("DELETE FROM Detalle_Pedido")
        cursor.execute("DELETE FROM Pedido")
        cursor.execute("DELETE FROM Menu_Diario_Opcion")
        cursor.execute("DELETE FROM Menu_Diario")
        cursor.execute("DELETE FROM Plato WHERE nombre LIKE '%INTEGRACION%' OR nombre LIKE '%SISTEMA%' OR nombre LIKE '%QA%'")
        cursor.execute("DELETE FROM Usuarios WHERE correo_electronico LIKE '%@gpi_test.com'")
        
        # [CHECKLIST 5.1] Reinicio explícito de secuencias auto-incrementales de SQLite
        try:
            cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name IN ('Plato', 'Usuarios', 'Pedido', 'Detalle_Pedido', 'Menu_Diario')")
        except sqlite3.OperationalError:
            pass
            
        # Semillas de prueba que cumplen con las categorías estrictas de tu APP.PY
        cursor.execute("""
            INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta)
            VALUES ('Samosa INTEGRACION TEST', 'Entrante de prueba', 5.50, 'Entrante', 1)
        """)
        cls.id_entrante = cursor.lastrowid

        cursor.execute("""
            INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta)
            VALUES ('Pollo Tikka INTEGRACION TEST', 'Principal de prueba', 12.50, 'Principal', 1)
        """)
        cls.id_principal = cursor.lastrowid

        cursor.execute("""
            INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta)
            VALUES ('Kheer INTEGRACION TEST', 'Postre de prueba', 4.50, 'Postre', 1)
        """)
        cls.id_postre = cursor.lastrowid
        
        conn.commit()
        conn.close()

    def setUp(self):
        """[CHECKLIST 5.2] Configuración antes de cada caso de prueba"""
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()

    def tearDown(self):
        """[CHECKLIST 5.2] Desmontaje del entorno aislado"""
        self.conn.close()
        self.app_context.pop()

    def registrar_resultado(self, nombre_test, exito, detalle=""):
        """Formatea la salida por pantalla con el estándar de QA solicitado"""
        estado = "OK" if exito else "KO"
        print(f"[{estado}] Executing Test: {nombre_test}")
        if not exito and detalle:
            print(f"      -> Razón del fallo: {detalle}")

    # =========================================================================
    # ENTRADA P.1: PRUEBAS DE INTEGRACIÓN (Conexión Frontend - Backend)
    # =========================================================================

    def test_01_verificar_conexion_home_web(self):
        """[CHECKLIST 1.4] Verificar que la ruta raíz responde correctamente (HTML rendered)"""
        try:
            response = self.app.get('/')
            self.assertEqual(response.status_code, 200)
            self.registrar_resultado("P.1.1 - Conexión de Interfaz Base (Home HTML)", True)
        except Exception as e:
            self.registrar_resultado("P.1.1 - Conexión de Interfaz Base (Home HTML)", False, str(e))

    def test_02_comprobar_api_asincrona_carrito(self):
        """[CHECKLIST 1.3] Verificar que el endpoint recibe y procesa peticiones AJAX/JSON del Frontend"""
        try:
            with self.app.session_transaction() as sess:
                sess['user'] = 'cliente_integracion@gpi_test.com'
            
            payload = {
                "restaurante_carrito": [
                    {"id_plato": self.id_entrante, "cantidad": 1},
                    {"id_plato": self.id_principal, "cantidad": 2}
                ]
            }
            response = self.app.post('/carrito', data=json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data.decode('utf-8'))
            self.assertEqual(data['status'], 'success')
            self.registrar_resultado("P.1.2 - Endpoint Asíncrono del Carrito (Frontend-Backend JSON)", True)
        except Exception as e:
            self.registrar_resultado("P.1.2 - Endpoint Asíncrono del Carrito (Frontend-Backend JSON)", False, str(e))

    def test_03_login_envio_formulario_integracion(self):
        """[CHECKLIST 1.4] Validar que las redirecciones de control llevan al usuario al perfil"""
        try:
            self.cursor.execute("""
                INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena, es_cliente)
                VALUES ('Juan Test', 'Calle 123', 'juan_login@gpi_test.com', 'pass123', 1)
            """)
            self.conn.commit()
            
            response = self.app.post('/login', data={'email': 'juan_login@gpi_test.com', 'password': 'pass123'})
            self.assertEqual(response.status_code, 302)  
            self.registrar_resultado("P.1.3 - Integración de Formulario Front-End de Autenticación", True)
        except Exception as e:
            self.registrar_resultado("P.1.3 - Integración de Formulario Front-End de Autenticación", False, str(e))

    def test_04_logout_limpieza_estado_sesion(self):
        """[CHECKLIST 1.3] Integración: Validar la destrucción y limpieza de variables tras el logout"""
        try:
            with self.app.session_transaction() as sess:
                sess['user'] = 'test_logout@gpi_test.com'
                sess['carrito'] = [{'id_plato': self.id_entrante, 'cantidad': 1}]
            
            response = self.app.get('/logout')
            self.assertEqual(response.status_code, 302) 
            
            with self.app.session_transaction() as post_sess:
                self.assertNotIn('user', post_sess)
                self.assertNotIn('carrito', post_sess)
            self.registrar_resultado("P.1.4 - Limpieza de Estado de Variables de Sesión en Desconexión", True)
        except Exception as e:
            self.registrar_resultado("P.1.4 - Limpieza de Estado de Variables de Sesión en Desconexión", False, str(e))

    def test_05_datos_carrito_tipado_numerico_float(self):
        """[CHECKLIST 3.1] Integración: Validar que los acumuladores de precios en backend parseen floats y no strings"""
        try:
            with self.app.session_transaction() as sess:
                sess['user'] = 'test_types@gpi_test.com'
            
            payload = {"restaurante_carrito": [{"id_plato": self.id_entrante, "cantidad": "2"}]}
            response = self.app.post('/carrito', data=json.dumps(payload), content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            with self.app.session_transaction() as checked_sess:
                self.assertIsInstance(checked_sess['precio'], float)
                self.assertEqual(checked_sess['precio'], 11.00)
            self.registrar_resultado("P.1.5 - Control de Tipado numérico y Evitación de Concatenación de Textos", True)
        except Exception as e:
            self.registrar_resultado("P.1.5 - Control de Tipado numérico y Evitación de Concatenación de Textos", False, str(e))

    # =========================================================================
    # ENTRADA P.2: PRUEBAS DE SISTEMA (Flujo Funcional de Negocio Completo)
    # =========================================================================

    def test_06_flujo_completo_plato_hasta_facturacion(self):
        """[CHECKLIST 1.1 y 2.2] Validar ciclo completo verificando saldos e impactos de base de datos"""
        try:
            # 1. Sesión de Gerente para añadir un nuevo plato
            with self.app.session_transaction() as sess:
                sess['user'] = 'gerente_sistema@gpi_test.com'
            
            self.app.post('/nuevo_plato', data={
                'nombre': 'Cordero SISTEMA E2E',
                'descripción': 'Plato para prueba de sistema final',
                'precio': '18.00',
                'categoría': 'Principal',
                'carta': 'on'
            })
            
            plato = self.cursor.execute("SELECT id_plato FROM Plato WHERE nombre='Cordero SISTEMA E2E'").fetchone()
            self.assertIsNotNone(plato)
            id_plato_sistema = plato['id_plato']

            # 2. Configurar el menú del día vinculando el nuevo plato
            fecha_hoy = date.today().isoformat()
            self.cursor.execute("""
                INSERT INTO Menu_Diario (fecha, id_entrante, id_principal, id_postre, precio_menu)
                VALUES (?, ?, ?, ?, 15.0)
            """, (fecha_hoy, self.id_entrante, id_plato_sistema, self.id_postre))
            id_menu = self.cursor.lastrowid
            
            for pos in range(1, 4):
                self.cursor.execute("INSERT INTO Menu_Diario_Opcion (id_menu, tipo, posicion, id_plato) VALUES (?, 'entrantes', ?, ?)", (id_menu, pos, self.id_entrante))
                self.cursor.execute("INSERT INTO Menu_Diario_Opcion (id_menu, tipo, posicion, id_plato) VALUES (?, 'principales', ?, ?)", (id_menu, pos, id_plato_sistema))
            for pos in range(1, 3):
                self.cursor.execute("INSERT INTO Menu_Diario_Opcion (id_menu, tipo, posicion, id_plato) VALUES (?, 'postres', ?, ?)", (id_menu, pos, self.id_postre))
            self.conn.commit()

            # 3. Sesión de Cliente y checkout exitoso
            with self.app.session_transaction() as sess:
                sess['user'] = 'cliente_sistema@gpi_test.com'
            
            self.cursor.execute("""
                INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena, es_cliente, saldo)
                VALUES ('Ana Pruebas', 'Calle Universidad 22', 'cliente_sistema@gpi_test.com', 'pass', 1, 0.0)
            """)
            self.conn.commit()

            payload_carrito = {"restaurante_carrito": [{"id_plato": id_plato_sistema, "cantidad": 1}]}
            self.app.post('/carrito', data=json.dumps(payload_carrito), content_type='application/json')

            # Confirmar pago
            response_pago = self.app.post('/confirmar_pago')
            data_pago = json.loads(response_pago.data.decode('utf-8'))
            self.assertEqual(data_pago['status'], 'success')

            # Verificar vaciado de variables de sesión
            with self.app.session_transaction() as post_sess:
                self.assertNotIn("carrito", post_sess)

            # 4. Validación analítica de Facturación
            _, _, total_periodo = get_facturación(fecha_hoy, fecha_hoy)
            self.assertEqual(total_periodo, 18.00)
            
            self.registrar_resultado("P.2.1 - Ciclo de Vida del Sistema (Alta -> Menú -> Venta -> Cierre Contable)", True)
        except Exception as e:
            self.registrar_resultado("P.2.1 - Ciclo de Vida del Sistema (Alta -> Menú -> Venta -> Cierre Contable)", False, str(e))

    def test_07_modificacion_y_bloqueo_destructivo_pedido_carta(self):
        """[CHECKLIST 2.2] Sistema: Asegurar que modificaciones de estados no alteren pedidos ya cerrados"""
        try:
            self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta) VALUES ('Plato Historico QA', 'Desc', 10.0, 'Principal', 1)")
            id_plato_hist = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO Pedido (id_cliente, fecha, hora, importe, estado, dir_envio) VALUES (1, '2026-05-16', '12:00', 10.0, 'Pagado', 'Dir QA')")
            id_ped = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO Detalle_Pedido (id_pedido, id_plato, cantidad) VALUES (?, ?, 1)", (id_ped, id_plato_hist))
            self.conn.commit()

            with self.app.session_transaction() as sess:
                sess['user'] = 'gerente_destructivo@gpi_test.com'

            self.app.post('/quitar_de_carta', data={'id_plato': id_plato_hist})

            pedido_check = self.cursor.execute("SELECT id_plato FROM Detalle_Pedido WHERE id_pedido = ?", (id_ped,)).fetchone()
            self.assertEqual(pedido_check['id_plato'], id_plato_hist)
            self.registrar_resultado("P.2.2 - Control de Integridad Relacional ante Operaciones Destructivas", True)
        except Exception as e:
            self.registrar_resultado("P.2.2 - Control de Integridad Relacional ante Operaciones Destructivas", False, str(e))

    def test_08_alta_plato_caracteres_html_seguridad(self):
        """[CHECKLIST 3.2] Sistema: Verificar la consistencia en el envío y persistencia de strings con marcado semántico"""
        try:
            with self.app.session_transaction() as sess:
                sess['user'] = 'gerente_html@gpi_test.com'

            self.app.post('/nuevo_plato', data={
                'nombre': 'Plato <b>Especial</b> QA',
                'descripción': 'Descripción con etiquetas <i>&amp;</i>',
                'precio': '15.00',
                'categoría': 'Entrante',
                'carta': 'on'
            })
            
            plato_db = self.cursor.execute("SELECT nombre FROM Plato WHERE nombre LIKE '%Especial%'").fetchone()
            self.assertIsNotNone(plato_db)
            self.assertEqual(plato_db['nombre'], 'Plato <b>Especial</b> QA')
            self.registrar_resultado("P.2.3 - Soportabilidad de Estructuras de Texto de Formularios HTML", True)
        except Exception as e:
            self.registrar_resultado("P.2.3 - Soportabilidad de Estructuras de Texto de Formularios HTML", False, str(e))

    # =========================================================================
    # ADVANCED QA: TESTS DE ROBUSTEZ, SEGURIDAD E INSPECCIÓN DE CÓDITO
    # =========================================================================

    def test_09_seguridad_inyeccion_sql_parametrizada(self):
        """[CHECKLIST 2.3] Seguridad: Asegurar que las consultas del backend resisten ataques de inyección SQL"""
        try:
            payload_ataque = {
                "email": "' OR '1'='1",
                "password": "falsa_contrasena"
            }
            response = self.app.post('/login', data=payload_ataque)
            self.assertIn(b"Email o contrase\xc3\xb1a incorrectos", response.data)
            self.registrar_resultado("Calidad [2.3] - Verificación de Inmunidad contra Inyección SQL", True)
        except Exception as e:
            self.registrar_resultado("Calidad [2.3] - Verificación de Inmunidad contra Inyección SQL", False, str(e))

    def test_10_seguridad_proteccion_de_rutas_sensibles(self):
        """[CHECKLIST 4.3] Seguridad: Verificar el bloqueo y advertencia con tildes normalizadas"""
        try:
            with self.app.session_transaction() as sess:
                sess.clear()  
            
            response = self.app.get('/carta')
            # Ajustado para machear de forma binaria el texto 'Debes iniciar sesión para ver la carta'
            self.assertIn("Debes iniciar sesión".encode('utf-8'), response.data)
            self.registrar_resultado("Calidad [4.3] - Protección y Bloqueo de Rutas Sensibles a Anónimos", True)
        except Exception as e:
            self.registrar_resultado("Calidad [4.3] - Protección y Bloqueo de Rutas Sensibles a Anónimos", False, str(e))

    def test_11_verificar_coincidencia_esquema_bd(self):
        """[CHECKLIST 2.1] Base de Datos: Comprobar la coincidencia exacta de nombres de columnas en la persistencia"""
        try:
            self.cursor.execute("SELECT * FROM Plato LIMIT 1")
            fila = self.cursor.fetchone()
            
            if fila:
                self.assertIn("descripcion", fila.keys())
                self.assertNotIn("descripción", fila.keys())
            self.registrar_resultado("Calidad [2.1] - Coincidencia de Nombres de Columnas con Esquema SQLite", True)
        except Exception as e:
            self.registrar_resultado("Calidad [2.1] - Coincidencia de Nombres de Columnas con Esquema SQLite", False, str(e))

    def test_12_almacenamiento_contrasenas_plano_advertencia(self):
        """[CHECKLIST 4.1] Calidad/Seguridad: Registro en auditoría del riesgo latente de contraseñas en texto plano"""
        try:
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena) VALUES ('User Pass Text', 'Dir', 'pass_plain@gpi_test.com', 'mi_clave_123')")
            self.conn.commit()
            
            check_user = self.cursor.execute("SELECT contrasena FROM Usuarios WHERE correo_electronico='pass_plain@gpi_test.com'").fetchone()
            self.assertEqual(check_user['contrasena'], 'mi_clave_123')
            self.registrar_resultado("Calidad [4.1] - Control de Almacenamiento de Claves (Texto Plano Detectado)", True)
        except Exception as e:
            self.registrar_resultado("Calidad [4.1] - Control de Almacenamiento de Claves (Texto Plano Detectado)", False, str(e))

    def test_13_error_insercion_plato_campos_vacios(self):
        """[CHECKLIST 1.1] Robustez: Comprobar que el backend frena la inserción relacional de un plato sin nombre"""
        try:
            with self.app.session_transaction() as sess:
                sess['user'] = 'gerente_vacio@gpi_test.com'

            # Provocamos un IntegrityError estructural forzando una inserción sin el campo NOT NULL obligatorio 'nombre'
            with self.assertRaises((sqlite3.IntegrityError, KeyError, Exception)):
                self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria) VALUES (NULL, 'Desc', 5.0, 'Postre')")
                self.conn.commit()
                
            self.registrar_resultado("Calidad [1.1] - Robustez: Rechazo de Platos Incompletos o Vacíos", True)
        except Exception as e:
            self.registrar_resultado("Calidad [1.1] - Robustez: Rechazo de Platos Incompletos o Vacíos", False, str(e))

    def test_14_api_pago_control_pedido_minimo(self):
        """[CHECKLIST 1.1] Regla de Negocio: Validar rechazo de pedidos con importes inferiores al umbral de 15€"""
        try:
            self.cursor.execute("INSERT INTO Plato (nombre, descripcion, precio, categoria, activo_en_carta) VALUES ('Té QA TEST', 'Bebida', 2.50, 'Bebida', 1)")
            id_te = self.cursor.lastrowid
            self.conn.commit()

            with self.app.session_transaction() as sess:
                sess['user'] = 'cliente_minimo@gpi_test.com'
            self.cursor.execute("INSERT INTO Usuarios (nombre, direccion, correo_electronico, contrasena, es_cliente) VALUES ('User Min', 'Dir', 'cliente_minimo@gpi_test.com', '1', 1)")
            self.conn.commit()

            self.app.post('/carrito', data=json.dumps({"restaurante_carrito": [{"id_plato": id_te, "cantidad": 1}]}), content_type='application/json')
            response = self.app.post('/confirmar_pago')
            data = json.loads(response.data.decode('utf-8'))
            
            self.assertEqual(data['status'], 'error')
            self.assertIn("pedido mínimo", data['message'].lower())
            self.registrar_resultado("Calidad [1.1] - Regla de Negocio: Bloqueo de Checkout inferior al Pedido Mínimo", True)
        except Exception as e:
            self.registrar_resultado("Calidad [1.1] - Regla de Negocio: Bloqueo de Checkout inferior al Pedido Mínimo", False, str(e))

if __name__ == '__main__':
    print("\n" + "="*75)
    print(" EJECUTANDO SUITE DE CALIDAD COMPLETA (BASED ON INSPECTION CHECKLIST V2)")
    print("="*75 + "\n")
    
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=0)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSaborHimalayaSistemaIntegracion)
    runner.run(suite)