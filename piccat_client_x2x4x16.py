# Bildanalyse mit Speicherung der Ordner- und Dateistruktur und den Ergebnissen in der MariaDB
# In dieser Version ist die Bildanalyse in piccat_server.py auf einen leistungsstärkeren Rechner ausgelagert

# Developed with support from Google Gemini (AI Assistance), Januar 2026:
# - Database schema and MariaDB optimization
# - Robust Python error handling and logging architecture
# - API integration for distributed image analysis

# Installationsschritte
# Läuft nur mit 64bit python Installation E:\dev_priv\python_3_12_9_64\python-3.12.9-amd64.exe

# virtuelle python-Umgebung erstellen und aktivieren:
# python -m venv ki_env
# ki_env\Scripts\activate

# nach der Aktivierung der virtuellen Umgebung diese Module installieren:
# python.exe -m pip install --upgrade pip

# Cuda ist für nvidia-Grafikkarten und erfordert die Installation des Cuda-Toolkits von
# https://developer.nvidia.com/cuda-12-8-0-download-archive?target_os=Windows&target_arch=x86_64&target_version=11&target_type=exe_local
# CPU-Variante: pip install torch torchvision
# Nvidia-Variante: pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# pip install pandas
# pip install git+https://github.com/openai/CLIP.git

# Im vs2026 erledigen:
# Python-Umgebungen --> Umgebung hinzufügen --> Vorhandene Umgebung --> Eigenen Speicherort angeben

# Speichern in die MariaDB: RaspiSolarMariaDb/piccat
# siehe createdb.sql

import logging
import requests, time, sys

from time import sleep

import os

import datetime
import json

import mariadb
import base64

import socket
import subprocess

from gmbasis import CBaseApp
from gmbasis import Zeitmessung
from gmbasis import ZeitmessungEinfach
from gmbasis import ProgressMonitor

from pathlib import Path

from PIL import Image, ImageOps

import threading
import queue

# Diese Ausschriften helfen, wenn man python noch nichtr richtig installiert hat:
import sys
print(f"sys.executable: {sys.executable}")
print(f"sys.path: {sys.path}")
# ['E:\\dev_priv\\python_svn\\piccat', 'E:\\dev_priv\\python_svn\\piccat', 'E:\\dev_priv\\python_3_12_9_64\\python312.zip', 
#  'E:\\dev_priv\\python_3_12_9_64\\DLLs', 'E:\\dev_priv\\python_3_12_9_64\\Lib', 'E:\\dev_priv\\python_3_12_9_64', 
#  'E:\\dev_priv\\python_svn\\piccat\\ki_env_64', 'E:\\dev_priv\\python_svn\\piccat\\ki_env_64\\Lib\\site-packages']

# Diese Ausschriften helfen, wenn man python noch nichtr richtig installiert hat:
import platform, struct
print(f"Python Version: {platform.python_version()}")
print(f"Architektur: {struct.calcsize('P') * 8} Bit")
# Python Version: 3.12.9
# Architektur: 64 Bit


import time
import datetime
# Da das Laden der KI-Module sehr lange dauert, wird hier schon mal die Zeitmessung begonnen:
tStartModulImport = datetime.datetime.now()
print( f"{tStartModulImport} Module für den Programmstart werden geladen...")


# Diese Module werden nur gebraucht, wenn die Bildanalyse hier lokal stattfindet:
# !!!!ACHTUNG! VS2026-KI pfuscht beim Aus- und Einkommentieren und änder u.U Groß-Kleinschreibung!!!!
# z.B. wurde aus Image, ImageOps --> image, imageOps
# print(f"modul os laden...")
# import os
# print(f"modul torch laden...")
# import torch
# print(f"modul clip  laden...")
# import clip
# print(f"modul pil laden...")
# from PIL import Image, ImageOps
# print(f"modul pandas laden...")
# import pandas as pd

#ist überflüssig: from tqdm import tqdm  # Fortschrittsanzeige
# kann man auch so erledigen: 
#   print(f"\r Speed: {speed:.2f} Dateien/s | Erledigt: {current_done}/{self.total_files} | ETA: {eta_str}  ", end="", flush=True)

import io
import struct

###### class CategoryInfo: ##############################################################################
###### Container für die Kategorien     #################################################################
class CategoryInfo:
    def __init__(self, user_text, ai_text):
        self.sUserText = user_text
        self.sAiText = ai_text

    def __repr__(self):
        return f"CategoryInfo(sUserText='{self.sUserText}', sAiText={self.sAiText})"

###### class CFolderInfo: ##############################################################################
###### Container für die Verzeichnisse     #################################################################
class CFolderInfo:
    def __init__(self, seqFolder, seqRun, bDelete):
        self.seqFolder = seqFolder
        self.seqRun = seqRun
        self.bDelete = bDelete

    def __repr__(self):
        return f"CFolderInfo(seqFolder='{self.seqFolder}', seqRun={self.seqRun}, bDelete={self.bDelete})"


###### class CDbFileInfo: ##############################################################################
###### Container für die Dateien     #################################################################
class CDbFileInfo:
    def __init__(self, seqFile, seqFolder, seqRun, iConfi, bDelete):
        self.seqFile = seqFile
        self.seqFolder = seqFolder
        self.seqRun = seqRun
        self.iConfi = iConfi
        self.bDelete = bDelete

    def __repr__(self):
        return f"CDbFileInfo(seqFile='{self.seqFile}', seqFolder='{self.seqFolder}', seqRun={self.seqRun}, iConfi={self.iConfi}, bDelete={self.bDelete})"

###### class CQueueFolderInfo: ##############################################################################
###### CQueueFolderInfo für die Verzeichnisdaten in der Queue     #################################################################
class CQueueFolderInfo:
    def __init__(self, seqFolder, sFolder):
        self.seqFolder = seqFolder
        self.sFolder = sFolder

    def __repr__(self):
        return f"CQueueFolderInfo(seqFolder={self.seqFolder}, sFolder={self.sFolder}')"



#################################################################################################################################
# Bei den Tests im Februar 2026 hat sich herausgestellt, dass das Allokieren von 90000 Byte-Arrays für die Bilder zu lange dauert
# Der RAM-Bedarf sprang im Sekundentakt zwischen 60 und 160MB.
# Abhilfe sollte mit global definierten, wiederverwedneten Speicherbereichen geschaffen werden
# Gemini hat vorgeschlagen, dies queue-basiert zu realisieren
# Container für das 16er-Bilddatenbündel, die über die QueueBilder an den Analyse-Thread übergeben werden  ######################

IMAGEBUFFSIZE = 33450

class CBildContainer:
   def __init__(self, bundle_nr, bild_nr):

      self.bundle_nr = bundle_nr
      self.bild_nr = bild_nr
      # so fkt es nicht:
      # self.ImageBuffSize = IMAGEBUFFSIZE
      # self.raw_buffer = bytearray(self.ImageBuffSize)
      # self.bio = io.BytesIO(self.raw_buffer)
      # self.view = self.bio.getbuffer()# memoryview für schnelles "Nullen" ohne Kopien
      
      # google sagt, ein so angelegtes byte-Array bleit mit
      # bun.listBilder[i].bio.seek(0)          # Zeiger zurücksetzen - der Speicher von 'bio' wird wiederverwendet!
      # bun.listBilder[i].bio.truncate(0)       # Den alten Inhalt logisch löschen, ohne den RAM freizugeben
      # erhalten:
      self.bio = io.BytesIO() 

      self.sFsFileNameOnly = ""
      self.seqFolder = 0
      self.dtExif = None


   ###### BildHinzufuegen(self, seqFolder, sFsFile, sFsFileNameOnly, sizePic, app) ##############################################################################
   def BildHinzufuegen(self, seqFolder, sFsFile, sFsFileNameOnly, sizePic, app):
      #self.Info2Log(f"BildHinzufuegen({sFsFileNameOnly})...")
      try:
         with Image.open(sFsFile).convert("RGB") as img:

            self.dtExif = app.GetExifDate( img)

            img = ImageOps.exif_transpose(img) # Korrigiert die Drehung basierend auf EXIF-Daten

            #Verkleinern, LANCZOS sorgt für hohe Qualität beim Resampling, BICUBIC ist schneller und weniger rechenintensiv
            # ganzes Bild, leider verzerrt: img = img.resize((224, 224), Image.Resampling.LANCZOS)
            # img = ImageOps.fit(img, (224, 224), method=Image.Resampling.LANCZOS)
            img = ImageOps.fit(img, sizePic, method=Image.Resampling.LANCZOS)


            self.sFsFileNameOnly = sFsFileNameOnly
            self.seqFolder = seqFolder
            self.bio.seek(0)          # Zeiger zurücksetzen - der Speicher von 'bio' wird wiederverwendet!
            self.bio.truncate(0)       # Den alten Inhalt logisch löschen, ohne den RAM freizugeben

            #print(f"BildHinzufuegen: bundle: {self.bundle_nr}, nr: {self.bild_nr} {sFsFileNameOnly}")
            img.save(self.bio, format='JPEG')      

            return True, None

        
      except Exception as e:
         return False, e
      finally:
         pass



   def Reset(self):
      try:
         #so fkt es nicht:
         #view = self.bio.getbuffer()# memoryview für schnelles "Nullen" ohne Kopien
         #view[:] = b'\x00' * IMAGEBUFFSIZE # Den Puffer effizient mit Nullen überschreiben (Zero-Copy)
         #aber so:
         self.bio.seek(0) # Den Zeiger auf den Anfang zurücksetzen
         self.bio.truncate(0) # Den alten Inhalt logisch löschen, ohne den RAM freizugeben

         self.sFsFileNameOnly = ""
         self.seqFolder = ""
         self.dtExif = None
      except Exception as e:
         print(f'main()',e)

class CBildContainerX16:
   def __init__(self, pool, bundle_nr):
      self.pool = pool
      self.bundle_nr = bundle_nr
      self.listBilder = []
      for b in range(16):
         self.listBilder.append(CBildContainer(bundle_nr, b)) 

   def release(self):
      for bc in self.listBilder:
         bc.Reset()
      self.pool.return_bundle(self)

class CBildContainerX16Pool:
    def __init__(self):
       anz = 20
       self.pool = queue.Queue(maxsize=anz)
       for a in range(anz ):
          self.pool.put( CBildContainerX16(self, a))

    def get_bundle(self):
        return self.pool.get() # Blockiert, wenn alle 8 Bündel unterwegs sind

    def return_bundle(self, bundle):
      self.pool.task_done()
      self.pool.put(bundle)








###### class CAnaThreadData: ##############################################################################
###### Container für die Daten, die an den Analyse-Thread übergeben werden  ######################
class CAnaThreadData:
    def __init__(self, port, anzDateienErledigt, dCallSumSec, dCallMinSec, dCallMaxSec, dMariaInsertSumSec, dMariaCommitSumSec):
        self.port = port
        self.anzDateienErledigt = anzDateienErledigt
        self.dCallSumSec = dCallSumSec
        self.dCallMinSec = dCallMinSec
        self.dCallMaxSec = dCallMaxSec
        self.dMariaInsertSumSec = dMariaInsertSumSec
        self.dMariaCommitSumSec = dMariaCommitSumSec

    def __repr__(self):
        return f"""CAnaThreadData(port='{self.port}', anzDateienErledigt='{self.anzDateienErledigt}', 
                   dCallSumSec={self.dCallSumSec}, dCallMinSec={self.dCallMinSec}, dCallMaxSec={self.dCallMaxSec},
                   dMariaInsertSumSec={self.dMariaInsertSumSec}, dMariaCommitSumSec={self.dMariaCommitSumSec})"""


###### class CBildDaten: ##############################################################################
###### Container für die Zwischenspeicherung der Bilddaten, während der Server gerufen wird ######################
class CBildDaten:
    def __init__(self, seqFolder, sFsFileNameOnly, dtExif):
        self.sFsFileNameOnly = sFsFileNameOnly
        self.seqFolder = seqFolder
        self.dtExif = dtExif

    def __repr__(self):
        return f"CBildDaten(sFsFileNameOnly='{self.sFsFileNameOnly}', seqFolder={self.seqFolder}, dtExif={self.dtExif})"


###### CBildAnalyse ##############################################################################
class CBildAnalyse (CBaseApp):

   ###### __init__(self) ##############################################################################
   def __init__(self):
       super().__init__()
       self.bUseSunSettings = False
       self.vInit('piccat', 'piccat_client.py')

      
   ###### vInit(self, sPrjName, sAppName) ##############################################################################
   def vInit(self, sPrjName, sAppName):
      
      super().vInit(sPrjName, sAppName)

      try:
         self.tNow = datetime.datetime.now()
         self.sNow = self.tNow.strftime("%Y%m%d_%H%M%S")


         self.sDateipfad = Path(self.Settings['Bildanalyse']['Verzeichnis'])


         self.iLaufNr = -1
         self.dictKat = {}
         self.dbFolder = {}
         self.fsFolder = {}
         self.iAllFiles = 0
         self.anzErlFolder = self.anzDateienErledigt = self.anzDateienVorhanden = self.anzDateienFehler = 0 

         self.sAufgabe =  self.Settings['Bildanalyse']['Aufgabe']
         self.sAufgabeVoll =  self.Settings['Bildanalyse']['Aufgaben']['AufgabeVoll']
         self.sAufgabeNeu  =  self.Settings['Bildanalyse']['Aufgaben']['AufgabeNeu']
         self.bVervollstaendigen = True if self.sAufgabe == self.sAufgabeVoll else False

         self.iDateienMaximal  =  self.Settings['Bildanalyse']['DateienMaximal']
         self.sModell =  self.Settings['Bildanalyse']['Modell']
         self.sModell224 =  self.Settings['Bildanalyse']['Modelle']['Modell224']
         self.sModell336  =  self.Settings['Bildanalyse']['Modelle']['Modell336']
         self.bAna = True if self.sModell == self.sModell224 or self.sModell == self.sModell336 else False
         self.ImageBuffSize = 33450 if self.sModell == self.sModell336 else 15980


         self.bHalfPrec = True if self.Settings['Bildanalyse']['HalfPrecision'] == 'True' else False

         self.iMinTrefferProzent = self.Settings['Bildanalyse']['MinTrefferProzent'] 
         self.MaxTrefferAnzahl = self.Settings['Bildanalyse']['MaxTrefferAnzahl'] 

         self.sErgebnisSpeicher = self.Settings['Bildanalyse']['Ergebnisspeicher'] 
         self.sErgCsv = self.Settings['Bildanalyse']['ErgSpeicher']['ErgSpeicherCsv'] 
         self.sErgDb = self.Settings['Bildanalyse']['ErgSpeicher']['ErgSpeicherDb'] 
         if self.sErgebnisSpeicher == self.sErgCsv:
            self.sResultFile = f"piccat_{self.sNow}_{self.sModell.replace('/','')}{'halfPrec' if self.bHalfPrec else ''}.csv"
         else:
            self.sResultFile = ""

         slocal = self.Settings['Bildanalyse']['Orte']['OrtLokal'] 
         self.sOrtServer = self.Settings['Bildanalyse']['Orte']['OrtServer'] 
         self.sOrt = self.Settings['Bildanalyse']['Ort'] 
         self.sServerIp = self.Settings['Server']['IP'] 
         self.url_base = f"http://{self.sServerIp}"
         self.session = requests.Session() # Wichtig für Performance (Keep-Alive)
         self.ServerPorts = [8000]#, 8001, 8002, 8003]

         self.queueFolder = None
         self.threadsEbene2 = []

         self.bcp = CBildContainerX16Pool() # zur Vermeidung zeitaufwendiger alloc/free für die Bytearrays
         self.queueBilder = queue.Queue(maxsize=500) 
         self.threadsEbene3 = []

         self.pbar = None

         self.stats_lock = threading.Lock()
         self.dCallMinSec = sys.float_info.max  # schnellster Server-Ruf in Sekunden
         self.dCallMaxSec = 0.0  # schnellster langsamster-Ruf  in Sekunden
         self.dCallSumSec = 0.0  # im Server verbrachte Zeitdauer  in Sekunden
         self.dMariaInsertSumSec = 0.0 # in den insert in MariaDB verbrachte Zeitdauer  in Sekunden
         self.dMariaCommitSumSec = 0.0 # in den commits in MariaDB verbrachte Zeitdauer  in Sekunden
         self.dPrepareSumSec = 0.0

         self.t21700 = None
         self.t36800 = None
         self.t47700 = None

      except Exception as e:
         self.Exception2Log(f'CBildAnalyse.vInit()',e)
         self.vScriptAbbruch("")

   ###### def EinstellungenInsLog(self) ##############################################################################
   def EinstellungenInsLog(self):
      try:
         sSett = f"""Beginn: {self.sNow} PC: {self.sHostName} Einstellungen: Verzeichnis: {self.sDateipfad}, 
                  Ergebnisse --> {self.sErgebnisSpeicher} {self.sResultFile if self.sErgebnisSpeicher == self.sErgCsv else ""} 
                  Aufgabe: {self.sAufgabe}, maximal {self.iDateienMaximal} Dateien"""
         self.Info2Log(sSett)
         sSett = f"""Nur Treffer mit mehr als {self.iMinTrefferProzent} Prozent,  maximal {self.MaxTrefferAnzahl} Treffer pro Datei
                  Analyse: {self.sOrt} {self.sServerIp if self.sOrt==self.sOrtServer else ""} {self.url_base if self.sOrt==self.sOrtServer else ""}
                  Modell: {self.sModell}, HalfPrec={'ja' if self.bHalfPrec else 'nein'}"""
         self.Info2Log(sSett)

      except Exception as e:
         self.Exception2Log(f'EinstellungenInsLog()',e)
         self.vScriptAbbruch("")


   ###### def ErgebnisseInsLog(self) ##############################################################################
   def ErgebnisseInsLog(self):
      try:
         tEnd = datetime.datetime.now()
         sDau = self.sGetDauer( tEnd - tStartModulImport)
         sDauVerarb = self.sGetDauer( tEnd - self.tNow)

         sResult = f"""LaufNr: {self.iLaufNr} Anzahl Kategorien: {len(self.dictKat)} Anzahl Verzeichnisse: {len(self.fsFolder)} 
Anzahl DB-Verzeichnisse: {len(self.dbFolder)} davon erledigt: {self.anzErlFolder} 
Anzahl Dateien: {self.iAllFiles} davon erledigt: {self.anzDateienErledigt}""" 
         self.Info2Log(sResult)

         sMin = "0.0" if self.dCallMinSec == sys.float_info.max else round(self.dCallMinSec,2)
         sResult = f"""Schnellste Bildanalyse: {sMin} langsamste Bildanalyse: {round(self.dCallMaxSec, 2)} 
Gesamtdauer: {sDau} Verarbeitungsdauer: {sDauVerarb} 
Dauer Bildvorbereitung in Minuten: {round(self.dPrepareSumSec/60.0, 2)}"""
         self.Info2Log(sResult)
         
         sResult = f"""Dauer Bildanalyse in Minuten: {round(self.dCallSumSec/60.0, 2)}, 
Dauer insertMariaDb in Minuten: {round(self.dMariaInsertSumSec/60.0, 2)},
Dauer commitMariaDb in Minuten: {round(self.dMariaCommitSumSec/60.0, 2)}"""
         self.Info2Log(sResult)

      except Exception as e:
         self.Exception2Log(f'ErgebnisseInsLog()',e)
         self.vScriptAbbruch("")



   ###### def ErmittleLaufNummer(self) ##############################################################################
   def ErmittleLaufNummer(self):
      try:
         sStmt = f'SELECT seqRun FROM {self.MariaDbName}.piccat_tab_run where tBeg = (select max(tBeg) FROM {self.MariaDbName}.piccat_tab_run)'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            sStmt = f'insert into {self.MariaDbName}.piccat_tab_run ( seqRun, tBeg) values ( NEXT VALUE FOR {self.MariaDbName}.piccat_seq_run, now(6))'
            cur.execute( sStmt)
            self.mdb.commit()
            return self.ErmittleLaufNummer()
         else:
            return rec[0]

      except Exception as e:
         self.Exception2Log(f'ErmittleLaufNummer()',e)
         return -1
      finally:
        cur.close()

   ###### def GibNeueLaufNummer(self) ##############################################################################
   def GibNeueLaufNummer(self):
      try:
         sStmt = f'SELECT NEXT VALUE FOR {self.MariaDbName}.piccat_seq_run'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Error2Log(f'Fehler in GibNeueLaufNummer() / {sStmt}'  )
            return -1
         else:
            LaufNr = rec[0]
            sStmt = f'insert into {self.MariaDbName}.piccat_tab_run ( seqRun, tBeg) values ( {LaufNr}, now(6))'
            cur.execute( sStmt)
            self.mdb.commit()
            return LaufNr

      except Exception as e:
         self.Exception2Log(f'GibNeueLaufNummer()',e)
         return -1
      finally:
        cur.close()


   ###### def LiesKategorien(self) ##############################################################################
   def LiesKategorien(self):

      try:
         sStmt = f'SELECT sAiText, sUserText, seqCat FROM {self.MariaDbName}.piccat_tab_category'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Info2Log(f'Keine Kategorien gefunden in piccat_tab_category')
            return True   

         while rec != None:
            sAi, sUser, nSeq = rec  # Entpackt das Tuple in Variablen
            self.dictKat[nSeq] = CategoryInfo(sUser, sAi)
            rec = cur.fetchone()

         self.mdb.commit()

      except Exception as e:
         self.Exception2Log(f'LiesKategorien()',e)
      finally:
        cur.close()

   ###### VerzeichnisLoeschen(self, sFolder, seqFolder, cur) ##############################################################################
   def VerzeichnisLoeschen(self, sFolder, seqFolder, cur):
      try:
           sStmt = f"delete from {self.MariaDbName}.piccat_tab_confidence where seqFolder = {seqFolder}"
           cur.execute( sStmt)

           sStmt = f"delete from {self.MariaDbName}.piccat_tab_file where seqFolder = {seqFolder}"
           cur.execute( sStmt)

           sStmt = f"delete from {self.MariaDbName}.piccat_tab_folder where sName = ?"
           cur.execute( sStmt, (sFolder,))
      except Exception as e:
         self.Exception2Log(f'VerzeichnisLoeschen()',e)
      finally:
         pass

   ###### VerzeichnisAnlegen(self, sFolder, cur) ##############################################################################
   def VerzeichnisAnlegen(self, sFolder, cur):
      try:
         sStmt = f"SELECT NEXT VALUE FOR {self.MariaDbName}.piccat_seq_folder"
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.vScriptAbbruch(f'Fehler in VerzeichnisAnlegen() / {sStmt}'  )
         seqFolder = rec[0]
         self.dbFolder[sFolder] = CFolderInfo( seqFolder, self.iLaufNr, bDelete=False)

         sStmt = f"INSERT INTO {self.MariaDbName}.piccat_tab_folder (seqFolder, sName, seqRun) VALUES ( ?, ?, ?)"
         cur.execute( sStmt, (seqFolder, sFolder, self.iLaufNr))

      except Exception as e:
         self.Exception2Log(f'VerzeichnisAnlegen()',e)
      finally:
         pass


   def LiesVerzeichnisse(self, start_folder):
      ergebnis_liste = {}
    
      for root, dirs, files in os.walk(start_folder):
         # 1. Verzeichnisse, die mit "000" beginnen, ignorieren (und nicht betreten)
         dirs[:] = [d for d in dirs if not d.startswith("000")]
        
         # 2. Prüfen, ob im aktuellen Verzeichnis jpeg/jpg Dateien liegen
         # case-insensitive Prüfung (.JPG, .jpeg etc.)
         # hat_bilder = any(f.lower().endswith(('.jpg', '.jpeg')) for f in files)
         # if hat_bilder:

         anzahl_bilder = sum(1 for f in files if f.lower().endswith(('.jpg', '.jpeg')))
         if 0 < anzahl_bilder:
            ergebnis_liste[root] = os.path.basename(root)
            self.iAllFiles += anzahl_bilder
            print(f"\r Dateien: {self.iAllFiles}  ", end="", flush=True)

      return ergebnis_liste


   ###### AktualisiereVerzeichnisse(self) ##############################################################################
   def AktualisiereVerzeichnisse(self):
      try:
         self.Info2Log(f"Unterverzeichnisse zu {self.sDateipfad} aus dem Dateisystem lesen...")

         pfad = Path(self.sDateipfad)

         # langsam und keine 000 und jp*-Berücksictigung
         # self.fsFolder = {str(d): d.name for d in pfad.rglob('*') if d.is_dir()}
         # viel besser:
         self.fsFolder = self.LiesVerzeichnisse(self.sDateipfad)

         #self.fsFolder[self.sDateipfad] = self.sDateipfad

         self.Info2Log(f"Filesystem-Verzeichnisse: {len(self.fsFolder)}")


         self.Info2Log(f"Verzeichnisse aus der DB lesen...")
         cur = self.mdb.cursor()
         sStmt = f'SELECT sName, seqFolder, seqRun FROM {self.MariaDbName}.piccat_tab_folder where seqRun = {self.iLaufNr} '
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Info2Log(f'Keine Folder gefunden in piccat_tab_folder')
         else:
            while rec != None:
               sFolder = rec[0]
               bDelete = True if self.fsFolder.get(sFolder) is None else False
               self.dbFolder[sFolder] = CFolderInfo(rec[1],rec[2], bDelete)
               rec = cur.fetchone()
         self.Info2Log(f"DB-Verzeichnisse: {len(self.dbFolder)}")

         for sFolderDel, fi in self.dbFolder.items():
            if fi.bDelete:
              self.VerzeichnisLoeschen(sFolderDel, fi.seqFolder, cur)


         for sFolderIns in self.fsFolder:
            bIns = True if len(self.dbFolder) <=0 else True if self.dbFolder.get(sFolderIns) == None else False
            if bIns:
              self.VerzeichnisAnlegen(sFolderIns,cur)


         self.queueFolder = queue.Queue(maxsize=len(self.dbFolder)) 
         for sDbFolder, fi in self.dbFolder.items():
            self.queueFolder.put(CQueueFolderInfo(fi.seqFolder, sDbFolder))


         self.mdb.commit()
   
      except Exception as e:
         self.Exception2Log(f'AktualisiereVerzeichnisse()',e)
      finally:
        cur.close()


   ###### ErmittleDateiAnzahl(self) ##############################################################################
   def ErmittleDateiAnzahl(self):
      try:
         self.Info2Log(f"Ermitteln, wieviele Dateien analysiert werden müssen...")

         pfad = Path(self.sDateipfad)
         files = list(pfad.rglob("*.jp*"))
         self.iAllFiles = len(files)

         self.Info2Log(f"Dateianzahl (*.jp*): {self.iAllFiles}")
         
      except Exception as e:
         self.Exception2Log(f'ErmittleDateiAnzahl()',e)
    
      finally:
         pass


   ###### InitialisiereModell(self) ##############################################################################
   def InitialisiereModell(self):
      try:
         if len(self.sModell) <= 0:
            return
         self.Info2Log(f"InitialisiereModell...")

         # self.dictKat[seqCat] = CategoryInfo(sUserText, sAiText)
         self.en_prompts = [f"{value.sAiText}" for key, value in self.dictKat.items()]
         self.aSeqCat = [f"{key}" for key in self.dictKat.keys()]

         # Cuda ist für nvidia-Grafikkarten und erfordert die Installation des Cuda-Toolkits
         self.device = "cuda" if torch.cuda.is_available() else "cpu"

         self.Info2Log(f"Modell {self.device} / {self.sModell} laden...")
         self.model, self.preprocess = clip.load( self.sModell, device=self.device)

         if self.device == "cuda" and self.bHalfPrec:
            #1+2model.half() # Nutzt die Tensor-Cores der RTX 5060 Ti optimal aus
            #2 for param in model.parameters():
            #2    param.data = param.data.to(torch.float16)
            #3model.to(torch.float16)
            #4:
            self.model.float() # Erst sicherstellen, dass alles Float ist
            clip.model.convert_weights(self.model) # Dann gezielt in Half konvertieren

         self.Info2Log(f"clip.tokenize...")
         self.text_inputs = clip.tokenize(self.en_prompts).to(self.device)


      except Exception as e:
         self.Exception2Log(f'InitialisiereModell()',e)
      finally:
         pass

   ###### HoleSeqNummern(self, cur) ##############################################################################
   def HoleSeqNummern(self, cur):
      try:
         aSeq = []

         sStmt = f"SELECT NEXT VALUE FOR {self.MariaDbName}.piccat_seq_file FROM {self.MariaDbName}.seq_1_to_16"
         cur.execute( sStmt)

         rec = cur.fetchone()
         if rec == None:
            self.vScriptAbbruch(f'Fehler in HoleSeqNummern() / {sStmt}'  )
         else:
            while rec != None:
               aSeq.append( rec[0])
               rec = cur.fetchone()

         return aSeq

      except Exception as e:
         self.Exception2Log(f'HoleSeqNummern()',e)
         return None
      finally:
         pass


   ###### DateiAnlegen(self, seqFolder, sFile, dtExif, cur) ##############################################################################
   def DateiAnlegen(self, seqFolder, sFile, dtExif, cur):
      try:
         sStmt = f"SELECT NEXT VALUE FOR {self.MariaDbName}.piccat_seq_file"
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.vScriptAbbruch(f'Fehler in DateiAnlegen() / {sStmt}'  )
         seqFile = rec[0]

         sStmt = f"INSERT INTO {self.MariaDbName}.piccat_tab_file (seqFile, sName, seqFolder, seqRun, dtExif) VALUES ( ?, ?, ?, ?, ?)"
         cur.execute( sStmt, (seqFile, sFile, seqFolder, self.iLaufNr, dtExif))

         return seqFile

      except Exception as e:
         self.Error2Log(f'Datei: {sFile}'  )
         self.Exception2Log(f'DateiAnlegen()',e)
         return -1
      finally:
         pass

   ###### DateiLoeschen(self, seqFile, sFile, cur) ##############################################################################
   def DateiLoeschen(self, seqFile, sFile, cur):
      try:
         #self.Info2Log(f"Dateien und Konfidenzen für {sFile}/{seqFile} aus der DB löschen...")

         sStmt = f"delete from {self.MariaDbName}.piccat_tab_confidence where seqFile = {seqFile}"
         cur.execute( sStmt)

         sStmt = f"delete from {self.MariaDbName}.piccat_tab_file where sName = ? and sSeqRun={self.iLaufNr}"
         cur.execute( sStmt, (sFile,))

      except Exception as e:
         self.Exception2Log(f'DateiLoeschen({sFile}/{seqFile})',e)
         return -1
      finally:
         pass

   ###### DbDateienLesen(self, sFolder, seqFolder, cur) ##############################################################################
   def DbDateienLesen(self, sFolder, seqFolder, cur):
      try:
         #self.Info2Log(f"Dateien für {sFolder} (Seq: {seqFolder})  aus der DB lesen...")

         aDbFiles = {}

         sStmt = f"""SELECT f.sName, f.seqFile, f.seqRun, count(c.seqFile) 
                        FROM {self.MariaDbName}.piccat_tab_file f 
                        LEFT join {self.MariaDbName}.piccat_tab_confidence c ON  c.seqFile = f.seqFile 
                        WHERE f.seqFolder = ? GROUP BY f.seqFile"""

         cur.execute( sStmt, (seqFolder, ))
         rec = cur.fetchone()
         if rec == None:
            pass #self.Info2Log(f'Keine Dateien zu Folder gefunden in piccat_tab_file')
         else:
            while rec != None:
               sName = rec[0]
               aDbFiles[sName] = CDbFileInfo(rec[1],seqFolder,rec[2], rec[3], bDelete=False)
               rec = cur.fetchone()

         return aDbFiles

      except Exception as e:
         self.Exception2Log(f'DbDateienLesen({sFolder} (Seq: {seqFolder}))',e)
         return None
      finally:
         pass



   # ###### NimmZwischenzeit(self) ##############################################################################
   # def NimmZwischenzeit(self):

   #    if 21700 < self.anzDateienErledigt and self.t21700 == None:
   #       self.t21700 = datetime.datetime.now()
   #       tDau = self.t21700 - self.tNow
   #       sDau = self.sGetDauer( tDau)
   #       minutes = int(tDau.total_seconds() / 60.0)
   #       if 0 < minutes:
   #          self.Info2Log(f"21700 Dateien: {sDau}, {21700/minutes} pro Minute")

   #    if 36800 < self.anzDateienErledigt and self.t36800 == None:
   #       self.t36800 = datetime.datetime.now()
   #       tDau = self.t36800 - self.t21700
   #       sDau = self.sGetDauer( tDau)
   #       minutes = int(tDau.total_seconds() / 60.0)
   #       anz = 36800 - 21700
   #       if 0 < minutes:
   #          self.Info2Log(f"{anz}Dateien: {sDau}, {anz/minutes} pro Minute")

   #    if 47700 < self.anzDateienErledigt and self.t47700 == None:
   #       self.t47700 = datetime.datetime.now()
   #       tDau = self.t47700 - self.t36800
   #       sDau = self.sGetDauer( tDau)
   #       minutes = int(tDau.total_seconds() / 60.0)
   #       anz = 47700 - 36800
   #       if 0 < minutes:
   #          self.Info2Log(f"{anz}Dateien: {sDau}, {anz/minutes} pro Minute")


   ###### ThreadData2AppAData(self, atd) ##############################################################################
   def ThreadData2AppAData(self, atd):
      with self.stats_lock:
         
         self.anzDateienErledigt += atd.anzDateienErledigt

         self.dCallSumSec += atd.dCallSumSec
         
         if atd.dCallMinSec < self.dCallMinSec:
            self.dCallMinSec = atd.dCallMinSec
         
         if self.dCallMaxSec < atd.dCallMaxSec:
            self.dCallMaxSec = atd.dCallMaxSec
         
         self.dMariaInsertSumSec += atd.dMariaInsertSumSec
         self.dMariaCommitSumSec += atd.dMariaCommitSumSec

   ###### FolderThreadData2AppData(self, anzFolder, dMariaCommitSumSec, dauSchrumpfAlle) ##############################################################################
   def FolderThreadData2AppData(self, anzFolder, dMariaCommitSumSec, dauSchrumpfAlle):
      with self.stats_lock:
         self.anzErlFolder += anzFolder
         self.dMariaCommitSumSec += dMariaCommitSumSec
         self.dPrepareSumSec += dauSchrumpfAlle



   ###### FolderThread(self, pbar) ##############################################################################
   def FolderThread(self, pbar):
      dauSchrumpfAlle = 0.0
      try:
         print(f"Start FolderThread()\n", end="")

         # EIGENE Verbindung für den Thread (Wichtig für MariaDB!)
         # Falls du eine globale Verbindung nutzt, stelle sicher, 
         # dass NUR dieser Thread sie verwendet.
         mariaDb = mariadb.connect( host=self.MariaIp, port=3306,user=str(self.aes.decrypt(self.MariaUserCode)), password=str(self.aes.decrypt(self.MariaPwdCode)))
         cur = mariaDb.cursor()

         anzFolder = 0
         while True:
            try:
               qfi =  self.queueFolder.get(timeout=30)
            except queue.Empty:
               break # keine weiteren Verzeichnisse -->  abbrechen

            if qfi is None:
               break # Beenden-Signal --> abbrechen

            pfad = Path(qfi.sFolder) # Dateien aus dem Dateisystem lesen...
            fsFiles = {str(d): d.name for d in pfad.glob('*.jp*')}
            anzFsFiles = len(fsFiles)

            if self.bVervollstaendigen:
               aDbFiles = self.DbDateienLesen( qfi.sFolder, folderinfoDb.seqFolder, cur) # aus DB lesen
               if aDbFiles != None:
                  for sDbFile, fiDb in aDbFiles.items():
                     bDelete = True if fsFiles.get(f"{qfi.sFolder}\\{sDbFile}") is None else False
                     if bDelete:
                        self.DateiLoeschen( fiDb.seqFile, sDbFile, cur)

            fileinfoDb = None

            bun16 = self.bcp.get_bundle()
            #print(f"FolderThread: self.bcp.get_bundle({bun16.bundle_nr})")
            iIdx = 0 

            for sFsFile, sFsFileNameOnly in fsFiles.items():  #Hauptschleife

               if self.bVervollstaendigen:
                  fileinfoDb = aDbFiles.get(sFsFileNameOnly)
                  if fileinfoDb != None:
                     if fileinfoDb.iConfi > 0:
                        self.anzDateienVorhanden += 1
                        continue  # diese Datei hat bereits Konfidenz-Sätze

               sizePic = (224, 224) if self.sModell == self.sModell224 else (336, 336)

               tStartPrepare = time.perf_counter()
               ret, exc = bun16.listBilder[iIdx].BildHinzufuegen(qfi.seqFolder, sFsFile, sFsFileNameOnly, sizePic, self)
               dauSchrumpf = ZeitmessungEinfach(tStartPrepare, 0.0)
                  
               if ret == False:
                  if exc != None:
                     self.Exception2Log(f'CBildContainer.BildHinzufuegen()',exc)

                  self.Error2Log(f"Bild übersprungen (defekt): {sFsFileNameOnly}")
                  continue

               iIdx += 1
               dauSchrumpfAlle += dauSchrumpf

               if iIdx >= 16:
                  self.queueBilder.put(bun16)
                  bun16 = self.bcp.get_bundle()
                  #print(f"FolderThread: self.bcp.get_bundle({bun16.bundle_nr})")
                  iIdx = 0

            if iIdx > 0:
               self.queueBilder.put(bun16)

            anzFolder +=1
        
      except Exception as e:
         self.Exception2Log(f'FolderThread()',e)
      finally:
         tStartCommit = time.perf_counter()

         if 'cur' in locals(): 
            cur.close()
         if 'mariaDb' in locals(): 
            mariaDb.commit()
            mariaDb.close()
         

         self.FolderThreadData2AppData( anzFolder, time.perf_counter() - tStartCommit, dauSchrumpfAlle)
         print(f"Ende FolderThread(), erledigt: {anzFolder}\n", end="")


   #################################################################################################################################
   def prepare_raw_payload(self, bild_container_liste):
       """
       Packt 16 Bilder in einen einzigen binären Stream.
       Format: [Länge Bild 1 (4 Bytes)][Daten Bild 1][Länge Bild 2 (4 Bytes)]...
       """
       payload = io.BytesIO()
    
       for container in bild_container_liste:
           if container.seqFolder == 0:
              continue
           img_data = container.bio.getbuffer()
           img_len = len(img_data)
        
           # 1. Schreibe die Länge des Bildes als Unsigned Int (4 Bytes, Big Endian)
           payload.write(struct.pack('I', img_len))
           # 2. Schreibe die Bilddaten direkt aus dem Buffer
           payload.write(img_data)
    
       return payload.getvalue() # Gibt den gesamten Block als ein bytes-Objekt zurück


   ###### AnalysierenSpeichernThread(self, pbar, atd) ##############################################################################
   def AnalysierenSpeichernThread(self, pbar, atd):
      try:
         # EIGENE Verbindung für den Thread (Wichtig für MariaDB!)
         # Falls du eine globale Verbindung nutzt, stelle sicher, 
         # dass NUR dieser Thread sie verwendet.
         mariaDb = mariadb.connect( host=self.MariaIp, port=3306,user=str(self.aes.decrypt(self.MariaUserCode)), password=str(self.aes.decrypt(self.MariaPwdCode)))
         cur = mariaDb.cursor()

         print(f"Start AnalysierenSpeichernThread(Port: {atd.port})\n", end="")

         raw_data = None

         while True:
            try:
               bun16 =  self.queueBilder.get(timeout=30) # 16er Bündel abholen, Timeout von 3 auf 30 Sekunden erhöht, damit sich die Threads nicht gleich beenden, wenn die Ebene 2 noch nichts gelifert hat
               #print(f"Ana: get bundle {bun16.bundle_nr}")
            except queue.Empty:
               break # keine weiteren Bilder --> abbrechen

            if bun16 is None:
               break # Beenden-Signal --> abbrechen

            payload = {'lfdNr': atd.anzDateienErledigt+1} # seqFile hier noch nicht bekannt

            try:               
               aSeq = self.HoleSeqNummern( cur)
               raw_data = self.prepare_raw_payload(bun16.listBilder)

               tStartAna = time.perf_counter()
               response = None
               maxVersuche = 3
               for versuch in range(maxVersuche):
                  try:
                     response = self.session.post(  f"{self.url_base}:{atd.port}/analyze", data=raw_data, headers={'Content-Type': 'application/octet-stream'}, timeout=30)
                     if response.status_code == 200:
                        break

                  except Exception as e:
                     if versuch < maxVersuche - 1:
                        time.sleep(2 * (versuch + 1)) # Exponentielles Warten (2s, 4s...)
                        continue
                     else:
                        self.Exception2Log(f'AnalysierenSpeichernThread(): analyse() konnte wiederholt nicht gerufen werden.',e)
                        return

               atd.dCallMinSec, atd.dCallMaxSec, atd.dCallSumSec = Zeitmessung(tStartAna, atd.dCallMinSec, atd.dCallMaxSec, atd.dCallSumSec)

               if response.status_code != 200:
                  self.Error2Log(f"Fehler in AnalysierenSpeichernThread( {self.url_base}:{atd.port}/analyze: response.status_code: {response.status_code}")
                  return

               raw_bytes = response.content
               # Wurde auf dem Server so eingepackt: binary_data.extend(struct.pack('<hh', cat_id, conf))
               pair_size = struct.calcsize('<hh') # Ein Paar (short, short) ist 4 Bytes groß
    
               for img_idx, bd in enumerate(bun16.listBilder):
            
                  if len(bd.sFsFileNameOnly) <= 0:
                     continue

                  tStartDb = time.perf_counter()

                  seqFile = self.DateiAnlegen( bd.seqFolder, bd.sFsFileNameOnly, bd.dtExif, cur)
                  if seqFile == -1:
                     self.anzDateienFehler += 1
                     continue


                  for pair_idx in range(5):                         # umwandeln des flachen Byte-Stream zurück in die 16x10 Struktur
                     offset = (img_idx * 5 + pair_idx) * pair_size  # Berechne die aktuelle Position im Byte-Stream
                     chunk = raw_bytes[offset : offset + pair_size]  # Extrahiere 4 Bytes und entpacke sie als zwei Shorts
                     seqKat, iKonfi = struct.unpack('<hh', chunk)
                     if seqKat <= 0:
                        continue

                     if self.iMinTrefferProzent < iKonfi or pair_idx == 0:
                        catinfo = self.dictKat.get(seqKat)
                        sStmt = f"INSERT INTO {self.MariaDbName}.piccat_tab_confidence (seqRun, seqFile, seqFolder, seqCategory, iConfidence) VALUES ( ?, ?, ?, ?, ?)"
                        cur.execute( sStmt, (self.iLaufNr, seqFile, bd.seqFolder, seqKat, iKonfi))

                  atd.dMariaInsertSumSec = ZeitmessungEinfach(tStartDb, atd.dMariaInsertSumSec)
                        
               atd.anzDateienErledigt += len(bun16.listBilder)

               tStartCommit = time.perf_counter()
               mariaDb.commit()
               atd.dMariaCommitSumSec = ZeitmessungEinfach(tStartCommit, atd.dMariaCommitSumSec)

            except Exception as e:
               self.Exception2Log(f'AnalysierenSpeichernThread()',e)
            finally:
               self.queueBilder.task_done()
               #print(f"Ana: release bundle {bun16.bundle_nr}")
               bun16.release()
               #print(f"task_done()(Port: {atd.port})")


         # self.NimmZwischenzeit()

        
      except Exception as e:
         self.Exception2Log(f'AnalysierenSpeichernThread()',e)
      finally:
         self.ThreadData2AppAData( atd)

         if 'cur' in locals(): 
            cur.close()
         if 'mariaDb' in locals(): 
            mariaDb.commit()
            mariaDb.close()

         print(f"Ende AnalysierenSpeichernThread(Port: {atd.port}), erledigt: {self.anzDateienErledigt}\n", end="")

 

   ###### StarteThreads(self) 2 Schrumpfer, 4 Verteiler erzeugen ##############################
   def StarteThreads(self):
      self.Info2Log("Alle nötigen Threads starten")

      # Ebene 2 holt Verzeichnis aus der QueueFolder, liest Bilder zum Verzeichnis, staucht sie und stellt sie als 16er Bündel in die QueueBilder
      self.threadsEbene2 = []
      for t in range(3):
         t = threading.Thread(target=self.FolderThread, args=(self.pbar,))
         t.daemon = True # Thread stirbt, wenn Hauptprogramm endet
         t.start()
         self.threadsEbene2.append(t)

      while self.queueBilder.empty(): #erstmal warten, bis die ersten Bilder da sind, sonst beenden sich die Ebene3-Threads gleich wieder
         sleep(1)

      # Ebene 3 holt 16er-Bilder-Bündel aus der QueueBilder, schickt sie zur Analyse an den Server, wartet auf Ergebnis und speichert es in MariaDB
      self.threadsEbene3 = []
      for p in self.ServerPorts:
         atd = CAnaThreadData( port=p, anzDateienErledigt=0, dCallSumSec=0.0, dCallMinSec=sys.float_info.max, dCallMaxSec=0.0, dMariaInsertSumSec=0.0, dMariaCommitSumSec=0.0)
         t = threading.Thread(target=self.AnalysierenSpeichernThread, args=(self.pbar,atd))
         t.daemon = True # Thread stirbt, wenn Hauptprogramm endet
         t.start()
         self.threadsEbene3.append((t,atd))
         sleep(0.5)

   ###### init_brain_on_ryzen(self) initialisert die Verbindung zum Server. Dort muss piccat_server.py gestartet sein
   def init_brain_on_ryzen(self):

      self.Info2Log("Kategorien aus DB lesen und die Analyse-Server auf dem Ryzen senden")

      cur = self.mdb.cursor()
      cur.execute(f"SELECT seqCat, sAiText FROM {self.MariaDbName}.piccat_tab_category")
        
      # Format für die API:
      cat_list = [{"id": r[0], "text": r[1]} for r in cur.fetchall()]
      cur.close()

      cl = {
         "categories": cat_list, # Ihre vorhandene Kategorien-Liste
         "total_items": int(self.iAllFiles / len(self.ServerPorts))      # Der neue Integer-Wert
      }

      try:
         # resp = self.session.post(f"{self.url_base}/init_brain", json=cl, timeout=20)


         for p in self.ServerPorts:
             url = f"{self.url_base}:{p}/init_brain"
             print(f"Initialisiere Port {p}...")
             resp = self.session.post(url, json=cl, timeout=20)

             self.Info2Log(f"{self.url_base}:{p}/init_brain: {resp.json()}")
             if resp.status_code != 200:
               self.vScriptAbbruch(f"Fehler in init_brain_on_ryzen(): {self.url_base}:{p}/init_brain liefert resp.status_code {resp.status_code}")

      except Exception as e:
         self.Exception2Log(f'init_brain_on_ryzen()',e)
         return False


   ###### Abschluss(self) ##############################################################################
   def Abschluss(self):
      try:
         sStmt = f'update {self.MariaDbName}.piccat_tab_run set tEnd = now(6) where seqRun = {self.iLaufNr}'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         self.mdb.commit()

         self.EinstellungenInsLog()
         self.ErgebnisseInsLog()

         if self.bFehlerpruefen:
            print(f"Es sind Fehler aufgetreten. Bitte das Log prüfen.")
            return f"Bildanalyse mit Fehlern."

         return f"\nDetails zur Bildanalyse siehe Log."

      except Exception as e:
         self.Exception2Log(f'Abschluss()',e)
         return ""
      finally:
        cur.close()



###### CBildAnalyse } ##############################################################################

def main(argv):

   monitor = None

   try:
      ba = CBildAnalyse()                # u.a. die Konfigdatei lesen 

      ba.VerbindeMitMariaDb()            # Verbindung zur DB herstellen, zweite Verbindung fürs Log
      ba.EinstellungenInsLog()

      if ba.sAufgabe == ba.sAufgabeNeu:     
         ba.iLaufNr = ba.GibNeueLaufNummer()    
         if ba.iLaufNr <= 0:
            ba.vScriptAbbruch(f'Keine Bildanalyse durchgeführt: iLaufNr <= 0')

      elif ba.sAufgabe == ba.sAufgabeVoll:    
         ba.iLaufNr = ba.ErmittleLaufNummer()
         if ba.iLaufNr <= 0:
            ba.vScriptAbbruch(f'Keine Bildanalyse durchgeführt: iLaufNr <= 0')

      else:
         ba.vScriptAbbruch(f'Keine Bildanalyse durchgeführt weil Aufgabe unklar. Bitte piccat.cfg Bildanalyse/Aufgabe korrigieren.')

      ba.LiesKategorien()

      ba.AktualisiereVerzeichnisse()    # nicht mehr vorhandene Verzeichnisse aus DB löschen und neue einfügen, alle mit aktueller Nummer speichern
                                        # die Verzeichnisse auch gleich in die QueueFolder stellen
      # ba.ErmittleDateiAnzahl() schon in ba.AktualisiereVerzeichnisse() erledigt
              
      ba.init_brain_on_ryzen()   # für Bildanalyse-Server initialisieren, Dateianzahl mitgeben

      # ba.pbar = tqdm(total=ba.iAllFiles, desc="Bild-Analyse", leave=True)

      # ba.FolderThread( ba.pbar)
      # atd = CAnaThreadData( port=8000, anzDateienErledigt=0, dCallSumSec=0.0, dCallMinSec=sys.float_info.max, dCallMaxSec=0.0, dMariaInsertSumSec=0.0, dMariaCommitSumSec=0.0)
      # ba.AnalysierenSpeichernThread(ba.pbar, atd)
      ba.StarteThreads() # 3 Bild-Schrumpfer, 4 Verteiler


      # while 0 < ba.queueFolder.qsize() or 0 < ba.queueBilder.qsize():
      #    sleep(60)

      monitor = ProgressMonitor(ba.iAllFiles)
      while any(t.is_alive() for t,atd in ba.threadsEbene3):
          
          aktueller_stand = sum(atd.anzDateienErledigt for t,atd in ba.threadsEbene3)# Summe bilden (Sicher ohne Lock)
          monitor.update_display(aktueller_stand)
          time.sleep(3.0)
      

      for t in ba.threadsEbene2:     #für jeden Thread ein Signal zum Beenden geben       
         t.join()#optional: Warten, bis der Thread wirklich physisch beendet ist

      for t,atd in ba.threadsEbene3:     #für jeden Thread ein Signal zum Beenden geben       
         t.join()#optional: Warten, bis der Thread wirklich physisch beendet ist
            

      ba.vEndeNormal( ba.Abschluss())


   except KeyboardInterrupt:
      ba.mdb.commit()
      ba.Info2Log("\nProgramm mit STRG+C abgebrochen.")

    
      # 1. Die Queue leeren (optional, aber beschleunigt den Abbruch)
      try:
         while True:
            ba.queueFolder.get_nowait()
            ba.queueFolder.task_done()
         while True:
            ba.queueBilder.get_nowait()
            ba.queueBilder.task_done()
      except queue.Empty:
         pass

      # 2. Jedem Thread ein "None" schicken
      for _ in range(len(ba.threadsEbene2)):
         ba.queueFolder.put(None)
      for _ in range(len(ba.threadsEbene3)):
         ba.queueBilder.put(None)

      # 3. Jetzt erst in die Überwachungs-Schleife
      while any(t.is_alive() for t in ba.threadsEbene2):
         sleep(0.1)
      while any(t.is_alive() for t, atd in ba.threadsEbene3):
         aktueller_stand = sum(atd.anzDateienErledigt for t,atd in ba.threadsEbene3)# Summe bilden (Sicher ohne Lock)
         sleep(0.1)
      monitor.update_display(aktueller_stand)

      ba.vEndeNormal( ba.Abschluss())

   except Exception as e:
      ba.Exception2Log(f'main()',e)
      ba.vScriptAbbruch(f'Bildanalyse unvollständig oder abgebrochen.')
   finally:
      pass

if __name__ == "__main__":
    main(sys.argv)

# offen: Verzeichnisse ohne jp* wieder löschen oder gar nicht erst einfügen in die DB
# im Server sind auch noch zwei Punkte offen, siehe #$$



