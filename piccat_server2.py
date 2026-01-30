#gemini 29.1.26

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
import signal

print("Lade torch") 
import torch

print("Lade clip") 
import clip

print("Lade weitere Module") 
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form
from typing import List, Dict
import uvicorn

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


# Modell beim Import/Start einmalig laden
print(f"--- Lade CLIP Modell auf {device} ---")
model, preprocess = clip.load("ViT-B/32", device=device)

@app.post("/init_brain")
async def init_brain(request_data: InitRequest):
    """
    Empfängt Liste von {'id': seqCat, 'text': sAiText} und Gesamtanzahl.
    Berechnet die Text-Features für CLIP vor und initialisiert den Fortschrittsbalken.
    """
    global text_features, category_ids, global_pbar

    
    try:
 
        
       # Zugriff auf die Daten über das request_data Objekt
        ids = [c['id'] for c in request_data.categories]
        texts = [c['text'] for c in request_data.categories]
        
        # Zugriff auf den Integer-Wert:
        max_files = request_data.total_items

        # den tqdm Balken initialisieren:
        if global_pbar is not None:
            global_pbar.close() # Schließt den alten tqdm-Balken
            global_pbar = None
        if global_pbar is None:
            global_pbar = tqdm(total=max_files, desc="Bild-Analyse (Server)", leave=True)


        print(f"Tokenisiere {len(texts)} Kategorien...")
        text_tokens = clip.tokenize(texts).to(device)
        
        with torch.no_grad():
            text_features = model.encode_text(text_tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            
        category_ids = ids
        return {"status": "success", "count": len(category_ids)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/analyze")
async def analyze(
    seqFile: int = Form(...), 
    image: UploadFile = File(...)  # 'image' muss dem Key im Client entsprechen
):
    """ Hauptanalyse-Funktion """
    if text_features is None:
        return {"error": "Brain nicht initialisiert. Bitte zuerst /init_brain aufrufen."}

    try:
        global_pbar.set_postfix(file=seqFile)

        image_bytes = await image.read() 

        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Normalisierung durch CLIP-Preprocess
        image_input = preprocess(pil_image).unsqueeze(0).to(device)

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            image_features /= image_features.norm(dim=-1, keepdim=True)

            # Cosine Similarity
            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            values, indices = similarity.topk(min(5, len(category_ids)))

        # IDs aus der initialisierten Liste mappen
        res_ids = [category_ids[idx] for idx in indices[0].tolist()]
        res_conf = [int(val * 100) for val in values[0].tolist()]

        global_pbar.update(1)
        return {
            "s": seqFile,
            "c": res_ids,
            "p": res_conf
        }
    except Exception as e:
        return {"error": str(e), "s": seqFile}

@app.get("/exit")
async def exit_server():
    os.kill(os.getpid(), signal.SIGINT)
    return {"status": "Shutdown initiated"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
