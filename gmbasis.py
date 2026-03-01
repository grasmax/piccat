import os
import sys
import base64

import time
import datetime
import suntime  #pip install suntime am 27.2.25, auch auf dem Solarraspi
import pytz     #pip install pytz am 27.2.25, auch auf dem Solarraspi


import json

import logging
from logging.handlers import RotatingFileHandler

# pip install pycryptodome
from Crypto.Cipher import AES
from Crypto import Random
import smtplib
from email.mime.text import MIMEText

import mariadb

import socket
import subprocess

import queue

###### ProgressLogger ##############################################################################
# Eine Python-Frage zu dieser Zeile an google gemini:
#    print(f"\r Speed: {speed:.2f} Dateien/s | Erledigt: {current_done}/{self.total_files} | ETA: {eta_str}  ", end="", flush=True)
#    Wie kann eine nachfolgende print-Anweisung feststellen, dass die vorherige print-Anweisung ohne \n ausgeführt wurde?

# Antwort:Das ist eine hervorragende Frage, denn Python (und die meisten Programmiersprachen) führen standardmäßig 
# kein „Gedächtnis“ über den Zustand des Cursors im Terminal.
# Kurze Antwort: Die nachfolgende print-Anweisung weiß es von sich aus nicht.
# Wenn du nach deinem Fortschrittsbalken einfach ein normales print("Fertig!") ausführst, wird Python den Text 
# einfach direkt hinter die ETA-Anzeige klatschen, anstatt eine neue Zeile zu beginnen.
# Hier eine Lösung:
# Alle Print- und Fortschrittsanzeigen müssen über ProgressLogger ausgeführt werden.
# ProgressLogger entscheidet, wie die nächste Zeile anzuzeigen ist:
class ProgressLogger:
    def __init__(self):
        self.needs_newline = False

    def log_progress(self, message):
        print(f"\r {message}", end="", flush=True)
        self.needs_newline = True

    def log_normal(self, message):
        if self.needs_newline:
            print() # Umbruch erzwingen
            self.needs_newline = False
        print(message)


###### ProgressMonitor ##############################################################################
class ProgressMonitor:
    def __init__(self, total_files, PrintLogger):
        self.start_time = time.perf_counter()
        self.total_files = total_files
        self.last_count = 0
        self.PrintLogger = PrintLogger

    def update_display(self, current_done):
        elapsed = time.perf_counter() - self.start_time
        if elapsed == 0: return

        # Items pro Sekunde
        speed = current_done / elapsed
        
        # Restzeit berechnen
        remaining = self.total_files - current_done
        eta_seconds = remaining / speed if speed > 0 else 0
        
        # Formatierung zu MM:SS oder HH:MM:SS
        eta_str = time.strftime("%H:%M:%S", time.gmtime(eta_seconds))
        
        self.PrintLogger.log_progress(f"Durchsatz: {speed:.2f} Dateien/s | Erledigt: {current_done}/{self.total_files} | ETA: {eta_str}  ")


###### Zeitmessung( tStart) ##############################################################################
def Zeitmessung( tStart, dCallMinSec, dCallMaxSec, dCallSumSec):

   stopSrv = time.perf_counter()

   dau = stopSrv - tStart

   if dau < dCallMinSec:
      dCallMinSec = dau

   if dCallMaxSec < dau:
      dCallMaxSec = dau

   dCallSumSec += dau  # Zeitdauer  in Sekunden

   return dCallMinSec, dCallMaxSec, dCallSumSec

###### ZeitmessungEinfach( tStart) ##############################################################################
def ZeitmessungEinfach( tStart, dSumSec):

   stopSrv = time.perf_counter()

   dau = stopSrv - tStart

   dSumSec += dau  # Zeitdauer  in Sekunden

   return dSumSec


###### CAesCipher    ##############################################################################
#  https://stackoverflow.com/questions/12524994/encrypt-and-decrypt-using-pycrypto-aes-256 / 258
BS = 16
pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS).encode()
unpad = lambda s: s[:-ord(s[len(s)-1:])]
class CAesCipher:

   def __init__( self, TestCode):
        self.key = bytes(TestCode, 'utf-8')

   def encrypt( self, Text ):
      encText = Text.encode()
      raw = pad(encText)

      iv = Random.new().read( AES.block_size )
      cipher = AES.new( self.key, AES.MODE_CBC, iv )

      ce = base64.b64encode( iv + cipher.encrypt( raw ) )
      return ce

   def decrypt( self, Text ):
      enc = base64.b64decode(Text)
      iv = enc[:16]
      cipher = AES.new(self.key, AES.MODE_CBC, iv )
      dec = cipher.decrypt( enc[16:] )
      u = unpad(dec)
      return u.decode("utf-8") 


###### CMailVersand   ##############################################################################
class CMailVersand:
   def __init__(self, sSmtpUser, sSmtpPwdCode, Von, An):
      
      self.SmtpUser = sSmtpUser
      self.SmtpPwdCode = sSmtpPwdCode
      self.Von = Von
      self.An = An

   ###### EmailVersenden(self, sBetreff, sText) ##############################################################################
   def EmailVersenden(self, sBetreff, sText, sTestCode):

    server = smtplib.SMTP_SSL('smtp.ionos.de',465,)
    # server.set_debuglevel(1)

    a = CAesCipher( sTestCode)
    server.login( self.SmtpUser, a.decrypt(self.SmtpPwdCode))
    
    message = MIMEText(sText, 'plain')
    message['Subject'] = sBetreff
    message['From'] = self.Von
    message['To'] = ", ".join(self.An)
    
    server.sendmail( self.Von, self.An,  message.as_string())
    # liefert sText nur als Byte-Folge: print(message.as_string()) 
    #$$ umstellen auf PrintLogger: print(f'Von: {self.Von}, An: {self.An}, Betreff: {sBetreff}, Text: {sText}')
    server.quit()

###### CBaseApp {   ##############################################################################

class CBaseApp:

   ###### __init__(self) ##############################################################################
   def __init__(self):
      self.tNow = datetime.datetime.now()
      self.sNow = self.tNow.strftime("%Y-%m-%d-%H-%M")
      self.tJetztStunde = datetime.datetime( self.tNow.year, self.tNow.month, self.tNow.day, self.tNow.hour, 0)
      self.bUseSunSettings = True

      
   ###### def vInit(self, sPrjName, sAppName) ##############################################################################
   def vInit(self, sPrjName, sAppName):

      sLogDir = './log'
      if not os.path.exists(sLogDir):
         os.mkdir(sLogDir)
         
      self.sPrjApp = f'{sPrjName}/{sAppName}'

      self.bFehlerpruefen = False
      
      self.PrintLogger = ProgressLogger()
      self.queueLogging = queue.Queue(maxsize=5000) 


      logging.basicConfig(encoding='utf-8', level=logging.INFO, # absteigend: DEBUG, INFO, WARNING,ERROR, CRITICAL
                          # DEBUG führt dazu, dass der HTTP-Request samt Passwörtern und APIKeys geloggt wird!
                          style='{', datefmt='%Y-%m-%d %H:%M:%S', format='{asctime} {levelname} {filename}:{lineno}: {message}',
                          handlers=[RotatingFileHandler(f'{sLogDir}/{sPrjName}.txt', maxBytes=100000, backupCount=20)],)
      sStart = f'Programmstart {self.sPrjApp} um {self.sNow}'
      logging.info(sStart)
      self.PrintLogger.log_normal( sStart)

      sCfgFile = f'{sPrjName}.cfg' # sFile = "E:\\dev_priv\\python_svn\\opendtu\\opendtu.cfg"
      try:
         f = open(sCfgFile, "r", encoding='utf-8')
      except Exception as e:
         logging.error(f'Fehler in open({sCfgFile}): {e}')
         quit()

      try:
         self.Settings = json.load(f)
         f.close()
      except Exception as e:
         logging.error(f'Fehler in json.load(): {e}')
         quit()

      self.sHostName = "unknown"
      try:
         self.sHostName =  socket.gethostname()
      except Exception as e:
          logging.error(f'Fehler bei socket.gethostname(): {e}')
          self.sHostName = "unknown"
      
      if self.sHostName == 'unknown':
         logging.error(f'Fehler: Hostname konnte nicht ermittelt werden')
         quit()      
      else:
         logging.info(f'Hostname: {self.sHostName}')

      
      try:
         self.bTestMode = True if self.Settings['Entwickler']['Testmode'] == 1 else False
         self.MariaIp = self.Settings['MariaDb']['IP']
         self.MariaUserCode = self.Settings['MariaDb']['User']
         self.MariaPwdCode = self.Settings['Pwd']['MariaDb']
         
         self.MariaDbName = self.Settings['MariaDb']['Db']
         self.LogTableName = self.Settings['MariaDb']['LogTableName']

         self.TestCode = self.Settings['Pwd']['Test']
         self.aes = CAesCipher(self.TestCode)

         self.mail = CMailVersand( self.Settings['Mail']['User'], self.Settings['Pwd']['Smtp'], self.Settings['Mail']['Von'], self.Settings['Mail']['An'])

         sSommerzeit = ''
         if self.bUseSunSettings:
            self.bSommerZeit = False
            sSommerzeit = 'nein'
            lt = time.localtime()
            if lt.tm_isdst:
               self.bSommerZeit = True
               sSommerzeit = 'ja'
         
            # 27.2.25
            # Aufgang:	06:57 Ortszeit Untergang:	17:42 Ortszeit
            self.latitude = self.Settings['Inverter']['latitude']
            self.longitude = self.Settings['Inverter']['longitude']

            sun = suntime.Sun(self.latitude, self.longitude)
            today_sr = sun.get_sunrise_time()
            today_ss = sun.get_sunset_time()

            tzBerlin = pytz.timezone('Europe/Berlin')
            self.tSonnenaufgang = today_sr.astimezone(tzBerlin)
            self.tSonnenuntergang = today_ss.astimezone(tzBerlin)
            # 2025-02-27 06:58:48+01:00    2025-02-27 17:40:48+01:00

            # jSun = {
            #    "Tag": self.sNow,
            #    "Aufgang": self.tSonnenaufgang.strftime("%Y-%m-%d-%H-%M"),
            #    "Untergang": self.tSonnenuntergang.strftime("%Y-%m-%d-%H-%M")
            # }
            # f = open("sunset.json", "w", encoding='utf-8')
            # json.dump(jSun, f, ensure_ascii=False, indent=4)
            # f.close()

            sF = "%d.%m.%Y %H:%M"
            sNow = f'Jetzt: {self.tNow.strftime(sF)}, Jetzt-Stunde: {self.tJetztStunde.strftime(sF)}, Sommerzeit: {sSommerzeit}, Sonnenaufgang: {self.tSonnenaufgang.strftime(sF)}, Sonnenuntergang: {self.tSonnenuntergang.strftime(sF)}'
         else:
            sF = "%d.%m.%Y %H:%M"
            sNow = f'Jetzt: {self.tNow.strftime(sF)}, Jetzt-Stunde: {self.tJetztStunde.strftime(sF)}'
         self.PrintLogger.log_normal(sNow)
         logging.info(sNow)

      except Exception as e:
         logging.error(f'Fehler beim Einlesen von: {sCfgFile}: {e}')
         quit()

   ###### Exception2Text(self, sContext, e) ##############################################################################
   def Exception2Text(self, sContext, e):

      error_msg = str(e)

      errno  = getattr(e, 'errno', None)
      msg    = getattr(e, 'msg', None)
      ret    = getattr(e, 'returncode', None)
      out    = getattr(e, 'output', None)

      details = []
      if errno is not None: details.append(f"ErrNo: {errno}")
      if msg   is not None: details.append(f"Msg: {msg}")
      if ret   is not None: details.append(f"Return: {ret}")
      if out   is not None: details.append(f"Output: {out}")

      detail_str = " | ".join(details)
      return f"Ausnahme in {sContext}: {error_msg} ({detail_str})"
      
   ###### Queue2Log(self, tLog, eTyp, sText) ##############################################################################
   def Queue2Log(self, tLog, eTyp, sText, mdbLog,cur):
   # Logeintrag in die Datenbank schreiben, bei Fehler auch in die Log-Datei
      s250 = sText[:250].replace('"', '') # self.LogTableName.sText ist aktuell 250 Zeichen lang und könnte " enthalten, die beim insert stören
      sStmt = f'insert into {self.MariaDbName}.{self.LogTableName} (tLog, eTyp, sText) values (?, ?, ?)'
      try:
         cur.execute( sStmt, (tLog, eTyp, s250))
         mdbLog.commit()
         if eTyp == "info":
            logging.info(sText)
         else:
            logging.error(sText)

         self.PrintLogger.log_normal(f'Logeintrag: {eTyp}: {sText}')

      except Exception as e:
         full_msg = self.Exception2Text("Queue2Log/insert into", e)
         logging.error(full_msg)
         quit()


   ###### Queue2Db(self, tLog, eTyp, sText) ##############################################################################
   # Logeintrag NUR in die Datenbank schreiben
   def Queue2Db(self, tLog, eTyp, sText, mdbLog, cur):
      s250 = sText[:250].replace('"', '') # self.LogTableName.sText ist aktuell 250 Zeichen lang und könnte " enthalten, die beim insert stören
      sStmt = f'insert into {self.MariaDbName}.{self.LogTableName} (tLog, eTyp, sText) values (?, ?, ?)'
      try:
         cur.execute( sStmt, (tLog, eTyp, s250))
         mdbLog.commit()

      except Exception as e:
         full_msg = self.Exception2Text("Queue/insert into", e)
         logging.error(full_msg)
         quit()




   ###### __Record2Log(self, eTyp, eLadeart, sText) ##############################################################################
   def __Record2Log(self, eTyp, sText):
   # Logeintrag in die Datenbank schreiben, bei Fehler auch in die Log-Datei
      try:
         self.queueLogging.put(("all",datetime.datetime.now(), eTyp, sText))

      except Exception as e:
         full_msg = self.Exception2Text("__Record2Log/queueDbErr.put", e)
         logging.error(full_msg)
         quit()


   ###### __Record2Db(self, eTyp, eLadeart, sText) ##############################################################################
   # Logeintrag NUR in die Datenbank schreiben
   def __Record2Db(self, eTyp, sText):

      try:
         self.queueLogging.put(("db_only",datetime.datetime.now(), eTyp, sText))

      except Exception as e:
         full_msg = self.Exception2Text(f"__Record2Db/self.queueDbErr.put({sText})", e)
         logging.error(full_msg)
         quit()

   ###### Info2Log(self, sText) ##############################################################################
   def Info2Log(self, sText):
      self.__Record2Log( "info", sText)


   ###### Error2Log(self, sText) ##############################################################################
   def Error2Log(self, sText):
      self.bFehlerpruefen = True
      self.__Record2Log( "error", sText)

   ###### Error2Db(self, sText) ##############################################################################
   def Error2Db(self, sText):
      self.__Record2Db( "error", sText)

   ###### Exception2Log(self, sContext, e) ##############################################################################
   def Exception2Log(self, sContext, e):
      self.bFehlerpruefen = True
      full_msg = self.Exception2Text(sContext, e)
      self.Error2Log(full_msg)


  ###### vEndeNormal(self) ##############################################################################
   def vEndeNormal(self, sEnde):
   #Script beenden und aufräumen
      self.mdb.close()
      sEnd = f'\nProgrammende {self.sPrjApp}: {sEnde}'
      self.Info2Log('mdb-close')
      self.Info2Log( sEnd)
      self.mdbLog.close()
      #unklar, wozu das gut ist: sys.stdout.flush() # write out cached messages to stdout
      quit()


   ###### vScriptAbbruch(self) ##############################################################################
   def vScriptAbbruch(self, sGrund):
   #Script beenden und aufräumen
      self.Error2Log(sGrund)
      self.Error2Log('\nProgrammabbruch mit mdb-close und email')
      self.mdb.close()
      self.mdbLog.close()
      self.mail.EmailVersenden(f'{self.sPrjApp}: Script abgebrochen!', sGrund, self.TestCode)
      #unklar, wozu das gut ist: sys.stdout.flush() # write out cached messages to stdout
      quit()




###### VerbindeMitMariaDb(self) ##############################################################################
###### 2 Verbindungen zur MariaDB aufbauen
   def VerbindeMitMariaDb(self):
      
      bConn = False
      bConnLog = False
      for i in range(1,10+1):
         try:
            self.mdb = mariadb.connect( host=self.MariaIp, port=3306,user=str(self.aes.decrypt(self.MariaUserCode)), password=str(self.aes.decrypt(self.MariaPwdCode)))
            bConn = True
         except Exception as e:
            self.logging.error(f'Fehler in mariadb.connect(): {e}')

         try:
            self.mdbLog = mariadb.connect( host=self.MariaIp, port=3306,user=str(self.aes.decrypt(self.MariaUserCode)), password=str(self.aes.decrypt(self.MariaPwdCode)))
            bConnLog = True

         except Exception as e:
            self.logging.error(f'Fehler in mariadb.connect() fürs Logging: {e}')

         if bConnLog == True and bConn == True:
            break
         time.sleep(2)

      if bConnLog != True or bConn != True:
         sErr = f'Fehler in VerbindeMitMariaDb(): Conn: {bConn}, ConnLog: {bConnLog}'
         self.vScriptAbbruch(sErr)


      # ab hier Logging in die MariaDb-Tabelle t_charge_log
      self.Info2Log('mdb-connect ok')

   def sGetDauer(self, td):
       total_seconds = int(td.total_seconds())
       hours, remainder = divmod(total_seconds, 3600)
       minutes, seconds = divmod(remainder, 60)
       return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

   def GetExifDate(self, img):
    try:
        exif_data = img.getexif()

        # EXIF Tags: 36867 = DateTimeOriginal, 306 = DateTime
        sRawDate = exif_data.get(36867) or exif_data.get(306)
        
        if not sRawDate or not isinstance(sRawDate, str):
            return None # Besser NULL in der DB als "Unbekannt"

        # EXIF Format ist oft '2024:05:12 14:30:05'
        # MariaDB braucht '2024-05-12 14:30:05'
        try:
            # Versuch 1: Standard EXIF Format parsen
            dt = datetime.datetime.strptime(sRawDate[:19], '%Y:%m:%d %H:%M:%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Falls das Format mal abweicht (manche Kameras nutzen Leerzeichen etc.)
            # Ersetzt die ersten zwei Doppelpunkte durch Bindestriche
            return sRawDate.replace(':', '-', 2)[:19]

    except Exception as e:
        self.Exception2Log("GetExifDate", e)
        return None


###### CBaseApp }   ##############################################################################
