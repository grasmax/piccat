#gemini 29.1.26

#Start mit nur einem Thread: python piccat_server.py
# oder
# python startsrv.py
# # import uvicorn
# # if __name__ == "__main__":
# #     uvicorn.run(
# #         "piccat_server:app", 
# #         host="0.0.0.0", 
# #         port=8000, 
# #         workers=4,
# #         loop="asyncio", # Explizit auf asyncio setzen
# #         timeout_keep_alive=5
# #     )

# Start mit 4 Threads:
# startsrv.bat




#automatischer Neustart:
# @echo off
# title PicCat Brain Server
# :loop
# echo Starte PicCat Server...
# :: Pfad zu deinem venv und dem Skript
# call C:\dev\python\piccat\ki_env\Scripts\activate
# python C:\dev\python\piccat\piccat_server.py
# echo Server wurde beendet oder ist abgestürzt. Neustart in 5 Sekunden...
# timeout /t 5
# goto loop

import os
import io
import struct
import requests

import signal

print("Lade torch") 
import torch
from torchvision import transforms

print("Lade clip") 
import clip

print("Lade weitere Module") 
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form
from typing import List, Dict

print("Uvicorn") 
import uvicorn
print("Uvicorn-Ende") 

from pydantic import BaseModel 
from tqdm import tqdm

app = FastAPI(title="PicCat AI Brain - API Mode")

# Definiere ein Pydantic Modell, das die erwartete Struktur beschreibt
class InitRequest(BaseModel):
    categories: List[Dict]
    total_items: int # Der neue Integer-Wert


# Globale Variablen
device = "cuda" if torch.cuda.is_available() else "cpu"
model = None
preprocess = None
text_features = None
category_ids = []  # Liste der seqCat IDs
global_pbar = None
max_files = 0
files_done = 0

# Modell beim Import/Start einmalig laden
print(f"--- Lade CLIP Modell auf {device} ---")
#model, preprocess = clip.load("ViT-B/32", device=device)
model, preprocess = clip.load("ViT-L/14@336px", device=device)


# Fragmente aus den Versuchen mit bHalfPrec
#  if self.device == "cuda" and self.bHalfPrec:
#             #1+2model.half() # Nutzt die Tensor-Cores der RTX 5060 Ti optimal aus
#             #2 for param in model.parameters():
#             #2    param.data = param.data.to(torch.float16)
#             #3model.to(torch.float16)
#             #4:
#             self.model.float() # Erst sicherstellen, dass alles Float ist
#             clip.model.convert_weights(self.model) # Dann gezielt in Half konvertieren

# diese Ausschriften unterdrücken, um eine vernüftige Fortschrittsanzeige zu bekommen:
# Beispiel: INFO:     192.168.2.2:26753 - "POST /analyze HTTP/1.1" 200 OK
import logging


@app.post("/init_brain")
async def init_brain(request_data: InitRequest):
    """
    Empfängt Liste von {'id': seqCat, 'text': sAiText} und Gesamtanzahl.
    Berechnet die Text-Features für CLIP vor und initialisiert den Fortschrittsbalken.
    """
    global text_features, category_ids, global_pbar, files_done, max_files

    
    try:
       
       # Zugriff auf die Daten über das request_data Objekt
        ids = [c['id'] for c in request_data.categories]
        texts = [c['text'] for c in request_data.categories]

        max_files = request_data.total_items

        
        # # funktioniert nur, wenn man uvicorn-Ausschriften wie "INFO:     192.168.2.2:13760 - "POST /analyze HTTP/1.1" 200 OK" unterdrückt
        if global_pbar is not None:
            global_pbar.close() # Schließt den alten tqdm-Balken
            global_pbar = None
            files_done = 0
            logging.getLogger("uvicorn").setLevel(logging.INFO)
            logging.getLogger("uvicorn.access").setLevel(logging.INFO)

        print(f"Brain-Init mit {len(texts)} Kategorien und device={device}...")

        if global_pbar is None:
            global_pbar = tqdm(total=max_files, desc="Bild-Analyse (Server)", leave=True)
            logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
            logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)

        text_tokens = clip.tokenize(texts).to(device)
        
        with torch.no_grad():
            text_features = model.encode_text(text_tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            
        category_ids = ids
        return {"init_brain()": "success", "count": len(category_ids)}
    except Exception as e:
        return {"init_brain": "error", "message": str(e)}

@app.post("/analyze")
async def analyze(request: requests.Request):
   """ Hauptanalyse-Funktion """

   global files_done, global_pbar, max_files

   if text_features is None:
      return {"error": "Brain nicht initialisiert. Bitte zuerst /init_brain aufrufen."}

    
   # Transformation definieren
   transform = transforms.Compose([
      transforms.ToTensor(),
      transforms.Normalize(
         mean=(0.48145466, 0.4578275, 0.40821073),
         std=(0.26862954, 0.26130258, 0.27577711)
      )
   ])

   tensors = []
        
   try:
      # 1. Alle Bilder sammeln und transformieren
      data = request.get_data() 
      offset = 0
      anzBilder = 0
      while offset < len(data):
         # 1. Länge lesen (4 Bytes)
         img_len = struct.unpack_parent('I', body[offset:offset+4])[0]
         offset += 4
         # 2. Bilddaten extrahieren
         img_data = data[offset:offset+img_len]
         offset += img_len

         pil_image = Image.open(io.BytesIO(img_data))
         tensors.append(transform(pil_image))
         anzBilder += 1

      # 2. Zu einem Batch-Tensor stapeln: Shape (16, 3, 224, 224)
      batch_tensor = torch.stack(tensors).to(device)

      # 3. Batch-Inferenz (Ein einziger GPU-Aufruf!)
      # Die Batch-Inferenz ist der "Turbo-Modus" für Deep Learning. Anstatt die GPU 16-mal 
      # nacheinander mit kleinen Aufgaben zu wecken, fütterst du sie einmal mit einem großen Block. Das reduziert den Overhead massiv.
      with torch.no_grad():
         # CLIP berechnet jetzt alle 16 Bilder gleichzeitig
         image_features = model.encode_image(batch_tensor)
         image_features /= image_features.norm(dim=-1, keepdim=True)

         # Cosine Similarity für den gesamten Batch
         # (Batch_Size x Feature_Dim) @ (Feature_Dim x Classes)
         similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            
         # Top-K Ergebnisse für alle Bilder gleichzeitig
         top_values, top_indices = similarity.topk(min(5, len(category_ids)), dim=-1)


      # 4. Ergebnisse aufbereiten: zip nimmt jeweils einen Wert aus top_indices und top_values
      # Beispiel-Ergebnisse (Kategorie-ID, Konfidenz)    
      # results = [         (101, 98.5), (102, 45.0), (105, 12.3), # ... insgesamt 16 Paare       ]
      flat_results = []

      for i in range(anzBilder):
         pairs = [
            [category_ids[idx], round(float(val) * 100)] 
            for idx, val in zip(top_indices[i].tolist(), top_values[i].tolist())
         ]

         for cat_id, conf in pairs:
            flat_results.extend([cat_id, conf])
    
      # '16If' packt 16-mal ein Paar aus Int und Float hintereinander
      binary_data = struct.pack('16If', *flat_results)
    

      # Progressbar aktualisieren
      files_done += anzBilder
      global_pbar.set_postfix(file=f"{files_done}/{max_files}")
      global_pbar.n = files_done
      global_pbar.refresh() 

      return request.Response(content=binary_data, media_type="application/octet-stream")
      
   except Exception as e:
      return {"error": str(e), "n": files_done}




@app.get("/exit")
async def exit_server():
    os.kill(os.getpid(), signal.SIGINT)
    return {"status": "Shutdown initiated"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
