#Clase definida para el manejo de excepciones ante situaciones incontroladas (por ejemplo acceso a base de datos)

class UnexpectedException(Exception):
    def __init__(self,args):
       super().__init__(args)
        
