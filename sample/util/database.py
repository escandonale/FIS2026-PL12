import sqlite3

from src.util.unexpectedException import UnexpectedException

class DataBase:
    '''
    Encapsula la conexión a una base de datos, la ejecución de consultas y scripts para
    generar el esquema y carga inicial de datos.
    Para cada consulta se abre y cierra la conexión y cursores.
    '''

    #Iniciliza el objeto con el nombre de la base de datos
    def __init__(self, name):
        self.dbname=name
    
    #Ejecuta un script nameFile sobre la base de datos.
    def executeScript (self,nameFile): 
        # Guarda las sentencias del fichero del esquema en un string para ejecutar posteriormente
        with open(nameFile, 'r', encoding='utf-8') as sqlFile:
            sqlScript = sqlFile.read() 
        try:
            conn = sqlite3.connect(self.dbname)
            curs = conn.cursor()
            curs.executescript (sqlScript) #Ejecuta el script
            conn.commit()
            curs.close()
            conn.close()
        except sqlite3.DatabaseError as e:
            raise UnexpectedException(e.args)

    #Ejecuta una consulta de selección (select)
    #El resultado es una lista de diccionarios y cada diccionario es una fila,
    #con keys los nombres de las columnas y values los valores de la columna.
    def executeQuery (self, query, *args):
        try:
            conn = sqlite3.connect(self.dbname)
            #Habilita el manejo de objetos Row para los resultados de la consulta
            conn.row_factory = sqlite3.Row
            curs = conn.cursor()
            curs.execute (query,args)
            #Crea la lista de diccionarios
            results = [dict(row) for row in curs.fetchall()] 
            conn.commit()
            curs.close()
            conn.close()
            return results  
        except sqlite3.DatabaseError as e:
            raise UnexpectedException(e.args)

    #Ejecuta una consulta de actualización (insert, update,...)
    def executeUpdateQuery (self, query, *args, multiple=False):
        if multiple==False:
            try:
                conn = sqlite3.connect(self.dbname)
                curs = conn.cursor()
                curs.execute (query,args)
                conn.commit()
                curs.close()
                conn.close()
            except sqlite3.DatabaseError as e:
                raise UnexpectedException(e.args)
        else:
            try:
                conn = sqlite3.connect(self.dbname) #Para actualizar multiples datos a la vez. Funcionamiento: 
                curs = conn.cursor()
                curs.executemany (query,args[0])
                conn.commit()
                curs.close()
                conn.close()
            except sqlite3.DatabaseError as e:
                raise UnexpectedException(e.args)
