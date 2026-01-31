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

from pathlib import Path

from PIL import Image, ImageOps

import socket

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

from tqdm import tqdm  # Fortschrittsanzeige
import io

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
         self.anzErlFolder = self.anzDateienErledigt = 0

         self.sAufgabe =  self.Settings['Bildanalyse']['Aufgabe']
         self.sAufgabeVoll =  self.Settings['Bildanalyse']['Aufgaben']['AufgabeVoll']
         self.sAufgabeNeu  =  self.Settings['Bildanalyse']['Aufgaben']['AufgabeNeu']

         self.iDateienMaximal  =  self.Settings['Bildanalyse']['DateienMaximal']
         self.sModell =  self.Settings['Bildanalyse']['Modell']
         self.sModell224 =  self.Settings['Bildanalyse']['Modelle']['Modell224']
         self.sModell336  =  self.Settings['Bildanalyse']['Modelle']['Modell336']
         self.bAna = True if self.sModell == self.sModell224 or self.sModell == self.sModell336 else False

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
         self.bSend2Server = True if self.sOrt == self.sOrtServer else False
         if self.bSend2Server:
            self.sServerIp = self.Settings['Server']['IP'] 
            self.url_base = f"http://{self.sServerIp}:8000"
            self.session = requests.Session() # Wichtig für Performance (Keep-Alive)

         self.dCallMinSec = sys.float_info.max  # schnellster Server-Ruf in Sekunden
         self.dCallMaxSec = 0.0  # schnellster langsamster-Ruf  in Sekunden
         self.dCallSumSec = 0.0  # im Server verbrachte Zeitdauer  in Sekunden


      except Exception as e:
         self.Exception2Log(f'Ausnahme in CBildAnalyse.vInit()',e)
         self.vScriptAbbruch("")

   ###### def EinstellungenInsLog(self) ##############################################################################
   def EinstellungenInsLog(self):
      try:
         sSett = f"""Beginn: {self.sNow} PC: {self.sHostName} Einstellungen: Verzeichnis: {self.sDateipfad}, 
                  Ergebnisse --> {self.sErgebnisSpeicher} {self.sResultFile if self.sErgebnisSpeicher == self.sErgCsv else ""} 
                  Aufgabe: {self.sAufgabe} Dateien maximal: {self.iDateienMaximal}, Treffer maximal: {self.MaxTrefferAnzahl} 
                  MinTrefferProzent: {self.iMinTrefferProzent}
                  Analyse: {self.sOrt} {self.sServerIp if self.sOrt==self.sOrtServer else ""} {self.url_base if self.sOrt==self.sOrtServer else ""}
                  Modell: {self.sModell}, HalfPrec={'ja' if self.bHalfPrec else 'nein'}"""
         self.Info2Log(sSett)

      except Exception as e:
         self.Exception2Log(f'Ausnahme in EinstellungenInsLog()',e)
         self.vScriptAbbruch("")


   ###### def ErgebnisseInsLog(self) ##############################################################################
   def ErgebnisseInsLog(self):
      try:
         tEnd = datetime.datetime.now()
         sDau = self.sGetDauer( tEnd - tStartModulImport)
         sDauVerarb = self.sGetDauer( tEnd - self.tNow)

         sResult = f"""LaufNr: {self.iLaufNr} Anzahl Kategorien: {len(self.dictKat)} Anzahl Verzeichnisse: {len(self.fsFolder)} 
                  Anzahl DB-Verzeichnisse: {len(self.dbFolder)} davon erledigt: {self.anzErlFolder} 
                  Anzahl Dateien: {self.iAllFiles} davon erledigt: {self.anzDateienErledigt} 
                  Schnellste Bildanalyse: {self.dCallMinSec} langsamste Bildanalyse: {self.dCallMaxSec} 
                  Anteil der Bildanalyse an der Verarbeitungsdauer: {self.dCallSumSec} 
                  Gesamtdauer: {sDau}, Verarbeitungsdauer: {sDauVerarb}
                    """
         self.Info2Log(sResult)

      except Exception as e:
         self.Exception2Log(f'Ausnahme in ErgebnisseInsLog()',e)
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
         self.Exception2Log(f'Ausnahme in ErmittleLaufNummer()',e)
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
         self.Exception2Log(f'Ausnahme in GibNeueLaufNummer()',e)
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
         self.Exception2Log(f'Ausnahme in LiesKategorien()',e)
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
         self.Exception2Log(f'Ausnahme in VerzeichnisLoeschen()',e)
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
         self.Exception2Log(f'Ausnahme in VerzeichnisAnlegen()',e)
      finally:
         pass


   ###### AktualisiereVerzeichnisse(self) ##############################################################################
   def AktualisiereVerzeichnisse(self):
      try:
         self.Info2Log(f"Unterverzeichnisse zu {self.sDateipfad} aus dem Dateisystem lesen...")

         pfad = Path(self.sDateipfad)
         self.fsFolder = {str(d): d.name for d in pfad.rglob('*') if d.is_dir()}

         self.fsFolder[self.sDateipfad] = self.sDateipfad

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


         #$$sStmt = f"update {self.MariaDbName}.piccat_tab_folder set seqRun = {self.iLaufNr}"
         #$$cur.execute( sStmt)
         self.mdb.commit()
   
      except Exception as e:
         self.Exception2Log(f'Ausnahme in AktualisiereVerzeichnisse()',e)
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
         self.Exception2Log(f'Ausnahme in ErmittleDateiAnzahl()',e)
    
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
         self.Exception2Log(f'Ausnahme in InitialisiereModell()',e)
      finally:
         pass

   ###### Zeitmessung(self, tStart) ##############################################################################
   def Zeitmessung(self, tStart):

      stopSrv = time.perf_counter()

      dau = stopSrv - tStart

      if dau < self.dCallMinSec:
         self.dCallMinSec = dau

      if self.dCallMaxSec < dau:
         self.dCallMaxSec = dau

      self.dCallSumSec += dau  # Zeitdauer  in Sekunden



   ###### AnalysiereEineDateiLokal(self, sFsFile) ##############################################################################
   def AnalysiereEineDateiLokal(self, sFsFile):
      #self.Info2Log(f"AnalysiereEineDateiLokal({sFsFile})...")
      try:
         with Image.open(sFsFile) as img:

            dtExif = self.GetExifDate( img)

            if  self.bAna == False:
               treffer_daten = []
               treffer_daten.append((43, 180)) # "a photo of something else"
               return True, dtExif, treffer_daten
#              return True, dtExif, None

            img = ImageOps.exif_transpose(img) # Korrigiert die Drehung basierend auf EXIF-Daten

            
            tStartAna = time.perf_counter()

            # Konvertierung zu RGB verhindert Fehler bei Graustufen-JPEGs
            if self.bHalfPrec:
               image = self.preprocess(img.convert("RGB")).unsqueeze(0).to(self.device).half()
            else:
               image = self.preprocess(img.convert("RGB")).unsqueeze(0).to(self.device)

            with torch.no_grad():
               logits_per_image, _ = self.model(image, self.text_inputs)
               probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]
            # würde bei half auch funktionieren:
            #  probs = logits_per_image.float().softmax(dim=-1).cpu().numpy()[0]

            # probs[0] extrahieren, da CLIP oft eine Batch-Dimension zurückgibt
            current_probs = probs[0] if len(probs.shape) > 1 else probs
    
            self.Zeitmessung(tStartAna)

            # Alle Treffer > 10% sammeln und sortieren
            treffer_daten = []
            iMore = 0
            for i, sAiText in enumerate(self.en_prompts):
                  iProzent = (int)(current_probs[i] * 100 + 0.5)
                  if iProzent > self.iMinTrefferProzent:   # Wir nehmen alle > xx%
                     treffer_daten.append( (self.aSeqCat[i], iProzent))
                     iMore += 1
                     if iMore >= self.MaxTrefferAnzahl:
                        break

            if iMore > 1:
               # Sortieren der Liste nach dem zweiten Element (Prozentwert) absteigend
               treffer_daten.sort(key=lambda x: x[1], reverse=True)

            return True, dtExif, treffer_daten


      except Exception as e:
         self.Exception2Log(f'Ausnahme in AnalysiereEineDateilokal()',e)
         return False, None, None
      finally:
        pass

   ###### AnalysiereEineDateiServer(self, sFsFile, sFsFileNameOnly) ##############################################################################
   def AnalysiereEineDateiServer(self, sFsFile, sFsFileNameOnly):
      #self.Info2Log(f"AnalysiereEineDateiServer({sFsFileNameOnly})...")
      try:
         with Image.open(sFsFile) as img:

            dtExif = self.GetExifDate( img)

            if  self.bAna == False:
               treffer_daten = []
               treffer_daten.append((43, 180)) # "a photo of something else"
               return True, dtExif, treffer_daten
#              return True, dtExif, None

            #lokale Vorarbeiten: u.a.Dateigröße minimieren
            img = ImageOps.exif_transpose(img) # Korrigiert die Drehung basierend auf EXIF-Daten

            #Verkleinern, LANCZOS sorgt für hohe Qualität beim Resampling
            if self.sModell ==  self.sModell224:
               img = img.resize((224, 224), Image.Resampling.LANCZOS)
            elif  self.sModell ==  self.sModell236:
               img = img.resize((336, 336), Image.Resampling.LANCZOS)

            img_byte_arr = io.BytesIO()# Bild in Byte-Array umwandeln
            img.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0) # Zurück zum Anfang des Buffers springen

            files = {'image': (sFsFileNameOnly, img_byte_arr, 'image/jpeg')}
            payload = {'lfdNr': self.anzDateienErledigt+1} # seqFile hier noch nicht bekannt

            jret = None
            try:
               tStartAna = time.perf_counter()

               response = self.session.post(f"{self.url_base}/analyze", files=files, data=payload,timeout=20)

               self.Zeitmessung(tStartAna)# im Server verbrachte Zeitdauer  in Sekunden

               if response.status_code != 200:
                  self.Error2Log(f"Fehler in AnalysiereEineDateiServer({sFsFileNameOnly}: {self.url_base}/analyze: response.status_code: {response.status_code}")
                  return False, dtExif, None
               jret = response.json()
            except Exception as e:
               self.Exception2Log(f'Ausnahme in AnalysiereEineDateiServer({sFsFileNameOnly})',e)

            treffer_daten = []
            for t in range(5):
               iProzent = jret["p"][t]
               if self.iMinTrefferProzent < iProzent:
                  treffer_daten.append((jret["c"][t], iProzent))

            return True, dtExif, treffer_daten

      except Exception as e:
         self.Exception2Log(f'Ausnahme in AnalysiereEineDateiServer()',e)
         return False, None, None
      finally:
        pass


   ###### DateiAnlegen(self, seqFolder, sFile, dtExif, cur) ##############################################################################
   def DateiAnlegen(self, seqFolder, sFile, dtExif, cur):
      try:
         sStmt = f"SELECT NEXT VALUE FOR {self.MariaDbName}.piccat_seq_file;"
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
         self.Exception2Log(f'Ausnahme in DateiAnlegen()',e)
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
         self.Exception2Log(f'Ausnahme in DateiLoeschen({sFile}/{seqFile})',e)
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
         self.Exception2Log(f'Ausnahme in DbDateienLesen({sFolder} (Seq: {seqFolder}))',e)
         return None
      finally:
         pass

   ###### Analysiere(self) ##############################################################################
   def Analysiere(self):
      try:
         self.Info2Log(f"Analysiere...")

         pbar = tqdm(total=self.iAllFiles, desc="Bild-Analyse", leave=True)

         anzFolder = len(self.dbFolder)
         self.anzErlFolder = self.anzDateienErledigt = 0

         cur = self.mdb.cursor()

         fileCsv = None
         if self.sErgebnisSpeicher == self.sErgCsv:
            fileCsv = open( self.sResultFile, "w", encoding="utf-8") if self.sErgebnisSpeicher == self.sErgCsv else None

         for sFolder, folderinfoDb in self.dbFolder.items():
            if folderinfoDb.bDelete:
               continue


            pfad = Path(sFolder) # Dateien aus dem Dateisystem lesen...
            fsFiles = {str(d): d.name for d in pfad.glob('*.jp*')}
            anzFsFiles = len(fsFiles)
            #self.Info2Log(f"{anzFsFiles} Dateien aus {sFolder} ...")

            aDbFiles = self.DbDateienLesen( sFolder, folderinfoDb.seqFolder, cur) # aus DB lesen
            if aDbFiles != None:
               for sDbFile, fiDb in aDbFiles.items():
                  bDelete = True if fsFiles.get(f"{sFolder}\\{sDbFile}") is None else False
                  if bDelete:
                     self.DateiLoeschen( fiDb.seqFile, sDbFile, cur)

            # Dateien analysieren und Ergebnisse speichern, aber nur die, die noch keine Konfidenz haben:
            for sFsFile, sFsFileNameOnly in fsFiles.items():
               fileinfoDb = aDbFiles.get(sFsFileNameOnly)
               if fileinfoDb != None:
                  if fileinfoDb.iConfi > 0:
                     continue

               pbar.set_postfix(file=sFsFileNameOnly)

               if self.bSend2Server:
                  ret, dtExif, treffer_daten = self.AnalysiereEineDateiServer(sFsFile, sFsFileNameOnly)
               else: 
                  ret, dtExif, treffer_daten = self.AnalysiereEineDateiLokal(sFsFile)
               if ret == False:
                  self.Error2Log(f'Fehler in Analysiere(): AnalysiereEineDatei*({sFsFile}) == False'  )
               
               seqFile = -1
               if fileinfoDb == None:
                  seqFile = self.DateiAnlegen( folderinfoDb.seqFolder, sFsFileNameOnly, dtExif, cur)
               else:
                  seqFile = fiDb.seqFile

               if seqFile == -1:
                  continue

               sKonfi = ""
               if treffer_daten != None:
                  for seqCat, iKonfi in treffer_daten:
                     catinfo = self.dictKat.get(seqCat)

                     if self.sErgebnisSpeicher == self.sErgDb:
                        sStmt = f"INSERT INTO {self.MariaDbName}.piccat_tab_confidence (seqRun, seqFile, seqFolder, seqCategory, iConfidence) VALUES ( ?, ?, ?, ?, ?)"
                        cur.execute( sStmt, (self.iLaufNr, seqFile, folderinfoDb.seqFolder, seqCat, iKonfi))
                     
                     elif self.sErgebnisSpeicher == self.sErgCsv:
                        if len(sKonfi) > 0:
                           sKonfi += ", "
                        sKonfi += f"{catinfo.sUserText}: {iKonfi}"

               if fileCsv != None:
                  sLine = f"{sFsFile}, {sExif}"
                  if len(sKonfi) > 0:
                     sLine += f", {sKonfi}"
                  fileCsv.write(f"{sLine}\n")

               pbar.update(1)
               self.anzDateienErledigt +=1
               if self.iDateienMaximal < self.anzDateienErledigt:
                  break

            sStmt = f"update {self.MariaDbName}.piccat_tab_file set seqRun = {self.iLaufNr} where seqFolder = {folderinfoDb.seqFolder}"
            cur.execute( sStmt)
            self.mdb.commit()

            if self.iDateienMaximal < self.anzDateienErledigt:
               break

            self.anzErlFolder +=1

         #self.Info2Log(f"Erledigt. Verzeichnisse: ({self.anzErlFolder}/{anzFolder}), *.jp*-Dateien:  {self.anzDateienErledigt}/{self.iAllFiles}")
         
      except Exception as e:
         self.Exception2Log(f'Ausnahme in Analysiere()',e)
      finally:
        pbar.close()
        cur.close()
        if fileCsv != None:
           fileCsv.close() 

   ###### Abschluss(self) ##############################################################################
   def Abschluss(self):
      try:
         sStmt = f'update {self.MariaDbName}.piccat_tab_run set tEnd = now(6) where seqRun = {self.iLaufNr}'
         cur = self.mdb.cursor()
         cur.execute( sStmt)
         self.mdb.commit()

         self.EinstellungenInsLog()
         self.ErgebnisseInsLog()

         return f"Bildanalyse erfolgreich."

      except Exception as e:
         self.Exception2Log(f'Ausnahme in Abschluss()',e)
         return ""
      finally:
        cur.close()


   ###### init_brain_on_ryzen(self) initialisert die Verbindung zum Server. Dort muss piccat_server.py gestartet sein
   def init_brain_on_ryzen(self):
      """Liest Kategorien aus DB und initialisiert das Brain."""
      self.Info2Log("Initialisiere Brain auf Ryzen...")
      cur = self.mdb.cursor()
      cur.execute(f"SELECT seqCat, sAiText FROM {self.MariaDbName}.piccat_tab_category")
        
      # Format für die API:
      cat_list = [{"id": r[0], "text": r[1]} for r in cur.fetchall()]
      cur.close()

      cl = {
         "categories": cat_list, # Ihre vorhandene Kategorien-Liste
         "total_items": 7777      # Der neue Integer-Wert
      }

      try:
         resp = self.session.post(f"{self.url_base}/init_brain", json=cl, timeout=20)
         self.Info2Log("{self.url_base}/init_brain:", resp.json())
         if resp.status_code != 200:
            self.vScriptAbbruch(f"Fehler in init_brain_on_ryzen(): {self.url_base}/init_brain liefert resp.status_code {resp.status_code}")

      except Exception as e:
         self.Exception2Log(f'Ausnahme in init_brain_on_ryzen()',e)
         return False




###### CBildAnalyse } ##############################################################################

def main(argv):
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


      ba.AktualisiereVerzeichnisse()    # nicht mehr vorhandene Verzeichnisse aus DB löschen und neue einfügen, alle mit aktueller Nummer speichern
      ba.ErmittleDateiAnzahl()

      ba.LiesKategorien()

      if ba.bSend2Server:
         ba.init_brain_on_ryzen()   # für Bildanalyse auf einem separaten Server
      else:
         ba.InitialisiereModell()   # für lokale Bildanalyse

      ba.Analysiere()

      ba.vEndeNormal( ba.Abschluss())

   except Exception as e:
      ba.Exception2Log(f'Ausnahme in main()',e)
      ba.vScriptAbbruch(f'Bildanalyse unvollständig oder abgebrochen.')
   finally:
      pass

if __name__ == "__main__":
    main(sys.argv)


