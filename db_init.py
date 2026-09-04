import pandas as pd
import sqlite3

FILE_EXCEL = 'Quotazioni_Fantacalcio_Stagione_2026_27.xlsx'
FILE_DB = 'fantacalcio.db'

print("Leggo il file Excel...")
df = pd.read_excel(FILE_EXCEL, header=1)

# Prepara le colonne se non esistono
for col in ['Appetibilita', 'Costo']:
    if col not in df.columns: df[col] = 0
for col in ['Acquistato', 'Mio']:
    if col not in df.columns: df[col] = ''

# Gestione della colonna Titolaria 'Tit' (se presente, converte da decimale a percentuale intera)
if 'Tit' in df.columns:
    df['Tit'] = pd.to_numeric(df['Tit'], errors='coerce').fillna(1.0) * 100
    df['Tit'] = df['Tit'].round().astype(int)
else:
    df['Tit'] = 100 # Default se per qualche motivo non la trova

# Pulisce gli altri dati
df['Appetibilita'] = df['Appetibilita'].fillna(0).astype(int)
df['Costo'] = pd.to_numeric(df['Costo'], errors='coerce').fillna(0).astype(int)
df['Acquistato'] = df['Acquistato'].fillna('').astype(str).str.strip().str.upper()
df['Mio'] = df['Mio'].fillna('').astype(str).str.strip().str.upper()

print("Creo il database SQLite aggiornato...")
conn = sqlite3.connect(FILE_DB)
df.to_sql('giocatori', conn, if_exists='replace', index=False)
conn.close()

print("Database ricreato con successo!")