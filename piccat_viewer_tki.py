import tkinter as tk
from tkinter import ttk
import threading
import queue
from PIL import Image, ImageTk

from gmbasis import CBaseApp


###### class CategoryInfo: ##############################################################################
###### Container für die Kategorien     #################################################################
class CategoryInfo:
    def __init__(self, user_text, ai_text):
        self.sUserText = user_text
        self.sAiText = ai_text

    def __repr__(self):
        return f"CategoryInfo(sUserText='{self.sUserText}', sAiText={self.sAiText})"

class PicCatApp (CBaseApp):
   ###### __init__(self, root) ##############################################################################
   def __init__(self, root):
       super().__init__()
       self.bUseSunSettings = False
       self.vInit('piccat', 'piccat_viewer_tki.py', root)

      
   ###### vInit(self, sPrjName, sAppName) ##############################################################################
   def vInit(self, sPrjName, sAppName, root):
      
      super().vInit(sPrjName, sAppName)

      try:
         self.VerbindeMitMariaDb()  # Verbindung zur DB herstellen, zweite Verbindung fürs Log

         self.root = root
         self.root.title("Bildanalyse - piccat")
         self.root.geometry("1000x700")

         self.image_queue = queue.Queue()
         self.loading_active = False
         self.check_queue() # Startet die Überwachung der Queue

         self.DictShow = {} # anzuzeigende Dateien


         # # 1. Hauptmenü
         # menubar = tk.Menu(root)
         # filemenu = tk.Menu(menubar, tearoff=0)
         # filemenu.add_command(label="Öffnen")
         # filemenu.add_separator()
         # filemenu.add_command(label="Beenden", command=root.quit)
         # menubar.add_cascade(label="Datei", menu=filemenu)
         # root.config(menu=menubar)

         # 2. Vertikaler Fensterteiler (PanedWindow)
         pw = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
         pw.pack(fill=tk.BOTH, expand=True)

         # Linke Seite: Container für Scroll-Logik
         left_frame = ttk.Frame(pw)
#         pw.add(left_frame, weight=0, stretch="never")

         # 1. Canvas und Scrollbar erstellen
         canvas_left = tk.Canvas(left_frame, highlightthickness=0)
         scrollbar_left = ttk.Scrollbar(left_frame, orient="vertical", command=canvas_left.yview)

         # 2. Frame im Canvas für die Checkboxen
         scrollable_frame_left = ttk.Frame(canvas_left)

         # 3. Canvas konfigurieren
         scrollable_frame_left.bind(
            "<Configure>",
            lambda e: canvas_left.configure(scrollregion=canvas_left.bbox("all"))
         )
         canvas_left.create_window((0, 0), window=scrollable_frame_left, anchor="nw")
         canvas_left.configure(yscrollcommand=scrollbar_left.set)

         # 4. Layout
         canvas_left.pack(side="left", fill="both", expand=True)
         scrollbar_left.pack(side="right", fill="y")

         # 43 Kategorien befüllen
         self.dictKat = {}
         self.LiesKategorien()
         for seq, cat in self.dictKat.items():
            var = tk.BooleanVar()
            self.dictKat[seq] = var
            cb = ttk.Checkbutton(scrollable_frame_left, text=f"{cat.sUserText}", variable=var, command=self.on_category_change)
            cb.pack(anchor="w", padx=5, pady=2)

         #canvas.pack(side="left", fill="both", expand=True)
         #scrollbar.pack(side="right", fill="y")
         pw.add(left_frame, weight=1)


         ###################################################################################################
         # Rechte Seite: Container für Navigation + Scrollbereich
         self.right_wrapper = ttk.Frame(pw)
         pw.add(self.right_wrapper, weight=4)


         # 1. Navigationsleiste oben
         self.nav_frame = ttk.Frame(self.right_wrapper)
         self.nav_frame.pack(side="top", fill="x", padx=5, pady=5)

         self.btn_start = ttk.Button(self.nav_frame, text="|< Anfang", command=self.go_start)
         self.btn_prev = ttk.Button(self.nav_frame, text="< Vorherige", command=self.go_prev)
         self.page_label = ttk.Label(self.nav_frame, text="Seite 1")
         self.btn_next = ttk.Button(self.nav_frame, text="Nächste >", command=self.go_next)
         self.btn_end = ttk.Button(self.nav_frame, text="Ende >|", command=self.go_end)

         for btn in [self.btn_start, self.btn_prev, self.page_label, self.btn_next, self.btn_end]:
            btn.pack(side="left", padx=2)


         # 2. Scrollbarer Bereich (Canvas)
         self.canvas_container = ttk.Frame(self.right_wrapper)
         self.canvas_container.pack(fill="both", expand=True)

         self.canvas = tk.Canvas(self.canvas_container, bg="white")
         self.v_scroll = ttk.Scrollbar(self.canvas_container, orient="vertical", command=self.canvas.yview)
         self.canvas.configure(yscrollcommand=self.v_scroll.set)

         self.grid_frame = ttk.Frame(self.canvas)
         self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

         self.canvas.pack(side="left", fill="both", expand=True)
         self.v_scroll.pack(side="right", fill="y")

         self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

         # Paginierungs-Variablen
         self.current_page = 0
         self.images_per_page = 360 # 120 Zeilen à 3 Bilder
         self.total_images = 1500   # Beispielwert aus Ihrer Datenbank

         #self.load_page()


         #Fensterteiler einstellen
         self.root.update()
         wLeft = scrollable_frame_left.winfo_reqwidth()
         canvas_left.configure(width=wLeft) 
         pw.sashpos(0, wLeft+30)

      except Exception as e:
         self.Exception2Log(f'CBildAnalyse.vInit()',e)
         self.vScriptAbbruch("")


   ###### get_selected_categories(self) ##############################################################################
   def get_selected_categories(self):
      # Gibt eine Liste der Indizes aller ausgewählten Kategorien zurück
      #return [seq for seq, var in self.dictKat.items() if var.get()]

      #gibt Zeichenkette für select in zurück:
      sIn = ""
      for seq, var in self.dictKat.items():
         if var.get():
            if len(sIn) > 0:
               sIn += ","
            sIn += f"{seq}"
      return sIn



   ###### on_category_change(self) ##############################################################################
   def on_category_change(self):
      try:
         sIn = self.get_selected_categories()

         sStmt = """
                SELECT 
                    fo.seqFolder AS seqFo, 
                    fi.seqFile AS seqFi, 
                    fo.sName || '\\\\' || fi.sName AS sFile, 
                    c.iConfidence AS Confi
                FROM piccat.piccat_tab_confidence c
                JOIN piccat.piccat_tab_folder fo ON fo.seqFolder = c.seqFolder
                JOIN piccat.piccat_tab_file fi ON fi.seqFile = c.seqFile
                WHERE c.seqCategory in (?)
                ORDER BY c.iConfidence DESC
                """

         cur = self.mdb.cursor(dictionary=True)
         cur.execute( sStmt, (sIn,))
         self.DictShow = cur.fetchall()
         self.load_page()

      except Exception as e:
         self.Exception2Log(f'on_category_change()',e)
      finally:
        cur.close()

   ###### image_loader_thread(self, paths, start_offset) ##############################################################################
   def image_loader_thread(self, paths, start_offset):
        """Arbeitet im Hintergrund: Lädt und skaliert Bilder."""
        for i, path in enumerate(paths):
            if not self.loading_active: break # Abbruch falls Seite gewechselt wurde
            
            try:
                # Bild laden und auf 224x224 skalieren (Box-Fitting)
                img = Image.open(path)
                img.thumbnail((224, 224))
                tk_img = ImageTk.PhotoImage(img)
                
                # Bild zurück an den Hauptthread geben
                self.image_queue.put((start_offset + i, tk_img))
            except Exception as e:
                print(f"Fehler bei {path}: {e}")


   ###### check_queue(self) ##############################################################################
   def check_queue(self):
       """Prüft alle 100ms, ob neue Bilder aus dem Thread fertig sind."""
       try:
           while not self.image_queue.empty():
               # Hole Daten aus der Queue
               data = self.image_queue.get_nowait()
               if data:
                   idx, tk_img = data  # Hier wird idx definiert
                
                   if idx in self.tiles:
                       lbl = self.tiles[idx]
                       lbl.config(image=tk_img, text="")
                       lbl.image = tk_img  # Referenz behalten!
       except Exception as e:
           print(f"Queue-Fehler: {e}")
       finally:
           # Plane den nächsten Check
           self.root.after(100, self.check_queue)


   ###### load_page(self) ##############################################################################
   def load_page(self):
        """Bereitet die Kacheln vor und startet den Lade-Thread."""
        self.loading_active = False # Alten Ladevorgang stoppen
        
        # Grid leeren
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        if self.DictShow == None or len(self.DictShow) <= 0:
           return;


        self.tiles = {} # Speichert Referenzen auf die Labels in den Kacheln
        start_idx = self.current_page * self.images_per_page
        end_idx = min(start_idx + self.images_per_page, self.total_images)

        # Erstmal nur leere Kacheln mit "Laden..." Text erstellen
        for i in range(start_idx, end_idx):
            rel_idx = i - start_idx
            row, col = divmod(rel_idx, 3)
            
            tile = tk.Frame(self.grid_frame, width=224, height=224, relief="ridge", borderwidth=1)
            tile.grid(row=row, column=col, padx=2, pady=2)
            tile.grid_propagate(False)
            
            lbl = tk.Label(tile, text="Lade...")
            lbl.pack(expand=True, fill="both")
            self.tiles[i] = lbl # Merken, wo das Bild später rein soll

        # Hintergrund-Thread starten
        self.loading_active = True

        # Hier die echten Pfade aus der DB übergeben 
        subset = self.DictShow[start_idx : end_idx + 1]
        image_paths = [x['sFile'] for x in subset]
        threading.Thread(target=self.image_loader_thread, args=(image_paths, start_idx), daemon=True).start()

        # # UI aktualisieren
        # self.page_label.config(text=f"Bilder {start_idx+1} bis {end_idx} (Seite {self.current_page+1})")
        # self.canvas.yview_moveto(0) # Nach oben scrollen

    # Navigations-Logik
   def go_start(self):
        self.current_page = 0
        self.load_page()

   def go_prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_page()

   def go_next(self):
        if (self.current_page + 1) * self.images_per_page < self.total_images:
            self.current_page += 1
            self.load_page()

   def go_end(self):
        self.current_page = (self.total_images - 1) // self.images_per_page
        self.load_page()

   ###### def LiesKategorien(self) ##############################################################################
   def LiesKategorien(self):

      try:
         sStmt = f"""select cat.sAiText AS sAiText, cat.sUserText AS sUserText, cat.seqCat AS seqCat,  COUNT(c.seqCategory) AS Anzahl
                     FROM {self.MariaDbName}.piccat_tab_confidence c 
                     JOIN {self.MariaDbName}.piccat_tab_category cat ON cat.seqCat = c.seqCategory
                     GROUP BY c.seqCategory"""


         cur = self.mdb.cursor()
         cur.execute( sStmt)
         rec = cur.fetchone()
         if rec == None:
            self.Info2Log(f'Keine Kategorien gefunden in piccat_tab_category')
            return True   

         while rec != None:
            sAi, sUser, nSeq, nAnz = rec  # Entpackt das Tuple in Variablen
            self.dictKat[nSeq] = CategoryInfo(f"{sUser} ({nAnz})", sAi)
            rec = cur.fetchone()

         self.mdb.commit()

      except Exception as e:
         self.Exception2Log(f'LiesKategorien()',e)
      finally:
        cur.close()

###### main() ###############################################################################################
if __name__ == "__main__":
    root = tk.Tk()
    app = PicCatApp(root)
    root.mainloop()

