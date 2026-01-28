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



# print(f"Modul os laden...")
# import os

# print(f"Modul torch laden...")
# import torch

# print(f"Modul clip  laden...")
# import clip

# print(f"Modul PIL laden...")
# from PIL import Image, ImageOps

# print(f"Modul pandas laden...")
# import pandas as pd



###### class CategoryInfo: ##############################################################################
###### Container für die Kategorien     #################################################################
class CategoryInfo:
    def __init__(self, user_text, seq_cat):
        self.sUserText = user_text
        self.seqCat = seq_cat

    def __repr__(self):
        return f"CategoryInfo(sUserText='{self.sUserText}', seqCat={self.seqCat})"

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
       self.vInit('piccat', 'piccatdb.py')

      
   ###### vInit(self, sPrjName, sAppName) ##############################################################################
   def vInit(self, sPrjName, sAppName):
      
      super().vInit(sPrjName, sAppName)

      try:
         self.sPcName = socket.gethostname()

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
         sModell224 =  self.Settings['Bildanalyse']['Modelle']['Modell224']
         sModell336  =  self.Settings['Bildanalyse']['Modelle']['Modell336']
         self.bAna = True if self.sModell == sModell224 or self.sModell == sModell336 else False

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

      except Exception as e:
         self.Exception2Log(f'Ausnahme in CBildAnalyse.vInit()',e)
         self.vScriptAbbruch("")

   ###### def EinstellungenInsLog(self) ##############################################################################
   def EinstellungenInsLog(self):
      try:

         sSett = f"PC: {self.sHostName} Einstellungen: Verzeichnis: {self.sDateipfad}, Ergebnisse --> {self.sErgebnisSpeicher} {self.sResultFile} "
         sSett += f"Dateien maximal: {self.iDateienMaximal}, Treffer maximal: {self.MaxTrefferAnzahl} "
         sSett += f"Modell: {self.sModell}, HalfPrec={'ja' if self.bHalfPrec else 'nein'}"
         self.Info2Log(sSett)

      except Exception as e:
         self.Exception2Log(f'Ausnahme in EinstellungenInsLog()',e)
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
            self.dictKat[rec[0]] = CategoryInfo(rec[1],rec[2])
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

         # self.dictKat[AiText] = CategoryInfo(Label, seqCat)
         self.en_prompts = [f"{key}" for key in self.dictKat.keys()]

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


   ###### AnalysiereEineDatei(self, sFsFile) ##############################################################################
   def AnalysiereEineDatei(self, sFsFile):
      self.Info2Log(f"AnalysiereEineDatei({sFsFile})...")
      try:
         with Image.open(sFsFile) as img:

            dtExif = self.GetExifDate( img)

            if  self.bAna == False:
               treffer_daten = []
               treffer_daten.append(("a photo of something else", 180))
               return True, dtExif, treffer_daten
#              return True, dtExif, None

            img = ImageOps.exif_transpose(img) # Korrigiert die Drehung basierend auf EXIF-Daten

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
    
            # Alle Treffer > 10% sammeln und sortieren
            treffer_daten = []
            iMore = 0
            for i, sAiText in enumerate(self.en_prompts):
                  iProzent = (int)(current_probs[i] * 100 + 0.5)
                  if iProzent > self.iMinTrefferProzent:   # Wir nehmen alle > xx%
                     treffer_daten.append((sAiText, iProzent))
                     iMore += 1
                     if iMore >= self.MaxTrefferAnzahl:
                        break

            if iMore > 1:
               # Sortieren der Liste nach dem zweiten Element (Prozentwert) absteigend
               treffer_daten.sort(key=lambda x: x[1], reverse=True)

            return True, dtExif, treffer_daten


      except Exception as e:
         self.Exception2Log(f'Ausnahme in AnalysiereEineDatei()',e)
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
         self.Info2Log(f"Dateien und Konfidenzen für {sFile}/{seqFile} aus der DB löschen...")

         sStmt = f"delete from {self.MariaDbName}.piccat_tab_confidence where seqFile = {seqFile}"
         cur.execute( sStmt)

         sStmt = f"delete from {self.MariaDbName}.piccat_tab_file where sName = ? and sSeqRun={self.iLaufNr}"
         cur.execute( sStmt, (sFile,))

      except Exception as e:
         self.Exception2Log(f'Ausnahme in DateiLoeschen()',e)
         return -1
      finally:
         pass

   ###### DbDateienLesen(self, sFolder, seqFolder, cur) ##############################################################################
   def DbDateienLesen(self, sFolder, seqFolder, cur):
      try:
         self.Info2Log(f"Dateien für {sFolder} (Seq: {seqFolder})  aus der DB lesen...")

         aDbFiles = {}

         sStmt = f"""SELECT f.sName, f.seqFile, f.seqRun, count(c.seqFile) 
                        FROM {self.MariaDbName}.piccat_tab_file f 
                        LEFT join {self.MariaDbName}.piccat_tab_confidence c ON  c.seqFile = f.seqFile 
                        WHERE f.seqFolder = ? GROUP BY f.seqFile"""

         cur.execute( sStmt, (seqFolder, ))
         rec = cur.fetchone()
         if rec == None:
            self.Info2Log(f'Keine Dateien zu Folder gefunden in piccat_tab_file')
         else:
            while rec != None:
               sName = rec[0]
               aDbFiles[sName] = CDbFileInfo(rec[1],seqFolder,rec[2], rec[3], bDelete=False)
               rec = cur.fetchone()

         return aDbFiles

      except Exception as e:
         self.Exception2Log(f'Ausnahme in DbDateienLesen()',e)
         return None
      finally:
         pass

   ###### Analysiere(self) ##############################################################################
   def Analysiere(self):
      try:
         self.Info2Log(f"Analysiere...")

         anzFolder = len(self.dbFolder)
         self.anzErlFolder = self.anzDateienErledigt = 0

         cur = self.mdb.cursor()

         fileCsv = open( self.sResultFile, "w", encoding="utf-8") if self.sErgebnisSpeicher == self.sErgCsv else None

         for sFolder, folderinfoDb in self.dbFolder.items():
            if folderinfoDb.bDelete:
               continue


            pfad = Path(sFolder) # Dateien aus dem Dateisystem lesen...
            fsFiles = {str(d): d.name for d in pfad.glob('*.jp*')}
            anzFsFiles = len(fsFiles)
            self.Info2Log(f"{anzFsFiles} Dateien aus {sFolder} ...")

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

               ret, dtExif, treffer_daten = self.AnalysiereEineDatei(sFsFile)
               if ret == False:
                  self.Error2Log(f'Fehler in Analysiere(): AnalysiereEineDatei({sFsFile}) == False'  )
               
               seqFile = -1
               if fileinfoDb == None:
                  seqFile = self.DateiAnlegen( folderinfoDb.seqFolder, sFsFileNameOnly, dtExif, cur)
               else:
                  seqFile = fiDb.seqFile

               if seqFile == -1:
                  continue

               sKonfi = ""
               if treffer_daten != None:
                  for sAiText, iKonfi in treffer_daten:
                     ci = self.dictKat.get(sAiText)

                     if self.sErgebnisSpeicher == self.sErgDb:
                        sStmt = f"INSERT INTO {self.MariaDbName}.piccat_tab_confidence (seqRun, seqFile, seqFolder, seqCategory, iConfidence) VALUES ( ?, ?, ?, ?, ?)"
                        cur.execute( sStmt, (self.iLaufNr, seqFile, folderinfoDb.seqFolder, ci.seqCat, iKonfi))
                     
                     elif self.sErgebnisSpeicher == self.sErgCsv:
                        if len(sKonfi) > 0:
                           sKonfi += ", "
                        sKonfi += f"{ci.sUserText}: {iKonfi}"

               if fileCsv != None:
                  sLine = f"{sFsFile}, {sExif}"
                  if len(sKonfi) > 0:
                     sLine += f", {sKonfi}"
                  fileCsv.write(f"{sLine}\n")

               self.anzDateienErledigt +=1
               if self.iDateienMaximal < self.anzDateienErledigt:
                  break

            sStmt = f"update {self.MariaDbName}.piccat_tab_file set seqRun = {self.iLaufNr} where seqFolder = {folderinfoDb.seqFolder}"
            cur.execute( sStmt)
            self.mdb.commit()

            if self.iDateienMaximal < self.anzDateienErledigt:
               break

            self.anzErlFolder +=1

         self.Info2Log(f"Erledigt. Verzeichnisse: ({self.anzErlFolder}/{anzFolder}), *.jp*-Dateien:  {self.anzDateienErledigt}/{self.iAllFiles}")
         
      except Exception as e:
         self.Exception2Log(f'Ausnahme in Analysiere()',e)
      finally:
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

         tEnd = datetime.datetime.now()
         sDau = self.sGetDauer( tEnd - tStartModulImport)
         sDauVerarb = self.sGetDauer( tEnd - self.tNow)

         return f"Bildanalyse erfolgreich: Gesamtdauer: {sDau}, Verarbeitungsdauer: {sDauVerarb}"

      except Exception as e:
         self.Exception2Log(f'Ausnahme in Abschluss()',e)
         return ""
      finally:
        cur.close()


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
      ba.InitialisiereModell()
      ba.Analysiere()

      ba.vEndeNormal( ba.Abschluss())

   except Exception as e:
      ba.Exception2Log(f'Ausnahme in main()',e)
      ba.vScriptAbbruch(f'Bildanalyse unvollständig oder abgebrochen.')
   finally:
      pass

      


if __name__ == "__main__":
    main(sys.argv)

#offen
# hier file/gesamte anzeigen: AnalysiereEineDatei(E:\Fotos und Bücher\2014\ArthurLotta\024.JPG)...
# Logausschriften reduzieren: nur noch für Folder
# Einstellungen nochmal am Ende ausgeben, auch die Laufnr


# KI auslagern
# import requests
# from io import BytesIO
# from PIL import Image

# def analyze_image_remote(image_path):
#     with Image.open(image_path) as img:
#         # Vorverarbeitung auf dem schwachen E570
#         img = img.convert('RGB').resize((224, 224))
        
#         # Bild in den Speicher schreiben statt auf Platte
#         buffer = BytesIO()
#         img.save(buffer, format="JPEG")
#         buffer.seek(0)
        
#         # Senden an den Django-Server
#         try:
#             response = requests.post(
#                 "http://dein-neuer-server:8000/api/analyze/",
#                 files={"image": ("image.jpg", buffer, "image/jpeg")}
#             )
#             return response.json() # Enthält deine 5 Kategorien
#         except Exception as e:
#             self.Exception2Log("API_Call", e)
#             return None

#views.py
# import torch
# import clip
# from PIL import Image
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser

# # Modell beim Starten des Servers einmalig laden (spart Zeit!)
# device = "cuda" if torch.cuda.is_available() else "cpu"
# model, preprocess = clip.load("ViT-B/32", device=device)

# class ImageAnalyzeView(APIView):
#     parser_classes = [MultiPartParser]

#     def post(self, request):
#         file_obj = request.FILES.get('image')
#         # Die Liste deiner Kategorien (sAiText aus deiner DB)
#         # In der Praxis würdest du diese aus der MariaDB laden
#         categories = ["a dog", "a cat", "a sunset", "architecture", "portrait"]
        
#         try:
#             # Bild laden und für CLIP vorbereiten
#             image = preprocess(Image.open(file_obj)).unsqueeze(0).to(device)
#             text = clip.tokenize(categories).to(device)

#             with torch.no_grad():
#                 # Berechnung der Wahrscheinlichkeiten
#                 logits_per_image, _ = model(image, text)
#                 probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

#             # Top 5 Ergebnisse zusammenstellen
#             results = []
#             for i in probs.argsort()[-5:][::-1]:
#                 results.append({
#                     "category": categories[i],
#                     "confidence": float(probs[i]) * 100
#                 })

#             return Response({"status": "success", "results": results})

#         except Exception as e:
#             return Response({"status": "error", "message": str(e)}, status=400)

# Nächste Schritte zur Umsetzung:
# Django Projekt aufsetzen: Hast du schon Erfahrung mit django-admin startproject?
# Kategorien-Sync: Soll der Server die Kategorien direkt aus der MariaDB lesen, damit Client und Server immer die gleichen Begriffe nutzen?
# Authentifizierung: Da die API im Netzwerk erreichbar ist, sollten wir einen einfachen API-Token einbauen, damit nur dein E570 darauf zugreifen darf.
# Soll ich dir zeigen, wie du den Kategorien-Abgleich zwischen MariaDB und der KI-Logik automatisierst?
# Dynamische Kategorien aus der DB laden
# API-Token Absicherung
# Deployment-Tipps für den neuen Server (Gunicorn/Nginx)