from src.util.database import DataBase
from datetime import datetime
from prettytable import PrettyTable, DOUBLE_BORDER
import sys

class transversales:

    def __init__ (self):
        self.db = DataBase ("Musica.db")
        self.user = None

    def get_categorias(self, idCancion=False, printear=True) ->list[str]:
        
        if idCancion:
            query = """SELECT g.nombre FROM genero g JOIN Cancion_genero cg
                        WHERE idCancion=? AND g.idGenero=cg.idGenero"""
            result = self.db.executeQuery(query, idCancion)


        else:
            query = """SELECT nombre FROM genero ORDER BY nombre"""
            result = self.db.executeQuery(query)
        categorias = [row["nombre"] for row in result]
        
        if printear:
            print("\n")
            print("=" * 70)
            print("CATEGORÍAS DISPONIBLES:")
            for categoria in categorias:
                print(f"- {categoria}")
            print("=" * 70)
        return categorias
    


    def get_nombres_canciones(self):
        query = """
        SELECT DISTINCT titulo, idCancion
        FROM Cancion
        ORDER BY titulo
        """
        result = self.db.executeQuery(query)
        titulos = [row["titulo"] for row in result]
        ids = [row["idCancion"] for row in result]
        dic_id_tit = dict(zip(ids, titulos))
        dic_tit_id = dict(zip(titulos, ids))
        return dic_id_tit, dic_tit_id


    def get_cancion(self, titulo, idCancion=None):
        if idCancion==None:
            query = """
            SELECT idCancion, titulo, stock, precio, artista
            FROM Cancion where titulo = ?
            """
            result = self.db.executeQuery(query, titulo) #Si solo hay una canción con ese título
        else:
            query = """
            SELECT idCancion, titulo, stock, precio, artista
            FROM Cancion where titulo = ? AND idCancion = ?
            """
            result = self.db.executeQuery(query, titulo, idCancion) #Si hay más de una con el mismo título          
        return result

    def get_usuario(self):
        query = """
        SELECT nombre_usuario, contrasena
        FROM Usuario
        """
        return self.db.executeQuery(query)

    def insertar_usuario(self, user, passwd, fecha_alta):
        query = """
        INSERT INTO Usuario (nombre_usuario, contrasena, fecha_alta)
        VALUES (?, ?, ?)
        """
        self.db.executeUpdateQuery(query, user, passwd, fecha_alta)

    def get_idUltimoGenero(self): #Funcion auxiliar para obtener el siguiente idGenero disponible
        query = """
        SELECT idGenero FROM Genero ORDER BY idGenero ASC
        """
        result = self.db.executeQuery(query)

        if not result:
            return 1

        ids = [row["idGenero"] for row in result]

        expected_id = 1
        for id_cancion in ids:
            if id_cancion != expected_id:
                return expected_id
            expected_id += 1

        return expected_id
    
    def get_idCancion(self): #Funcion auxiliar para obtener el siguiente idCancion disponible
        query = """
        SELECT idCancion FROM Cancion ORDER BY idCancion ASC
        """
        result = self.db.executeQuery(query)

        if not result:
            return 1

        ids = [row["idCancion"] for row in result]

        expected_id = 1
        for id_cancion in ids:
            if id_cancion != expected_id:
                return expected_id
            expected_id += 1

        return expected_id

    def get_canciones_wishlist(self, id_wishlist):
        query = """
        SELECT C.idCancion, C.titulo
        FROM Cancion C
        JOIN Wishlist_cancion ON C.idCancion = Wishlist_cancion.idCancion
        WHERE idWishlist = ?
        """ 
        result = self.db.executeQuery(query, id_wishlist)
        nombres = [row["titulo"] for row in result]
        id = [row["idCancion"] for row in result]
        dic_id_tit = dict(zip(id, nombres))
        dic_tid_id = dict(zip(nombres, id))
        return dic_id_tit, dic_tid_id

    def get_users_wishlist(self):
        query = """
        SELECT usuario
        FROM Wishlist
        """
        result = self.db.executeQuery(query)
        usuarios = [row["usuario"] for row in result]
        return usuarios

    def set_filtros(self,wishlist=False):
        categorias = transversales.get_categorias(self)
        while True:
            categoria = input("\nIntroducir la categoría deseada (dejar en blanco para verlas todas): ")
            if categoria == "":
                categoria=None
                break
            if categoria not in categorias:
                print(f"\nLa categoría {categoria} no existe. Categorías disponibles: {categorias}")
            else:
                print("Categoría seleccionada: {0}".format(categoria))
                break
            
        print("="*40)
        while True:
            rango_precios = input("Introducir rango de precios (min-max) o dejar en blanco para ver todas: ")
            if rango_precios != "":
                try:
                    min_precio, max_precio = map(float, rango_precios.split('-'))
                    print(f"Rango de precios seleccionado: {min_precio} - {max_precio}")
                    break
                except ValueError:
                    print("\nFormato de rango de precios inválido. Use el formato min-max.\n")
            else: 
                min_precio=max_precio=None
                break

        print("="*40)
        while True:
            rango_fechas = input("Introducir rango de fechas de salida (YYYY-MM-DD / YYYY-MM-DD) o dejar en blanco para ver todas: ")
            if rango_fechas != "":
                try:
                    fecha_inicio_str, fecha_fin_str = map(str.strip, rango_fechas.split('/'))
                    fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")
                    fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d")
                    print(f"Rango de fechas seleccionado: {fecha_inicio_str} - {fecha_fin_str}")
                    break
                except ValueError:
                    print("\nFormato de rango de fechas inválido. Use el formato YYYY-MM-DD - YYYY-MM-DD.")
            else: 
                fecha_inicio=fecha_fin=None
                break
        print("="*40)

        if wishlist==True:
            while True:
                min_agregacion = input("Introducir la fecha mínima de agregación a la wishlist: ")
                if min_agregacion != "":
                    try:
                        fecha_inicio = datetime.strptime(min_agregacion, "%Y-%m-%d")
                        print(f"Fecha mínima de agregación seleccionada: {min_agregacion}")
                        break
                    except ValueError:
                        print("\nFormato de fecha inválido. Use el formato YYYY-MM-DD.")
                else: 
                    fecha_inicio=None
                    break
            print("="*40)
            while True:
                max_agregacion = input("Introducir la fecha mínima de agregación a la wishlist: ")
                if max_agregacion != "":
                    try:
                        fecha_fin = datetime.strptime(max_agregacion, "%Y-%m-%d")
                        print(f"Fecha máxima de agregación seleccionada: {max_agregacion}")
                        break
                    except ValueError:
                        print("\nFormato de fecha inválido. Use el formato YYYY-MM-DD.")
                else: 
                    fecha_fin=None
                    break
            print("="*40)
        else: min_agregacion=max_agregacion=None
        
        return {"categoria":categoria, "min_precio":min_precio, "max_precio":max_precio, "fecha_inicio":fecha_inicio, "fecha_fin":fecha_fin, "min_agregacion":min_agregacion, "max_agregacion":max_agregacion}


    def contar(self, query_base_contar, args, query_filtro=None, stock=False):
        query = f"SELECT COUNT(*) as total {query_base_contar}"

        query += query_filtro if query_filtro else ""

        if stock:
            if query_filtro:
                query += " AND CANCION.stock > 0"
            else:
                query += " WHERE CANCION.stock > 0"
        
        try:
            result = self.db.executeQuery(query, *args)

            if result:
                return result[0]['total']
            else: return 0
        
        except Exception as e:
            print(f"Error en el conteo: {e}")
            return 0

    def visualizar(
        self, id_wishlist=None, categoria=None, min_precio=None, max_precio=None,
        fecha_inicio=None, fecha_fin=None, min_agregacion=None, max_agregacion=None,
        is_wishlist=False
    ):
        if not is_wishlist:
            from src.sisRec.predict import Recomendador
            rec = Recomendador()

        args = []
        conds = []
        query_filtro = ""

        # ======================================================
        # 1) CONSULTA BASE (sin generos)
        # ======================================================

        if not is_wishlist:  # MODO CATÁLOGO
            query_base = """
                SELECT
                    idCancion,
                    titulo,
                    artista,
                    fecha_salida,
                    stock,
                    precio
                FROM CANCION
            """
            query_base_contar = "FROM CANCION"
            col_list = ["idCancion", "titulo", "artista", "fecha_salida", "stock", "precio"]

            # Filtros simples (sin genero)
            if min_precio: conds.append("precio >= ?"); args.append(min_precio)
            if max_precio: conds.append("precio <= ?"); args.append(max_precio)
            if fecha_inicio: conds.append("fecha_salida >= ?"); args.append(fecha_inicio)
            if fecha_fin: conds.append("fecha_salida <= ?"); args.append(fecha_fin)

            # Filtro por categoría (género)
            if categoria:
                conds.append("""
                    idCancion IN (
                        SELECT idCancion
                        FROM Cancion_genero
                        JOIN Genero USING(idGenero)
                        WHERE Genero.nombre = ?
                    )
                """)
                args.append(categoria)

            if conds:
                query_filtro = " WHERE " + " AND ".join(conds)

            query = query_base + query_filtro + " ORDER BY idCancion"

        # ======================================================
        # MODO WISHLIST
        # ======================================================
        else:
            query_base = """
                SELECT 
                    CANCION.idCancion,
                    CANCION.titulo,
                    CANCION.artista,
                    CANCION.fecha_salida,
                    CANCION.stock,
                    CANCION.precio,
                    Wishlist_cancion.fecha_agregado
                FROM Wishlist_cancion
                JOIN CANCION ON Wishlist_cancion.idCancion = CANCION.idCancion
            """
            query_base_contar = """
                FROM Wishlist_cancion
                JOIN CANCION ON Wishlist_cancion.idCancion = CANCION.idCancion
            """
            col_list = [
                "idCancion", "titulo", "artista", "fecha_salida",
                "stock", "precio", "fecha_agregado"
            ]

            # Filtro obligatorio
            conds.append("Wishlist_cancion.idWishlist = ?")
            args.append(id_wishlist)

            # Filtros extra de wishlist
            if min_agregacion: conds.append("fecha_agregado >= ?"); args.append(min_agregacion)
            if max_agregacion: conds.append("fecha_agregado <= ?"); args.append(max_agregacion)

            # Filtros estándar
            if categoria:
                conds.append("""
                    CANCION.idCancion IN (
                        SELECT idCancion
                        FROM Cancion_genero
                        JOIN Genero USING(idGenero)
                        WHERE Genero.nombre = ?
                    )
                """)
                args.append(categoria)

            if min_precio: conds.append("precio >= ?"); args.append(min_precio)
            if max_precio: conds.append("precio <= ?"); args.append(max_precio)
            if fecha_inicio: conds.append("fecha_salida >= ?"); args.append(fecha_inicio)
            if fecha_fin: conds.append("fecha_salida <= ?"); args.append(fecha_fin)

            query_filtro = " WHERE " + " AND ".join(conds)
            query = query_base + query_filtro + " ORDER BY CANCION.idCancion"

        # ======================================================
        # 2) EJECUTAR CONSULTA PRINCIPAL
        # ======================================================
        result = self.db.executeQuery(query, *args)

        if not result:
            print("No se ha encontrado ningún resultado que cumpla los criterios especificados.")
            return

        # ======================================================
        # 3) CONSULTA PARA OBTENER GÉNEROS POR CADA CANCIÓN
        # ======================================================
        q_generos = """
            SELECT Genero.nombre
            FROM Cancion_genero
            JOIN Genero USING(idGenero)
            WHERE idCancion = ?
        """

        # ======================================================
        # 4) IMPRESIÓN
        # ======================================================

        cols = ["ID", "Título", "Artista", "Categoría", "Fecha de salida", "En Stock", "Precio"]

        table = PrettyTable()
        
        if is_wishlist:
            cols.append("Fecha Agregación")
        else: 
            cols.append("Para tí")
            table.align["Para tí"] = "c"

        table.field_names = cols

        table.align["ID"] = "l"
        table.align["Título"] = "l"
        table.align["Artista"] = "l"
        table.align["Categoría"] = "l"
        table.align["En Stock"] = "r"
        table.align["Precio"] = "r"


        if hasattr(result[0], "get"):
            get_func = lambda row, key: row.get(key)
        else:
            get_func = lambda row, key: row[col_list.index(key)]

        ids = []; titulos = []

        for row in result:
            get = lambda k, r=row: get_func(row, k)

            if not get("stock"):
                continue  # Saltar canciones sin stock

            # Obtener géneros
            gen_rows = self.db.executeQuery(q_generos, get("idCancion"))
            generos = ", ".join([g[0] if isinstance(g, tuple) else g["nombre"] for g in gen_rows])

            precio = get("precio")
            try: precio = f"{float(precio):.2f}"
            except: precio = str(precio or "")
            
            # Valores
            fila = [
            str(get("idCancion") or ""),
            str(get("titulo") or ""),
            str(get("artista") or ""),
            generos,
            str(get("fecha_salida") or ""),
            str(get("stock") or ""),
            precio
            ]

            ids.append(get('idCancion')); titulos.append(get('titulo'))
            if is_wishlist:
                fila.append(str(get("fecha_agregado") or ""))
            else:
                puntuacion = rec.predecir_puntuacion(get("idCancion"))
                fila.append("{|♥|}" if puntuacion > 3.5 else "{---}")
                
            
            table.add_row(fila)

        table.set_style(DOUBLE_BORDER)

        if len(table.rows) > 0:
            print(table)
        else:
            print("No se encontraron resultados para mostrar")

        # ======================================================
        # 5) RESÚMENES FINAL
        # ======================================================
        try:
            print(f"Total de canciones: {transversales.contar(self, query_base_contar, args, query_filtro)}")
            print(f"Total en stock: {transversales.contar(self, query_base_contar, args, query_filtro, stock=True)}")
        except Exception as e:
            print(f"Error al generar el resumen de 'contar': {e}")

        input("\n\nPresiona cualquier tecla para continuar...")
        return ids, titulos
