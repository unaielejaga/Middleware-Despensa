from distutils.log import error
import socket
import time
from datetime import date, datetime, timedelta
from weakref import ref
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

#Declaración del diccionario de productos según el número de serie
num_serie_dic = {
    '954819236': 'Leche Semidesnatada'
}

#Declaración del diccionario de fabricantes según su código
fabricante_dic = {
    '1425751': 'Kaiku'
}

#Declaración del diccionario de clases de productos según su código
clase_dic = {
    '236786': 'Lácteos'
}

#Declaración del diccionario de distribuidores según su código
distribuidor_dic = {
    '01' : 'Eroski',
    '02' : 'Mercadona',
    '03' : 'BM'
}

#Declaración del diccionario de referencias de distribuidores según su código
distridb_dic = {
    '01' : 'EROS',
    '02' : 'MERC',
    '03' : 'BM'
}

#Definición de las credenciales de Firebase
cred = credentials.Certificate('firebase-sdk.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://my-app-20856-default-rtdb.europe-west1.firebasedatabase.app/'
})

#Referencia del árbol JSON de la despensa según el número de serie de la despensa
ref_despensa = db.reference('/despensas/45654132')
#Referncia del árbol JSON de los distribuidores
url_distr = '/distribuidores/'

#Configuración del socket para la comunicación con el lector RFID
IP_lector = '192.168.1.238'
puerto = 7086
buffer = 21
array_epc = []
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(10)

#Declaración de variables globales del sistema
envio_productos_despensa = {} #Diccionario de productos de la despensa
envio_productos_distri_EROS = {} #Diccionario de productos de Eroski
envio_productos_distri_MERC = {} #Diccionario de productos de Mercadona
envio_productos_distri_BM = {} #Diccionario de productos de BM
envio_productos_despensa_anterior = {} #Estado anterior de la despensa
num_producto = 0 #Número de productos leídos

#Funciónencargada de la conexión con el lector, lectura de etiquetas, 
#detención de lectura y desconexión con el lector RFID
def lectura_codigos(num_producto):

    #Envío de trama para la conexión con el lector
    trama1 = '55 01 AB 03 20 00 01 76 CE'
    mensaje1 = bytes.fromhex(trama1)
    s.send(mensaje1)
    recibe1 = s.recv(buffer) #Respuesta del lector al middleware
    print('Trama recibida (conexión): ', recibe1.hex())

    #Envío de trama de lectura al lector
    trama2 = '55 02 AB 04 91 01 01 00 99 4D'
    mensaje2 = bytes.fromhex(trama2)
    s.send(mensaje2)

    start_time = time.time()
    array_epc = []

    while True: #Deberá de estar leyendo durante 10s
        global buffer_epc
        buffer_epc = 25
        current_time = time.time()
        elapsed_time = current_time - start_time

        if elapsed_time > 10: #Si el tiempo trasncurrido es mayor de 10s sale del bucle
            break
        try:
            recibido_epc = s.recv(buffer_epc)
            array_epc.append(recibido_epc.hex()) #Las tramas recibidas por el lector se guardan en un array
        except s.timeout:
            break  
        
    final_epc = list(set(array_epc)) #Se filtran las tramas duplicadas del array anterior

    #Envío de trama para deternar la lectura al lector
    trama3 = '55 03 AB 02 20 00 DC 90'
    mensaje3 = bytes.fromhex(trama3)
    s.send(mensaje3)
    recibe3 = s.recv(buffer)
    print('Trama recibida (stop leer): ', recibe3.hex())

    #Envío e trama para desconexión con el lector
    trama4 = '55 04 AB 03 20 00 01 6E CB'
    mensaje4 = bytes.fromhex(trama4)
    s.send(mensaje4)
    recibe4 = s.recv(buffer)
    print('Trama recibida (desconexión): ', recibe4.hex())
    
    #Procesado de cada una de las tramas leidas por el la antena RFID
    print('Codigos leidos: ')
    for epc in final_epc:
        epc = epc[:-4].replace('5502ab13910001', '') #Se eliminan el prefijo y sufijo de la trama para obtener el código EPC
        print('\n', epc + '\n')
        procesado(epc, num_producto, envio_productos_despensa) #Identificación del código EPC
        num_producto += 1
    print('\n')
    comprobacion_dic(envio_productos_despensa) #Comprbación del estado de la despensa con el estado anterior
    envio_datos(ref_despensa, envio_productos_despensa) #Envío de los datos recogidos a Firebase


#Función encargada de la identificación del producto en base a su código EPC,
#y construcción de los distintos diccionarios para su posterior envio
def procesado(epc, num_producto, envio_productos_despensa):
    estado = '' #Declaración del estado del producto
    epc = epc.replace('e2', '') #Eliminación de la versión EPC del código
    fabricante = epc[0:7] #Obtención del fabricante del código EPC
    clase = epc[7:13] #Obtención de la clase del producto del código EPC
    num_serie = epc[13:22] #Obtención del producto del código EPC
    distribuidor = epc[22:24] #Obtención del distribuidor del código EPC
    fecha_cad = epc[24:26] + '/' + epc[26:28] + '/20' + epc[28:30] #Obtención de la fecha de caducidad del código EPC

    print(fabricante, clase, num_serie, distribuidor, fecha_cad, '\n')
    
    #Comprobación de si las variables obtenidas anteriormente existen en los diccionarios
    if fabricante in fabricante_dic:
        if clase in clase_dic:
            if num_serie in num_serie_dic:
                if distribuidor in distribuidor_dic:
                    print(fabricante_dic[fabricante], clase_dic[clase], num_serie_dic[num_serie], distribuidor_dic[distribuidor], fecha_cad, '\n')
                    #Creación del diccionario de producto de los distribuidores
                    dict_producto_distri = { 
                        'ingre'+str(num_producto):{
                            'fechacad': fecha_cad,
                            'fechacompra': '0/0/0',
                            'fechacons': '0/0/0',
                            'marca': fabricante_dic[fabricante],
                            'nombre': num_serie_dic[num_serie]
                        }
                    }

                    #Introducción del producto en su diccionario de distribuidor correspondiente
                    if(distridb_dic[distribuidor] == 'EROS'):
                        envio_productos_distri_EROS.update(dict_producto_distri)
                    elif(distridb_dic[distribuidor] == 'MERC'):
                        envio_productos_distri_MERC.update(dict_producto_distri)
                    elif(distridb_dic[distribuidor] == 'BM'):
                        envio_productos_distri_BM.update(dict_producto_distri)

                    #Cálculo del estado del producto
                    fecha_cad_formateado = datetime.strptime(fecha_cad, "%d/%m/%Y")
                    fecha_hoy = date.today()
                    if fecha_cad_formateado.date() < fecha_hoy:
                        estado = 'malo'
                    elif (fecha_cad_formateado.date() - timedelta(days=3)) > fecha_hoy:
                        estado = 'bueno'
                    else:
                        estado = 'medio'

                    #Creación del diccionario de producto de la despensa
                    dict_producto_despensa = {
                        'ingre'+str(num_producto):{
                            'distribuidor': distribuidor_dic[distribuidor],
                            'estado': estado,
                            'fechacad': fecha_cad,
                            'fechacons': '0/0/0',
                            'marca': fabricante_dic[fabricante],
                            'nombre': num_serie_dic[num_serie]
                        }
                    }
                    #Introducción del proddcuto en el diccionario de la despensa
                    envio_productos_despensa.update(dict_producto_despensa)
                else:
                    print('Distribuidor no existe')
            else:
                print('Número de serie no existe')
        else:
            print('Clase de producto no existe')
    else:
        print('Fabricante no existe')
    

#Función encargada de la comprobación del estado anterior de la despensa,
#para añadir la fecha de compra y consumición del producto
def comprobacion_dic(envio_productos_despensa):

    hoy = datetime.now().strftime("%d/%m/%Y") #Declaración de la fecha de hoy

    common_keys = [key for key in envio_productos_despensa if key in envio_productos_despensa_anterior] #Buscamos si hay diferencias entre los diccionarios
    
    #Si hay un nuevo producto, se le añade la fecha de compra a los diccionarios de los distribuidores
    if(len(envio_productos_despensa) > len(envio_productos_despensa_anterior)): 
        for key in envio_productos_despensa.keys():
            if key not in common_keys:
                if(envio_productos_despensa[key]["distribuidor"] == 'Eroski'):
                    envio_productos_distri_EROS[key]["fechacompra"] = hoy
                elif(envio_productos_despensa[key]["distribuidor"] == 'Mercadona'):
                    envio_productos_distri_MERC[key]["fechacompra"] = hoy
                elif(envio_productos_despensa[key]["distribuidor"] == 'BM'):
                    envio_productos_distri_BM[key]["fechacompra"] = hoy
    
    #Si falta un producto producto, se le añade la fecha de consumición a los diccionarios de los distribuidores
    elif(len(envio_productos_despensa) < len(envio_productos_despensa_anterior)):
        for key in envio_productos_despensa_anterior.keys():
            if key not in common_keys:
                if(envio_productos_despensa_anterior[key]["distribuidor"] == 'Eroski'):
                    envio_productos_distri_EROS[key]["fechacons"] = hoy
                elif(envio_productos_despensa_anterior[key]["distribuidor"] == 'Mercadona'):
                    envio_productos_distri_MERC[key]["fechacons"] = hoy
                elif(envio_productos_despensa_anterior[key]["distribuidor"] == 'BM'):
                    envio_productos_distri_BM[key]["fechacons"] = hoy

#Función encargada del envío de datos a las distintas referencias de Firebase
def envio_datos(ref_despensa, envio_productos_despensa):
    envio_productos_despensa_anterior = envio_productos_despensa.copy() #Se guarda el estado anterior de la despensa
    ref_despensa.set(envio_productos_despensa) #Se envía la información de la despensa a la referencia de la despensa
    db.reference(url_distr+'EROS').set(envio_productos_distri_EROS) #Envío de los datos de Eroski a la referencia de Eroski
    db.reference(url_distr+'MERC').set(envio_productos_distri_MERC) #Envío de los datos de Mercadona a la referencia de Mercadona
    db.reference(url_distr+'BM').set(envio_productos_distri_BM) #Envío de los datos de BM a la referencia de BM
    print('Datos enviados')

#Función encragada del funcionamiento completo del sistema
def funcionamiento_sistema():
    try:
        s.connect((IP_lector, puerto)) #Conexión con el socket del sistema
        print('Conectado')
        lectura_codigos(num_producto) #Declaración para la lectura de las tramas
    except socket.error as msg:
        print("Error: ", msg)

#Función principal del sistema
def main():
    while True: #El ciclo de funcionamiento se repite cada hora
        funcionamiento_sistema()
        time.sleep(3600)

if __name__ == "__main__":
    main()






    



