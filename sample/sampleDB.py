import sqlite3
from datetime import date

from util.UnexpectedException import UnexpectedException 

'''
Ejemplos básicos de acceso a una base de datos sqllite

(1) Ejemplo básico de conexión y consulta simple a base de datos
(2) Consultas con parámetros
(3) Manejo de fechas
(4) Scripts para definición del esquema y carga de datos
(5) Otras consultas (JOINS, GROUP BY, UPDATE)

'''

# Ejemplo básico, parte 1, conexión y consulta
def example1Basic ():
    DATABASE = "demoDB.db"  # Nombre de la base de datos local

    try: 
        #Creación de un objeto Connection y Cursor 
        conn = sqlite3.connect(DATABASE)
        curs = conn.cursor()

        #Ejecuta una sentencia SQL para la creación de una tabla con algunas filas
        try: 
            curs.execute("drop table if exists Company")
        except sqlite3.DatabaseError:
            pass  #ignora la excepción, por ejemplo la primera vez que se ejecuta

        curs.execute("create table Company(id int not null primary key, id2 int, name varchar(32))")
        curs.execute("insert into Company(id,id2,name) values(1,null,'Company 1')")
        curs.execute("insert into Company(id,id2,name) values(2,2222,'Company 2')")
        curs.execute("insert into Company(id,id2,name) values(3,3333,'Company 3')")

        #Enviamos los datos a la base de datos
        conn.commit() 
        #Cierra los objetos de la conexión
        curs.close() 
        conn.close() 

        #Consulta de todas las filas de la base de datos mediante sentencias SQL
        conn = sqlite3.connect(DATABASE)
        curs = conn.cursor()

        res = curs.execute("select id,id2,name from Company order by id asc")
        conn.commit() #Enviamos los datos a la base de datos.

        #El resultado es una lista donde cada elemento es una tupla (id,id2,name).
        #Iteramos por la lista, imprimiendo cada fila
        for row in res:
            #cada columna de la tabla
            id=row[0]
            id2=row[1]
            if id2==None:
                id2="Nulo"
            name=row[2]
            print ("example1Basic:",id,id2,name)   
            #También se puede imprimir toda la fila          
            print ("example1Basic:",row) 
        
        curs.close()
        conn.close()
    #En algunas de las operaciones anteriores puede producirse excepciones que se capturan aquí
    #Lo más habitual es capturar esas excepciones de forma individualizada
    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args) 

# Para usar a partir de parte (1)
def crearDB (dbName:str):
    try: 
        #Creación de un objeto Connection y Cursor 
        conn = sqlite3.connect(dbName)
        curs = conn.cursor()

        #Ejecuta una sentencia SQL para la creación de una tabla con algunas filas
        try: 
            curs.execute("drop table if exists Company")
        except sqlite3.DatabaseError:
            pass  #ignora la excepción, por ejemplo la primera vez que se ejecuta
        curs.execute("create table Company(id int not null primary key, id2 int, name varchar(32), startDate varchar(10))")
        #Fechas en sqllite en formato ISO AAAA-MM-DD, que serán almacenadas como strings        
        curs.execute("insert into Company(id,id2,name,startDate) values(1,null,'Company 1','2020-05-03')")
        curs.execute("insert into Company(id,id2,name,startDate) values(3,3333,'Company 3','1999-12-24')")
        curs.execute("insert into Company(id,id2,name,startDate) values(2,2222,'Company 2','2013-01-23')")
        #Enviamos los datos a la base de datos
        conn.commit() 
        #Cierra los objetos de la conexión
        curs.close() 
        conn.close() 
    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args) 

#Ejemplo básico, parte 2, consultas con parámeteros
def example2Parameters ():
    DATABASE = "demoDB.db"    
    crearDB(DATABASE)
    try: 
        conn = sqlite3.connect(DATABASE)
         #Para acceder a los datos de la base de datos por el nombre la columna en vez de por el índice
        conn.row_factory = sqlite3.Row
        curs = conn.cursor()
                
        #Consulta con parámetros donde ? indica un valor que podría ser desconocido hasta la ejecución
        query = "select * from Company where id2 <> ? or id2 is null  order by id asc "
        value = "2222"
        res = curs.execute(query,(value,))
        conn.commit() #Enviamos los datos a la base de datos.
        
        #Dado que utilizamos sqlite3.Row, el resultado ahora es una lista de objetos Row a los que
        #podemos acceder tanto por el nombre de la columna como por el índice
        for row in res:
            print ("example2Parameters:",row[0],row[1],row["name"],row["startDate"])            
        
        curs.close()
        conn.close()
    #En algunas de las operaciones anteriores puede producirse excepciones que se capturan aquí
    #Lo más habitual es capturar esas excepciones de forma individualizada
    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args) 
    
#Ejemplo de manejo de fechas, parte 3
def example3Dates ():
    DATABASE = "demoDB.db"    
    crearDB(DATABASE)
    try: 
        conn = sqlite3.connect(DATABASE)
        curs = conn.cursor() 
       
        query1 = "select * from Company order by id asc" 
        res = curs.execute(query1)
        conn.commit() #Enviamos los datos a la base de datos.
              
        for row in res:
            # Tratamiento de fecha en formato string (sqlite) a date para facilitar manejo (aaa, mm, dd)
            fecha = date.fromisoformat(row[3])  # date.fromisoformat(row["startDate"])
            year = fecha.year
            month = fecha.month
            day = fecha.day
            print ("example3Dates:",fecha,year,month,day)            
        
        #Una consulta de manejo de fecha en la propia sql
        query2 = "select * from Company where startDate between '1990-01-01' and '2014-01-01'"
        res = curs.execute(query2)
        conn.commit() #Enviamos los datos a la base de datos.
      
        for row in res: 
             print ("example3Dates:",row)
        
        #Otra consulta para obtener la antiguedad de la compañia en años
        query3 = "select id, name, date()-startDate as antiguedad from Company where antiguedad>5"
        res = curs.execute(query3)
        conn.commit() #Enviamos los datos a la base de datos.
      
        for row in res: 
             print ("example3Dates:",row)

        curs.close()
        conn.close()
    #En algunas de las operaciones anteriores puede producirse excepciones que se capturan aquí
    #Lo más habitual es capturar esas excepciones de forma individualizada
    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args)

#Ejemplo de definición y ejecución del esquema de BBDD y carga inicial de datos, parte 4
def example4Schemas ():
    DATABASE = "CompanyDB.db"
    SCHEMA = "resources/schema.sql"
    DATA = "resources/data.sql"

    # Guarda las sentencias del fichero del esquema en un string para ejecutar posteriormente
    with open(SCHEMA, 'r') as sqlFile:
         sqlSchema = sqlFile.read() 
         # Idem para la carga de datos
    with open(DATA, 'r') as sqlFile:
        sqlData = sqlFile.read() 

    try:
        conn = sqlite3.connect(DATABASE)
        curs = conn.cursor()
        print ("example4Schemas: Ejecutando script ", SCHEMA)
        curs.executescript (sqlSchema) #Ejecuta el script con el esquema
        print ("example4Schemas: Ejecutando script ", DATA)
        curs.executescript (sqlData) #Ejecuta el script con la carga de datos
        
        #Consultas para comprobar lo anterior
        query1 = "select * from Company"
        query2 = "select * from Employee"
        res = curs.execute(query1)
        for row in res: 
                print ("example4Schemas-Company:",row)
        
        res = curs.execute(query2)
        for row in res: 
                print ("example4Schemas-Employee:",row)
        conn.commit()
    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args)
    
    curs.close()
    conn.close()

#Para utilizar en el ejemplo siguiente
def ejecutaScript (nameFile): 
    DATABASE = "CompanyDB.db"
   
    # Guarda las sentencias del fichero del esquema en un string para ejecutar posteriormente
    with open(nameFile, 'r') as sqlFile:
         sqlScript = sqlFile.read() 
    
    try:
        conn = sqlite3.connect(DATABASE)
        curs = conn.cursor()
        curs.executescript (sqlScript) #Ejecuta el script 
               
    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args)
    
    curs.close()
    conn.close()

def example5Otras ():
    DATABASE = "CompanyDB.db"
    ejecutaScript("resources/schema.sql") #Crea el esquema
    ejecutaScript("resources/data.sql") #Carga incial de datos
    try: 
        conn = sqlite3.connect(DATABASE)
        curs = conn.cursor() 
        # JOINs -Listar compañias y todos sus empleados 
        query1="""select Company.id, Company.name, Employee.id, Employee.name 
                  from Company inner join Employee on Company.id=Employee.idCompany
                  order by Company.id asc
               """
        res = curs.execute(query1)
        for row in res: 
            print ("example5Otras - INNER JOIN:",row)
        
        # GROUP BY -Número de empleados de cada compañia 
        query2="""select Company.name, count(Employee.id)
                  from Company left join Employee on Company.id=Employee.idCompany
                  group by (Company.id)
               """
        res = curs.execute(query2)
        for row in res: 
            print ("example5Otras - GROUP BY:",row)

        # HAVING - Compañias con salario medio de sus empleados mayor que 1200 si tienen al menos 3 empleados
        query3="""select Company.name, avg(Employee.salary) as avgSalary
                  from Company inner join Employee on Company.id=Employee.idCompany
                  group by (Company.id)
                  having avgSalary >= 1200 and count(Employee.id)>=3
                """
        res = curs.execute(query3)
        for row in res: 
            print ("example5Otras - HAVING:",row)

        # UPDATE - Actualización de salario 10%s de los empleados que tienen salario inferior a 2000
        query4="""update Employee 
                  set salary = salary + salary*0.1
                  where salary <2000
                """
        res = curs.execute(query4)
        res = curs.execute("select * from Employee")
        for row in res: 
            print ("example5Otras - UPDATE (Employee new salary):",row)

        conn.commit()

    except sqlite3.DatabaseError as e:
       raise UnexpectedException(e.args)
    
    curs.close()
    conn.close()
    
#example1Basic()
#example2Parameters()
#example3Dates()
#example4Schemas()
#example5Otras()
