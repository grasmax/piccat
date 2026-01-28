# Script für das Erstellen einer Datenbank für das Projekt https://github.com/grasmax/piccat
# für die Analyse von Foto-Dateien an Hand von Kategorien mit torch und clip

CREATE SEQUENCE piccat_seq_run START WITH 1 INCREMENT BY 1;
# SELECT NEXT VALUE FOR piccat_seq_run;
CREATE SEQUENCE piccat_seq_category START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE piccat_seq_folder START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE piccat_seq_file START WITH 1 INCREMENT BY 1;

ALTER SEQUENCE piccat_seq_run RESTART WITH 1;
ALTER SEQUENCE piccat_seq_file RESTART WITH 1;
ALTER SEQUENCE piccat_seq_folder RESTART WITH 1;
ALTER SEQUENCE piccat_seq_category RESTART WITH 1;

DROP TABLE piccat_tab_category;
CREATE TABLE `piccat_tab_category` (
	`seqCat` INT(11) NULL DEFAULT NULL COMMENT 'von piccat_seq_categroy generierter Wert',
	`sAiText` VARCHAR(100) NULL DEFAULT NULL COMMENT 'englische Wortgruppe oder Satz, der den Bildinhalt beschreibt' COLLATE 'utf8mb4_general_ci',
	`sUserText` VARCHAR(100) NULL DEFAULT NULL COMMENT 'Text, der an der Oberfläche zur Auswahl angeboten wird' COLLATE 'utf8mb4_general_ci'
)
COMMENT='Speichert alle Kategorien, gegen die die Bildinhalte vergleichen werden'
COLLATE='utf8mb4_general_ci'
ENGINE=INNODB
;
ALTER TABLE piccat_tab_category ADD PRIMARY KEY (seqCat);

DROP TABLE piccat_tab_confidence;
CREATE TABLE `piccat_tab_confidence` (
	`seqRun` INT(11) NOT NULL COMMENT 'Verweis auf den Lauf',
	`seqFile` INT(11) NOT NULL COMMENT 'Verweis auf eine Datei',
	`seqCategory` INT(11) NOT NULL COMMENT 'Verweis auf eine Kategorie',
	`seqFolder` INT(11) NOT NULL COMMENT 'Verweis auf ein Verzeichnis, wird beim Löschen benutzt',	
	`iConfidence` INT(11) NULL DEFAULT NULL COMMENT 'Wahrscheinlichkeit in Prozent, dass das Bild dieser Kategorie angehört'
)
COMMENT='Speichert alle Analyseergebnisse'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
ALTER TABLE piccat_tab_confidence ADD PRIMARY KEY (seqFile,seqCategory);
ALTER TABLE piccat_tab_confidence ADD INDEX (seqCategory);
ALTER TABLE piccat_tab_confidence ADD INDEX (seqFolder);
ALTER TABLE piccat_tab_confidence ADD INDEX (seqRun);


DROP TABLE piccat_tab_file;
CREATE TABLE `piccat_tab_file` (
	`seqFile` INT(11) NOT NULL COMMENT 'von piccat_seq_file gelesener Wert',
	`sName` VARCHAR(100) NOT NULL COLLATE 'utf8mb4_general_ci',
	`seqFolder` INT(11) NOT NULL, 
   `seqRun` INT(11) NULL DEFAULT NULL,
	`dtExif` DATETIME NULL DEFAULT NULL COMMENT 'wenn gefunden, dann Aufnahmedatum' COLLATE 'utf8mb4_general_ci'
)
COMMENT='Speichert alle gefundenen Dateien'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
ALTER TABLE piccat_tab_file ADD PRIMARY KEY (seqFile);
ALTER TABLE piccat_tab_file ADD INDEX (seqFolder);
ALTER TABLE piccat_tab_file ADD INDEX (seqRun);


DROP TABLE piccat_tab_folder;
CREATE TABLE `piccat_tab_folder` (
	`seqFolder` INT(11) NULL DEFAULT NULL COMMENT 'von piccat_seq_folder gelesener Wert',
	`sName` VARCHAR(500) NULL DEFAULT NULL COLLATE 'utf8mb4_general_ci',
	`seqRun` INT(11) NULL DEFAULT NULL COMMENT 'Verweis auf den Lauf' COLLATE 'utf8mb4_general_ci'
)
COMMENT='Speichert alle Verzeichnisse, in denen Bilddateien gefunden wurden'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
ALTER TABLE piccat_tab_folder ADD PRIMARY KEY (seqFolder);
ALTER TABLE piccat_tab_folder ADD INDEX (seqRun);

DROP TABLE piccat_tab_run;
CREATE TABLE `piccat_tab_run` (
 	`seqRun` INT(11) NULL DEFAULT NULL COMMENT 'von piccat_seq_run generierter Wert',
 	`tBeg` DATETIME NULL DEFAULT NULL,
 	`tEnd` DATETIME NULL DEFAULT NULL
 )
 COMMENT='Speichert alle Analyseläufe'
 COLLATE='utf8mb4_general_ci'
 ENGINE=InnoDB
;
ALTER TABLE piccat_tab_run ADD PRIMARY KEY (seqRun);



delete  FROM piccat_tab_run;
delete FROM piccat_tab_folder;
delete  FROM piccat_tab_file;


delete  FROM piccat_tab_category;
delete  FROM piccat_tab_confidence;
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category, "Gesicht", "facial expression");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Mensch", "Individual people or groups of people");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Architekturfragment", "a fragment of architecture");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Gebäude", "A fragment of a building structure");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Straßenpflaster", "Paved paths or streets");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Strand", "Beach at the ocean");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Himmel", "Sky with or without clouds");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Schiffe", "Sailing ships, sailboats and steamships");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Altar", "altar");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Treppe", "stairs");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Blüte", "blossom");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Blumenstrauß", "bouquet of flowers");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Landschaft", "landscape photography");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Wasser", "water or lake");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Dach", "roof");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Fenster", "window");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Ikebana", "ikebana flower arrangement");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Pflanze an Mauer", "plant growing on a wall");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Tiere", "living animal but not a cat and not a dog");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Schmetterlinge", "butterfly");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Katzen", "cat");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Hunde", "dog");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Tische und Stühle", "tables and chairs");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Dekoration", "decoration");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Flaschen und Gläser", "bottles and glasses");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Speisen und Getränke", "food and drinks");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Stillleben", "still life photography");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Wegweiser", "signpost");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Weihnachtsfest", "christmas celebration");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Inneneinrichtung", "Interior decoration");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Kirche", "a photo of a church building, cathedral or chapel");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Landkarten und Wetterkarten", "Maps and weather maps");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Burg/Schloss", "a medieval castle or a royal palace architecture");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Dokument", "a screenshot, scan, or photo of a document");

INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Skulptur", "A sculpture or sculpture");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Straße", "a street in a city");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Menschen vor Kamera", "People looking into the camera");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Pflanzen im Garten", "Plants in the garden");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Modelle von Schiffen", "Models of ships");

INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Menschen auf Weg", "People on a path in the forest or park");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Menschen auf Straße", "People on a city street");
INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Frau, blond", "Woman with blonde hair");

INSERT INTO piccat_tab_category  (seqCat, sUserText, sAiText) VALUES ( NEXT VALUE FOR piccat_seq_category,   "Sonstiges", "a photo of something else");



DROP table piccat_tab_log;
CREATE TABLE `piccat_tab_log` (
	`tLog` DATETIME(6) NULL DEFAULT NULL COMMENT 'Log-Zeitpunkt',
	`eTyp` VARCHAR(20) NULL DEFAULT NULL COMMENT 'Info oder Fehler' COLLATE 'utf8mb4_general_ci',
	`sText` VARCHAR(250) NULL DEFAULT NULL COMMENT 'Fehler oder Infotext' COLLATE 'utf8mb4_general_ci'
)
COMMENT='Tabelle speichert alle Info und Fehler beim Holen und Speichern der Solarprognose'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
ALTER TABLE `piccat_tab_log` MODIFY `tLog` DATETIME(6) NOT NULL;


# Verzeichnisse, Dateien und Konfidenzen lesen
#SELECT fold.sName, f.sName, f.seqFile, f.seqRun, count(c.seqFile)
#FROM piccat_tab_file f
#INNER JOIN piccat_tab_folder fold on fold.seqFolder = f.seqFolder
#LEFT join piccat_tab_confidence c ON  c.seqFile = f.seqFile 
#WHERE f.seqFolder = 4 GROUP BY f.seqFile;

SELECT * FROM piccat_tab_run;
SELECT * FROM piccat_tab_category;
SELECT * FROM piccat_tab_folder;
SELECT * FROM piccat_tab_file;
SELECT * FROM piccat_tab_confidence;





