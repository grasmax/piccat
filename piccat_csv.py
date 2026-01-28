# Script zum Kategorisieren von Bildinhalten, Variante 2 mit englischen Begriffen und Prüfung gegen alle Kategorien
# 20.1.26. Auftrag an google gemini und chatcpt:
# "Gib mir einen Lösungsvorschlag für dieses Problem: Durchsuche einen Ordner und alle Unterordner 
# auf einem lokalen Festplattenlaufwerk eines PC mit Windows 10 Prof nach Dateien im jpg-Format,
# kategorisiere die gefundenen Dateien nach 
# "Architekturfragment", "Altar", "Treppe", "Blüte", "Blumenstrauß", "Landschaft", 
# "Wasser", "Dach", "Fenster", "Ikebana", "Pflanze an Mauer", "Tiere", "Schmetterlinge", 
# "Katzen", "Hunde", "Tische und Stühle", "Dekoration", "Flaschen und Gläser", "Speisen und Getränke", 
# "Stillleben", "Wegweiser", "Weihnachtsfest" 
# und erstelle eine Liste mit drei Spalten (Ordner, Dateiname, Kategorie)"

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


import time
import datetime
tStart = datetime.datetime.now()
print( f"Programmstart: {tStart}")


import sys
print(f"sys.executable: {sys.executable}")
print(f"sys.path: {sys.path}")
# ['E:\\dev_priv\\python_svn\\piccat', 'E:\\dev_priv\\python_svn\\piccat', 'E:\\dev_priv\\python_3_12_9_64\\python312.zip', 
#  'E:\\dev_priv\\python_3_12_9_64\\DLLs', 'E:\\dev_priv\\python_3_12_9_64\\Lib', 'E:\\dev_priv\\python_3_12_9_64', 
#  'E:\\dev_priv\\python_svn\\piccat\\ki_env_64', 'E:\\dev_priv\\python_svn\\piccat\\ki_env_64\\Lib\\site-packages']

import platform, struct
print(f"Python Version: {platform.python_version()}")
print(f"Architektur: {struct.calcsize('P') * 8} Bit")
# Python Version: 3.12.9
# Architektur: 64 Bit

# Einstellungen:
root_dir = r'd:\piccat' 
sResultFile = 'bild_analyse_gefiltert_2026.csv'
iMaxFiles = -1
sMaxFiles = f", nur {iMaxFiles} Dateien" if iMaxFiles > 0 else ""
bHalfPrec = False # True
print(f"Einstellungen: Verzeichnis: {root_dir}, Ergebnisdatei: {sResultFile}{sMaxFiles}, HalfPrec={'ja' if bHalfPrec else 'nein'}")


print(f"Modul os laden...")
import os

print(f"Modul torch laden...")
import torch

print(f"Modul clip  laden...")
import clip

print(f"Modul PIL laden...")
from PIL import Image, ImageOps

print(f"Modul pandas laden...")
import pandas as pd

def sGetDauer(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# Konfiguration & Übersetzung für bessere KI-Erkennung
# Wir nutzen englische Prompts für die KI (maximal 100 Zeichen), behalten aber deutsche Labels für die Liste
kategorien_dict = {
    "Gesicht": "facial expression",
    "Mensch": "Individual people or groups of people",
    "Architekturfragment": "a fragment of architecture",
    "Gebäude": "A fragment of a building structure",
    "Straßenpflaster": "Paved paths or streets",
    "Strand": "Beach at the ocean",
    "Himmel": "Sky with or without clouds",
    "Schiffe": "Sailing ships, sailboats and steamships",
    "Altar": "altar",
    "Treppe": "stairs",
    "Blüte": "blossom",
    "Blumenstrauß": "bouquet of flowers",
    "Landschaft": "landscape photography",
    "Wasser": "water or lake",
    "Dach": "roof",
    "Fenster": "window",
    "Ikebana": "ikebana flower arrangement",
    "Pflanze an Mauer": "plant growing on a wall",
    "Tiere": "animals",
    "Schmetterlinge": "butterfly",
    "Katzen": "cat",
    "Hunde": "dog",
    "Tische und Stühle": "tables and chairs",
    "Dekoration": "decoration",
    "Flaschen und Gläser": "bottles and glasses",
    "Speisen und Getränke": "food and drinks",
    "Stillleben": "still life photography",
    "Wegweiser": "signpost",
    "Weihnachtsfest": "christmas celebration",
    "Inneneinrichtung": "Interior decoration",
    "Kirche": "a photo of a church building, cathedral or chapel",
    "Landkarten und Wetterkarten": "Maps and weather maps",
    "Burg/Schloss": "a medieval castle or a royal palace architecture",
    "Sonstiges": "a photo of something else"
}

de_labels = list(kategorien_dict.keys())
en_prompts = [f"a photo of {val}" for val in kategorien_dict.values()]

# Cuda ist für nvidia-Grafikkarten und erfordert die Installation des Cuda-Toolkits
device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Modell {device} laden...")
#model, preprocess = clip.load("ViT-B/32", device=device)
model, preprocess = clip.load("ViT-L/14@336px", device=device)

if device == "cuda" and bHalfPrec:
   #1+2model.half() # Nutzt die Tensor-Cores der RTX 5060 Ti optimal aus
   #2 for param in model.parameters():
   #2    param.data = param.data.to(torch.float16)
   #3model.to(torch.float16)
   #4:
   model.float() # Erst sicherstellen, dass alles Float ist
   clip.model.convert_weights(model) # Dann gezielt in Half konvertieren

print(f"clip.tokenize...")
text_inputs = clip.tokenize(en_prompts).to(device)

print(f"Dateianzahl ermitteln...")
iAllFiles = 0
for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.lower().endswith((".jpg", ".jpeg")):
           iAllFiles += 1
if iMaxFiles <= 0:
   iMaxFiles = iAllFiles
print(f"Dateianzahl (*.jpg,*.jpeg): {iAllFiles}, davon zu analysieren: {iMaxFiles} ")

tStartVerarb = datetime.datetime.now()
print(f"Verarbeitung beginnt um {tStartVerarb}")
results = []
iFiles = 0
dSizeMB = 0.0

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if iFiles >= iMaxFiles:
           break
        if file.lower().endswith((".jpg", ".jpeg")):
            img_path = os.path.join(root, file)

            try:
               dSizeMB += os.path.getsize(img_path) / (1024 * 1024)

               with Image.open(img_path) as img:

                  sAufnahmedatum = "Unbekannt"
                  exif_data = img.getexif()
                  if exif_data:
                      # 36867 ist die Standard-ID für 'DateTimeOriginal' (Aufnahmedatum)
                       # Alternativ kann 306 ('DateTime') genutzt werden
                       sAufnahmedatum = exif_data.get(36867) or exif_data.get(306) or "Unbekannt"

                  img = ImageOps.exif_transpose(img) # Korrigiert die Drehung basierend auf EXIF-Daten

                  # Konvertierung zu RGB verhindert Fehler bei Graustufen-JPEGs
                  if bHalfPrec:
                     image = preprocess(img.convert("RGB")).unsqueeze(0).to(device).half()
                  else:
                     image = preprocess(img.convert("RGB")).unsqueeze(0).to(device)

                  with torch.no_grad():
                     logits_per_image, _ = model(image, text_inputs)
                     probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]
                  # würde bei half auch funktionieren:
                  #  probs = logits_per_image.float().softmax(dim=-1).cpu().numpy()[0]

                  # probs[0] extrahieren, da CLIP oft eine Batch-Dimension zurückgibt
                  current_probs = probs[0] if len(probs.shape) > 1 else probs
    
                  # 1. Haupt-Kategorie (Bestwert) ermitteln
                  idx = current_probs.argmax()
                  best_cat = de_labels[idx]
                  best_prob_val = current_probs[idx] * 100
                  best_prob_str = f"{best_prob_val:.2f}" # in Prozent

                  # 2. Alle Treffer > 10% sammeln und sortieren
                  treffer_daten = []
                  iMore = 0
                  for i, cat_name in enumerate(de_labels):
                      prozent = current_probs[i] * 100
                      # Wir nehmen alle > 10%, außer der bereits identifizierten besten Kategorie
                      if prozent > 10.0 and cat_name != best_cat:
                          treffer_daten.append((cat_name, prozent))
                          iMore += 1
                          if iMore > 5:
                             break

                  if iMore > 0:
                     # Sortieren der Liste nach dem zweiten Element (Prozentwert) absteigend
                     treffer_daten.sort(key=lambda x: x[1], reverse=True)

                     # Umwandeln der sortierten Liste in das gewünschte String-Format
                     treffer_liste = [f"{name}: {p:.2f}" for name, p in treffer_daten]
                     treffer_string = ", ".join(treffer_liste)

                     # 3. Den Datensatz für die Zeile zusammenbauen
                     row = [f"{img_path}: {sAufnahmedatum}", f"{best_cat}: {best_prob_str}", treffer_string]
                     print(f"{iFiles+1}/{iAllFiles}  {img_path}: {sAufnahmedatum} -> {best_cat} {best_prob_str} sowie in {treffer_string}")
                  else:
                     row = [f"{img_path}: {sAufnahmedatum}", best_cat, best_prob_str]
                     print(f"{iFiles+1}/{iAllFiles}  {img_path}: {sAufnahmedatum} -> {best_cat} {best_prob_str}")
                  results.append(row)
                  iFiles += 1
                  


            except Exception as e:
               print(f"Fehler bei {img_path}: {e}")


print("Export beginnt...")

sDau = sGetDauer( datetime.datetime.now() - tStart)
sDauVerarb = sGetDauer( datetime.datetime.now() - tStartVerarb)

row = [f"Dateien: {iFiles}", f"Größe: {dSizeMB} MB", f"Gesamtdauer: {sDau}, Verarbeitungsdauer: {sDauVerarb}"]
print(f"Dateien: {iFiles} Größe: {dSizeMB}MB Gesamtdauer: {sDau} Verarbeitungsdauer: {sDauVerarb}")
results.append(row)


df = pd.DataFrame(results, columns=["Dateipfad", "Beste Kategorie: Konfidenz", "max 5 weitere Treffer > 10%"])
df.to_csv(sResultFile, index=False, encoding="utf-8-sig")
print(f"\nAnalyse abgeschlossen. Datei {sResultFile} wurde erstellt.")


