#!/usr/bin/python
# -*- coding: utf-8 -*-

# armoni.py
#       
#  Copyright 2012-2014 Ángel Coto <codiasw@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details (http://www.gnu.org/licenses/gpl.txt)
#  

# Descripcion:
# Este programa verifica periódicamente los archivos que se defina en archivo de
# configuración y emite alertas si han cambiado o no.  Las alerta que se generan
# por defecto son ante cambio de los archivos, pero opcionalmente puede indicarse
# por parámetro de línea de comando que emita alertas ante no cambio.  Las alertas
# son registradas en log también son enviadas por correo.

# Historial de versión
# 1.0.1: Incorpora los destinatarios en el mensaje que se guarda en log de eventos, 
#        relativo a la notificación de cumplimiento de regla
# 1.1.0: * Simplifica el método de comparación
#        * Actualiza el listado de archivos cada vez que se hace ronda de monitoreo.
#          Esto funciona en modalidad de directorio.

import os
import smtplib
from artamiz import calcsum, enllavado
from ConfigParser import SafeConfigParser
from time import sleep, localtime, strftime
from sys import argv
from getpass import getpass
from base64 import standard_b64decode, standard_b64encode
from email.mime.text import MIMEText
from email.Header import Header
from socket import gethostname


### Define la versión del programa
Programa = 'armoni'
Ver = '1.1.0 (beta)'
Copyright = 'Copyright (c) 2012-2014 Angel Coto <codiasw@gmail.com>'
Maquina = gethostname()

### Inicializa variables de mensajes
Error1 = "* Error 1: Error al leer archivo '{0}'."
Error2 = "* Error 2: El campo '{0}' no tiene formáto válido."
Error3 = "* Error 3: '{0}' no es directorio."
Error4 = "* Error 4: '{0}' no es un archivo."
Error5 = "* Error 5: '{0}' no es valor esperado para '{1}'."

MensajeLog1 = "{0}\t{1}\t{2}\t{3}" #Mensaje que se graba en el log de monitoreo

ErrorLog1 = "{0}\tERROR\tError en la comunicación o autenticación con el servidor de correo"
ErrorLog2 = "{0}\tERROR\tError al intentar enviar el mensaje luego de contactar exitosamente al servidor de correo"
ErrorLog3 = "{0}\tERROR\t{1} finalizó debido a errores en archivo de ini"
ErrorLog4 = "{0}\tERROR\t{1} finalizó porque ninguno de los archivos se puede analizar"
ErrorLog5 = "{0}\tERROR\tNo se pudo verificar archivos\t{1}"

EventoLog0 = "{0}\tINFORMATIVO\t{1} inició con éxito con parámetros\t{2}\t{3}\t{4}\t{5}"
EventoLog1 = "{0}\tINFORMATIVO\tSe notificó cumplimiento de la regla\t{1}\t{2}"
EventoLog2 = "{0}\tINFORMATIVO\tNo fue posible notificar cumplimiento de la regla\t{1}"
EventoLog3 = "{0}\tINFORMATIVO\tSe notificó el inicio de {1}\t{2}"
EventoLog4 = "{0}\tINFORMATIVO\tNo fue posible notificar el inicio de {1}"
EventoLog5 = "{0}\tINFORMATIVO\tSe excluyen archivos del monitoreo\t{1}"
EventoLog6 = "{0}\tINFORMATIVO\tInicio de ciclo de verificación"
EventoLog7 = "{0}\tINFORMATIVO\tFin de ciclo de verificación"
EventoLog100 = "{0}\tINFORMATIVO\t{1} fue detenido"


class Correo:
	
	def __init__(self, Servidor, Puerto, Cuenta, Pwd = None):
		self.Cuenta = Cuenta
		self.Pwd = Pwd
		self.Servidor = Servidor
		self.Puerto = Puerto
		self.Asunto = ''
		self.Mensaje = ''
	
	def CreaMensaje(self, Mensaje): #Método genérico para cualquier mensaje preelaborado
		self.Mensaje = Mensaje
		
	def CreaAsunto(self, Asunto): #Método genérico para cualquier asunto preelaborado 
		self.Asunto = Asunto

	def CreaAsuntoLog(self, CausaAlerta): #Método específico para crear el asunto de correo de alerta
		if CausaAlerta == 'cambio':
			self.Asunto = Programa + '@' + Maquina + ': ** Reportando cambios en archivos'
		else:
			self.Asunto = Programa + '@' + Maquina + ': ** Reportando archivos que no han cambiado'
	
	def CreaMensajeLog(self, Archivos, CausaAlerta, Intervalo, Hora): #Método específico para crear mensaje de correo de alerta
		self.Mensaje = '------------ Reporte de ' + Programa + '@' + Maquina + ' en fecha ' + Hora + ' ------------\n\n'
		if CausaAlerta == 'cambio':
			self.Mensaje =  self.Mensaje + 'Se detectó que los siguientes archivos se modificaron en los últimos ' + str(Intervalo) + ' minutos:\n\n'
		else:
			self.Mensaje =  self.Mensaje + 'Se detectó que los siguientes archivos no han cambiado en los últimos ' + str(Intervalo) + ' minutos:\n\n'
		Parrafo = ''
		for Archivo in Archivos:
			Parrafo = Parrafo + ' * ' + Archivo + '\n'
		self.Mensaje = self.Mensaje + Parrafo + '\n' + Programa + '-' + Ver
		
	def EnviarCorreo(self, Remitente, Destinatarios): #Método genérico para enviar correo
		# Construye el mensaje simple (texto y sin adjunto)
		Asunto = self.Asunto.decode('utf-8')
		Asunto = Header(Asunto,'utf-8')
		Mensaje = MIMEText(self.Mensaje,'plain','utf-8')
		Mensaje['From'] = Remitente
		Mensaje['To'] = Remitente
		Mensaje['Subject'] = Asunto
		Mensaje = Mensaje.as_string()

		# Conecta con el servidor de correo
		if self.Servidor == 'smtp.gmail.com':
			try:
				mailServer = smtplib.SMTP(self.Servidor,self.Puerto)
				mailServer.starttls()
				mailServer.login(self.Cuenta, standard_b64decode(self.Pwd))
			except:
				return 1
		else:
			try:
				mailServer = smtplib.SMTP(self.Servidor, self.Puerto)
			#	mailServer.set_debuglevel(True) #Usar en caso de requerir ver comunicación con server
			except:
				return 1
		
		# Envía el mensaje
		try:
			mailServer.sendmail(Remitente, Destinatarios, Mensaje)
			return 0
		except:
			return 2
		finally:
			mailServer.quit()

class Log:
	
	def __init__(self, Archivo):
		self.Archivo = Archivo
		self.TamanoMaximo = 1048576
	
	def GrabaRegistroLog(self, Registro):
		ArchivoLog = open(self.Archivo, 'a')
		ArchivoLog.write(Registro + '\n')
		ArchivoLog.close()
		if self.VerificaTamano():
			self.RenombraLog()
		
	def VerificaTamano(self):
		if os.path.getsize(self.Archivo) >= self.TamanoMaximo:
			return True
		else:
			return False
		
	def RenombraLog(self):
		Parte1 = os.path.splitext(os.path.basename(self.Archivo))[0]
		Extension = os.path.splitext(os.path.basename(self.Archivo))[1]
		Complemento = hora = strftime("_%Y%m%d_%H%M%S", localtime())
		Nuevonombre = Parte1 + Complemento + Extension
		os.rename(self.Archivo,Nuevonombre)

class Parametros:
	
	def __init__(self, Ini, TipoObjeto):
		self.ArchivoIni = Ini
		self.Error = False
		
		if os.path.isfile(self.ArchivoIni):
			if TipoObjeto == 'directorio':
				self.Directorios = self.LeeLista('datos_monitoreo','directorios')
				if self.Directorios <> False:
					self.ValidaDirectorios()
			else:
				self.Archivos = self.LeeLista('datos_monitoreo','archivos')
				if self.Archivos <> False:
					self.ValidaArchivos()
			self.MinutosIntervalo = self.LeeNumerico('datos_monitoreo','minutos_intervalo')
			self.Intervalo = self.MinutosIntervalo * 60
			self.Servidor = self.LeeString('datos_servidor_correo', 'servidor')
			self.RequiereAutenticacion = self.LeeString('datos_servidor_correo','requiere_autenticacion', ['si', 'no'])
			self.Puerto = self.LeeNumerico('datos_servidor_correo', 'puerto')
			self.Cuenta = self.LeeString('datos_servidor_correo', 'cuenta')
			self.De = self.LeeString('datos_correo', 'de')
			self.Para = self.LeeLista('datos_correo', 'para')
			self.ParaAdmin = self.LeeLista('datos_correo', 'para_admin')
		else:
			print(error1.format(self.ArchivoIni))
			self.Error = True
		
	def ValidaDirectorios(self):
		for Directorio in self.Directorios:
			if not os.path.isdir(Directorio):
				print(Error3.format(Directorio))
				self.Error = True
		if self.Error:
			return False
		else:
			return True
						
	def ValidaArchivos(self):
		for Archivo in self.Archivos:
			if not os.path.isfile(Archivo):
				print(Error4.format(Archivo))
				self.Error = True
		if self.Error:
			return False
		else:
			return True

	def LeeLista(self, seccion, opcion):
		parser = SafeConfigParser()
		parser.read(self.ArchivoIni)
		valor = parser.get(seccion,opcion).strip()
		cadena = ''
		Lista = []
		if valor.strip() <> '':
			for caracter in valor:
				if caracter <> ';':
					cadena = cadena + caracter
				else:
					Lista.append(cadena.strip())
					cadena = ''
			Lista.append(cadena.strip())
			return Lista
		else:
			print(Error2.format(opcion))
			self.Error = True
			return False
	
	def LeeString(self, seccion, opcion, valores = None):
		parser = SafeConfigParser()
		parser.read(self.ArchivoIni)
		MiString = parser.get(seccion,opcion)
		MiString = MiString.strip()
		if MiString <> '':
			ValorValido = True
			if valores <> None:
				if MiString not in valores:
					ValorValido = False
			if ValorValido:
				return MiString
			else:
				print(Error5.format(MiString,opcion))
				self.Error = True
				return False
		else:
			print(Error2.format(opcion))
			self.Error = True
			return False
	
	def LeeNumerico(self, seccion, opcion):
		parser = SafeConfigParser()
		parser.read(self.ArchivoIni)
		Numero = 0
		try:
			Numero = int(parser.get(seccion,opcion))
			return Numero
		except:
			print(Error2.format(opcion))
			self.Error = True
			return False

class Monitor:

	def __init__(self):
		self.Archivos = []
		self.ArchivosError = []
		
	def ArchivoVerificable(self, Archivo):
		if os.path.isfile(Archivo):
			if os.access(Archivo, os.R_OK):
				if not enllavado(Archivo):
					Verificable = True
				else:
					Verificable = False
					self.ArchivosError.append([Archivo, 'enllavado'])
			else:
				Verificable = False
				self.ArchivosError.append([Archivo, 'sinpermisolectura'])
		else:
			Verificable = False
			self.ArchivosError.append([Archivo, 'noexiste'])
		return Verificable
		
	def CargaArchivos(self, TipoObjeto, Objetos): #Carga inicial de archivos y sus hash sha1
		self.Archivos = [] 
		Resultado = False

		for Archivo in Objetos:
			RegistroArchivo = []
			RegistroArchivoError = []
			if os.path.isfile(Archivo): # Si el archivo existe
				if os.access(Archivo,os.R_OK): # Si tiene permiso de lectura
					if not enllavado(Archivo): #Si no está enllavado (comprobado con función de artamiz)
						RegistroArchivo.append(Archivo)
						RegistroArchivo.append(calcsum(Archivo,'a','sha1')) #Guarda el hash sha1 del archivo
						self.Archivos.append(RegistroArchivo)
					else:
						RegistroArchivoError.append(Archivo)
						RegistroArchivoError.append('enllavado')
						self.ArchivosError.append(RegistroArchivoError)
				else:
					RegistroArchivoError.append(Archivo)
					RegistroArchivoError.append('sinpermisolectura')
					self.ArchivosError.append(RegistroArchivoError)

		if self.Archivos:
			Resultado = True
		return Resultado
			
	def VerificaArchivos(self, CausaAlerta):
		Indice = 0
		Alerta = False
		Alertas = []
		self.ArchivosError = []
		for Archivo in self.Archivos: #Recorre la lista de archivos
			if self.ArchivoVerificable(Archivo[0]):
				NuevoHash = calcsum(Archivo[0], 'a', 'sha1')
				if CausaAlerta == 'nocambio':
					if Archivo[1] == NuevoHash:
						Alerta = True
						Alertas.append(Archivo[0])
				elif CausaAlerta == 'cambio':
					if Archivo[1] <> NuevoHash:
						Alerta = True
						Alertas.append(Archivo[0])
				else:
					None
				self.Archivos[Indice] = [Archivo[0], NuevoHash]
			Indice = Indice + 1
		return Alerta, Alertas

def main():
	
	def HintDeUso():
		print(' Monitorea la variación de archivos.\n')
		print(' Uso: python {0} [?,-nC, -a]\n'.format(Programa))
		print(' Opciones:')
		print('         <ninguna>: Alerta si hay cambios en directorios.')
		print('               -nC: Alerta cuando no hay cambios en los objetos monitoreados.')
		print('                -a: Monitorea archivos en lugar de directorios completos.')
		print('                 ?: Muestra esta ayuda.\n')
		print(' Este programa es software libre bajo licencia GPLv3.\n')

	def PantallaInicial():
		if os.name == 'posix':
			os.system('clear')
		elif os.name == 'nt':
			os.system('cls')
		else:
			None
		print('{0} {1}. {2}\n'.format(Programa,Ver,Copyright))
	
	def LeeParametrosLc():
		CausaAlerta = 'cambio'
		TipoObjeto = 'directorio'
		ParametroOk = True
		try:
			ar1 = argv[1]
			if argv[1] == '-nC':
				CausaAlerta = 'nocambio'
			elif argv[1] == '-a':
				TipoObjeto = 'archivo'
			else:
				ParametroOk = False
		except:
			None
			
		if ParametroOk:
			try:
				ar2 = argv[2]
				if ar2 == '-nC':
					CausaAlerta = 'nocambio'
				elif ar2 == '-a':
					TipoObjeto = 'archivo'
				else:
					ParametroOk = False
			except:
				None
				
		return ParametroOk, CausaAlerta, TipoObjeto
	
	def HoraTexto():
		return strftime('%Y-%m-%d %H:%M:%S', localtime())

	def ImprimeLinea():
		print('------------------------------------------------------------------------------')
	
	def CargaInicial():
		if TipoObjeto == 'directorio':
			Archivos = []
			for Directorio in ParametrosIni.Directorios:
				ListaArchivos = os.listdir(Directorio)
				for Archivo in ListaArchivos:
					Archivos.append(os.path.join(Directorio, Archivo))
			ResultadoCarga = MiMonitor.CargaArchivos(TipoObjeto, Archivos)
		else:
			ResultadoCarga = MiMonitor.CargaArchivos(TipoObjeto, ParametrosIni.Archivos)
		if MiMonitor.ArchivosError:
			PreparaRegistroErr(EventoLog5.format(HoraTexto(),MiMonitor.ArchivosError))
		return ResultadoCarga

	def PreparaRegistroErr(Registro):
		LogServicio.GrabaRegistroLog(Registro)
		print(Registro)
	
	def PreparaRegistroLog(Archivo, Hora, Causa):
		RegistroLog = MensajeLog1.format(Hora,Causa,Archivo,ParametrosIni.MinutosIntervalo)
		LogMonitoreo.GrabaRegistroLog(RegistroLog)
		print(RegistroLog)

	def PreparaCorreoLog(Alertas, CausaAlerta, Hora):
		MiCorreo.CreaAsuntoLog(CausaAlerta)
		MiCorreo.CreaMensajeLog(Alertas, CausaAlerta, ParametrosIni.MinutosIntervalo, Hora)
		ResultadoEnvio = MiCorreo.EnviarCorreo(ParametrosIni.De, ParametrosIni.Para)
		Hora = HoraTexto() #Actualiza la hora para el registro de eventos
		if ResultadoEnvio == 0:
			PreparaRegistroErr(EventoLog1.format(Hora,CausaAlerta,ParametrosIni.Para))
		elif ResultadoEnvio == 1:
			PreparaRegistroErr(EventoLog2.format(Hora,CausaAlerta))
			PreparaRegistroErr(ErrorLog1.format(Hora))
		else:
			PreparaRegistroErr(EventoLog2.format(Hora,CausaAlerta))
			PreparaRegistroErr(ErrorLog2.format(Hora))
			
	def InformaInicio(Hora):
		
		if TipoObjeto == 'directorio':
			Objetos = str(ParametrosIni.Directorios)
		else:
			Objetos = str(ParametrosIni.Archivos)
		PreparaRegistroErr(EventoLog0.format(Hora,Programa,CausaAlerta,ParametrosIni.MinutosIntervalo,TipoObjeto,Objetos))
		
		Texto = Programa + '@' + Maquina + ': ** Se inició el servicio'
		MiCorreo.CreaAsunto(Texto)

		Texto = 'El servicio ' + Programa + '-' + Ver + ' inició.\n\n'
		Texto = Texto + 'Equipo     : ' + Maquina + '\n'
		Texto = Texto + 'Hora       : ' + Hora + '\n'
		Texto = Texto + 'Regla      : ' + CausaAlerta + '\n'
		Texto = Texto + 'Tipo objeto: ' + TipoObjeto + '\n'
		if TipoObjeto == 'directorio':
			Texto = Texto + 'Directorios: ' + str(ParametrosIni.Directorios) + '\n\n'
		else:
			Texto = Texto + 'Archivos   : ' + str(ParametrosIni.Archivos) + '\n\n'
		Texto = Texto + 'La actividad del monitoreo se puede consultar en los log del servicio.'
		MiCorreo.CreaMensaje(Texto)
		
		ResultadoEnvio = MiCorreo.EnviarCorreo(ParametrosIni.De, ParametrosIni.ParaAdmin)
		Hora = HoraTexto() #Actualiza la hora para el log de eventos
		if ResultadoEnvio == 0:
			PreparaRegistroErr(EventoLog3.format(Hora, Programa, ParametrosIni.ParaAdmin))
		elif ResultadoEnvio == 1:
			PreparaRegistroErr(EventoLog4.format(Hora, Programa))
			PreparaRegistroErr(ErrorLog1.format(Hora))
		else:
			PreparaRegistroErr(EventoLog4.format(Hora, Programa))
			PreparaRegistroErr(ErrorLog2.format(Hora))

	def MonitoreaArchivos():
		PreparaRegistroErr(EventoLog6.format(HoraTexto()))
		HayAlerta, Alertas = MiMonitor.VerificaArchivos(CausaAlerta)
		Hora = HoraTexto()
		for ArchivoError in MiMonitor.ArchivosError:
			PreparaRegistroLog(ArchivoError[0], Hora, ArchivoError[1])
		if HayAlerta:
			for Archivo in Alertas:
				PreparaRegistroLog(Archivo, Hora, CausaAlerta)
			PreparaCorreoLog(Alertas, CausaAlerta, Hora)
#		if HayAlerta or MiMonitor.ArchivosError:
#			ImprimeLinea()
		PreparaRegistroErr(EventoLog7.format(HoraTexto()))
		ImprimeLinea()
	
	try:
		PantallaInicial()
		ParametrosLcOk, CausaAlerta, TipoObjeto = LeeParametrosLc()

		if ParametrosLcOk:
			ParametrosIni = Parametros('armoni.ini', TipoObjeto) #Crea el objeto de parámetros
			LogServicio = Log('armoni.err') #Para registrar eventos del servicio

			if not ParametrosIni.Error:
				LogMonitoreo = Log('armoni.log') #Para registrar las actividades del monitoreo
				MiMonitor = Monitor() #Crea el objeto monitor
				if ParametrosIni.RequiereAutenticacion == 'si':
					Pwd = standard_b64encode(getpass("Password de '" + ParametrosIni.Cuenta + "': "))
					MiCorreo = Correo(ParametrosIni.Servidor, ParametrosIni.Puerto, ParametrosIni.Cuenta, Pwd)
				else:
					MiCorreo = Correo(ParametrosIni.Servidor, ParametrosIni.Puerto, ParametrosIni.Cuenta)
				print("\nIniciando el servicio de verificación archivos con la regla '"+ CausaAlerta + "'...")
				if CargaInicial():
					print("\nServicio iniciado")
					ImprimeLinea()
					InformaInicio(HoraTexto())
					ImprimeLinea()
					Error = False	
					sleep(ParametrosIni.Intervalo)
					while not Error:
						MonitoreaArchivos()
						if TipoObjeto == 'directorio':
							if not CargaInicial():
								None
								#Error = True
						sleep(ParametrosIni.Intervalo)
				else:
					PreparaRegistroErr(ErrorLog4.format(HoraTexto(),Programa))
			else:
				PreparaRegistroErr(ErrorLog3.format(HoraTexto(),Programa))
		else:
			HintDeUso()
	except(KeyboardInterrupt, SystemExit):
		pass
		PreparaRegistroErr(EventoLog100.format(HoraTexto(), Programa))

if __name__ == '__main__':
	main()
else:
	None
