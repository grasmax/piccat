

import requests, datetime, time, sys
import io

from PIL import Image, ImageOps
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor


import logging
from time import sleep

import os

import json

import mariadb
import base64

from gmbasis import CBaseApp

import socket # für GetHostname


###### PicCatWorker ##############################################################################
class PicCatWorker (CBaseApp):

   ###### __init__(self) ##############################################################################
   def __init__(self):
       super().__init__()
       self.bUseSunSettings = False
       self.vInit('piccat', 'piccat_client.py')

      
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

         self.sServerIp = self.Settings['Server']['IP'] 
         self.url_base = f"http://{self.sServerIp}:8000"
         self.session = requests.Session() # Wichtig für Performance (Keep-Alive)

      except Exception as e:
         self.Exception2Log(f'Ausnahme in CBildAnalyse.vInit()',e)
         self.vScriptAbbruch("")


   def init_brain_on_ryzen(self):
        """Liest Kategorien aus DB und initialisiert das Brain."""
        print("Initialisiere Brain auf Ryzen...")
        cur = self.mdb.cursor()
        cur.execute(f"SELECT seqCat, sAiText FROM {self.MariaDbName}.piccat_tab_category")
        
        # Format für die API:
        cat_list = [{"id": r[0], "text": r[1]} for r in cur.fetchall()]
        cur.close()

        try:
            resp = self.session.post(f"{self.url_base}/init_brain", json=cat_list, timeout=20)
            print("Brain Status:", resp.json())
            return resp.status_code == 200
        except Exception as e:
            print(f"Fehler bei Init: {e}")
            return False

   def process_single_image(self, img_info):
        """Verarbeitet ein einzelnes Bild: Resize -> Send -> Save"""
        seqFile, sPath = img_info
        
        try:
            # 1. Bild auf E570 vorverarbeiten (Resize auf 224x224)
            with Image.open(sPath) as img:
                img_resized = img.convert('RGB').resize((224, 224))
                buf = io.BytesIO()
                img_resized.save(buf, format="JPEG", quality=85)
                img_bytes = buf.getvalue()

            # 2. An Ryzen senden (mit Retry-Logik falls Ryzen rebootet)
            files = {'file': ('img.jpg', img_bytes, 'image/jpeg')}
            data = {'seqFile': seqFile}
            
            # Timeout von 30s, falls der Ryzen gerade hängt
            resp = self.session.post(f"{self.url_base}/analyze", files=files, data=data, timeout=30)
            result = resp.json()

            if "error" in result:
                # Falls Brain die Init verloren hat (nach Reboot)
                if "nicht initialisiert" in result["error"]:
                    self.init_brain_on_ryzen()
                return False

            # 3. Ergebnisse (Top 5) in MariaDB schreiben
            # result['c'] sind die IDs, result['p'] die Prozente
            self.save_results_to_db(seqFile, result['c'], result['p'])
            return True

        except Exception as e:
            # Hier greift deine neue Exception2Log Methode
            return False

   def save_results_to_db(self, seqFile, cat_ids, confidences):
        """Schreibt die 5 Treffer in piccat_tab_confidence"""
        # Hier nutzt du am besten ein Batch-Verfahren oder ein vorbereitetes Statement
        cur = self.db.mdb.cursor()
        for c_id, prob in zip(cat_ids, confidences):
            # Nutze deine SQL-Struktur
            sStmt = "INSERT INTO piccat_tab_confidence (seqFile, seqCategory, iConfidence, seqRun, seqFolder) VALUES (?, ?, ?, ?, ?)"
            # ... (Werte ergänzen) ...
            cur.execute(sStmt, (seqFile, c_id, prob, 1, 1)) # Beispielwerte
        self.db.mdb.commit()

   def run_mass_analysis(self, image_list):
        """Startet die Analyse mit Fortschrittsbalken und Threads"""
        # 4-8 Threads sind ideal für den E570 I7, um I/O zu maskieren
        with ThreadPoolExecutor(max_workers=5) as executor:
            list(tqdm(executor.map(self.process_single_image, image_list), 
                      total=len(image_list), desc="Gesamtfortschritt"))

   def send_with_retry(data, files, max_retries=5):
       for i in range(max_retries):
           try:
               return requests.post(url, files=files, data=data, timeout=30)
           except requests.exceptions.ConnectionError:
               print(f"Server nicht erreichbar. Versuch {i+1} in 30 Sek...")
               time.sleep(30) # Wartezeit, falls der Ryzen gerade rebootet
       return None

   def SendeTestbild(self):
   
      sFile = "E:\\Fotos und Bücher\\2008\\Sommergarten\\20080706_104419_Sommergarten 002.jpg"

      # Bild binär öffnen und senden
      with Image.open(sFile) as img:

         img = ImageOps.exif_transpose(img) # Korrigiert die Drehung basierend auf EXIF-Daten

         # 3. Verkleinern auf exakt 224x224 Pixel
         # LANCZOS sorgt für hohe Qualität beim Resampling
         img = img.resize((224, 224), Image.Resampling.LANCZOS)

         # 4. Bild im Speicher "zwischenspeichern", statt auf Festplatte
         img_byte_arr = io.BytesIO()
         img.save(img_byte_arr, format='JPEG')
         img_byte_arr.seek(0) # Zurück zum Anfang des Buffers springen

         # 5. Übermittlung an den Ryzen-Server
         files = {'image': ('cat.jpg', img_byte_arr, 'image/jpeg')}

         # Die Sequenz der Kategorie (seqFile) wird über 'data' gesendet
         payload = {'seqFile': 12} # Blumenstrauß

   
         try:
            response = self.session.post(f"{self.url_base}/analyze", files=files, data=payload,timeout=20)
            jret = response.json()
            return jRet
         except Exception as e:
            return {"status": "error", "message": str(e)}

         # # Ergebnis prüfen
         # if response.status_code == 200:
         #       print("Analyse-Ergebnis:", response.json())
         # else:
         #       print(f"Fehler {response.status_code}: {response.text}")


# Start des Prozesses
if __name__ == "__main__":
    pcw = PicCatWorker() 
    pcw.VerbindeMitMariaDb()            # Verbindung zur DB herstellen, zweite Verbindung fürs Log

    if pcw.init_brain_on_ryzen():
         pcw.SendeTestbild()
         # Beispiel: Liste von (ID, Pfad) aus deiner piccat_tab_file laden
         # image_list = worker.load_pending_images() 
         # worker.run_mass_analysis(image_list)
         pass

