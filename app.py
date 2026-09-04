from flask import Flask, request, Response, redirect
import pandas as pd
import sqlite3

app = Flask(__name__)
FILE_DB = 'fantacalcio.db'

# --- 1. IMPOSTA LE TUE CREDENZIALI QUI ---
USERNAME_SEGRETO = 'admin'
PASSWORD_SEGRETA = 'nsg2026'

# ==========================================
# ⚙️ IMPOSTAZIONI ASTA (MODIFICALE QUI)
# ==========================================
BUDGET_TOTALE = 1000
SLOT_MAX = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
# Imposta qui quanto vorresti spendere idealmente per ogni ruolo.
# Il sistema calcolerà se sei in positivo o in negativo!
BUDGET_IDEALE = {'P': 70, 'D': 150, 'C': 220, 'A': 560}
# ==========================================

def check_auth(username, password):
    return username == USERNAME_SEGRETO and password == PASSWORD_SEGRETA

def richiedi_login():
    return Response('Accesso negato.', 401, {'WWW-Authenticate': 'Basic realm="Area Riservata"'})

@app.route('/')
def home():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return richiedi_login()
    
    conn = sqlite3.connect(FILE_DB)
    df = pd.read_sql_query('SELECT * FROM giocatori', conn)
    conn.close()
    
    ruolo_selezionato = request.args.get('ruolo', 'Tutti')
    ordinamento_1 = request.args.get('sort1', 'Appetibilita')
    
    COLONNA_RUOLO = 'R'
    COLONNA_TITOLARITA = 'Tit'
    
    if COLONNA_TITOLARITA not in df.columns:
        df[COLONNA_TITOLARITA] = 100
        
    df[COLONNA_TITOLARITA] = pd.to_numeric(df[COLONNA_TITOLARITA], errors='coerce').fillna(100).astype(int)
    
    df_miei = df[df['Mio'] == 'SI']
    
    miei_count = {}
    spesa_ruoli = {}
    ruoli_ordine = ['P', 'D', 'C', 'A']
    
    for r in ruoli_ordine:
        df_ruolo = df_miei[df_miei[COLONNA_RUOLO] == r]
        miei_count[r] = len(df_ruolo)
        spesa_ruoli[r] = df_ruolo['Costo'].sum()
    
    spesa_totale = sum(spesa_ruoli.values())
    budget_rimasto = BUDGET_TOTALE - spesa_totale
    slot_occupati = sum(miei_count.values())
    slot_rimasti = sum(SLOT_MAX.values()) - slot_occupati
    rilancio_max = budget_rimasto - (slot_rimasti - 1) if slot_rimasti > 0 else 0
    
    # 🧮 LOGICA DI CASCATA DEL BUDGET
    budget_ideale_dinamico = BUDGET_IDEALE.copy()
    
    for i in range(len(ruoli_ordine)):
        r = ruoli_ordine[i]
        if miei_count[r] >= SLOT_MAX[r]:
            extra = budget_ideale_dinamico[r] - spesa_ruoli[r]
            num_successivi = len(ruoli_ordine) - i - 1
            if num_successivi > 0:
                quota = int(extra / num_successivi)
                resto = extra - (quota * num_successivi)
                for j in range(num_successivi):
                    target = ruoli_ordine[i + 1 + j]
                    aggiunta = quota
                    if resto != 0:
                        aggiunta += (1 if extra > 0 else -1)
                        resto += (-1 if extra > 0 else 1)
                    budget_ideale_dinamico[target] += aggiunta
                    
    if ruolo_selezionato in ruoli_ordine:
        budget_ruolo_rimanente = budget_ideale_dinamico[ruolo_selezionato] - spesa_ruoli[ruolo_selezionato]
        colore_budget_ruolo = "text-success" if budget_ruolo_rimanente >= 0 else "text-danger"
        label_ruolo = f"Bdgt {ruolo_selezionato}"
        budget_ruolo_html = f"<p class='dash-val {colore_budget_ruolo}'>{budget_ruolo_rimanente}</p>"
    else:
        label_ruolo = "Bdgt Ruolo"
        budget_ruolo_html = "<p class='dash-val text-muted'>-</p>"

    # 📊 CONTEGGIO GIOCATORI LIBERI PER APPETIBILITÀ (Da 5 a 1)
    df_liberi = df[df['Acquistato'] != 'SI']
    if ruolo_selezionato in ruoli_ordine:
        df_liberi_ruolo = df_liberi[df_liberi[COLONNA_RUOLO] == ruolo_selezionato]
    else:
        df_liberi_ruolo = df_liberi
        
    conteggi_stelle = {}
    for stella in range(5, 0, -1):
        conteggi_stelle[stella] = len(df_liberi_ruolo[df_liberi_ruolo['Appetibilita'] == stella])

    badge_liberi_html = ""
    colori_badge_stella = {5: '#6f42c1', 4: '#dc3545', 3: '#ffc107', 2: '#198754', 1: '#0dcaf0'}
    for s in range(5, 0, -1):
        num = conteggi_stelle.get(s, 0)
        bg_c = colori_badge_stella.get(s, '#6c757d')
        txt_c = 'text-dark' if s == 3 else 'text-white'
        badge_liberi_html += f"""
        <div class="text-center px-1" style="flex: 1;">
            <span class="badge {txt_c} w-100 py-1 shadow-sm" style="background-color: {bg_c}; font-size: 11px;">
                ★{s}: <b>{num}</b>
            </span>
        </div>
        """

    df_tabella = df.copy()
    if ruolo_selezionato in ruoli_ordine:
        df_tabella = df_tabella[df_tabella[COLONNA_RUOLO] == ruolo_selezionato]
        
    if ordinamento_1 == COLONNA_TITOLARITA:
        ordinamento_2 = 'Appetibilita'
    elif ordinamento_1 == 'Qt.A':
        ordinamento_2 = 'Appetibilita'
    else:
        ordinamento_2 = 'Qt.A'
        
    df_tabella = df_tabella.sort_values(by=[ordinamento_1, ordinamento_2], ascending=[False, False])
    
    df_visibile = df_tabella.head(150) 
    righe_html = ""
    
    for _, row in df_visibile.iterrows():
        appet = int(row['Appetibilita'])
        acquistato = row['Acquistato'] == 'SI'
        mio = row['Mio'] == 'SI'
        titolarita_perc = int(row[COLONNA_TITOLARITA])
        squadra = str(row['Squadra']) if pd.notna(row['Squadra']) else ''
        
        # 🎨 Colore percentuale titolarità (>70 verde, 30-70 giallo, <30 rosso)
        if titolarita_perc > 70:
            colore_tit = "text-success fw-bold"
        elif titolarita_perc >= 30:
            colore_tit = "text-warning fw-bold" # Giallo scuro/arancio leggibile
        else:
            colore_tit = "text-danger fw-bold"
        
        bg_stella = colori_badge_stella.get(appet, '#6c757d')
        txt_stella = 'text-dark' if appet == 3 else 'text-white'
        
        if appet == 0:
            badge_html = f"<span class='badge bg-secondary' style='font-size: 13px; padding: 5px 8px;'>★ 0</span>"
        else:
            badge_html = f"<span class='badge {txt_stella}' style='background-color: {bg_stella}; font-size: 13px; padding: 5px 8px;'>★ {appet}</span>"
        
        if acquistato:
            riga_style = "opacity: 0.5; background-color: #e9ecef;"
            badge_mio = f"<span class='badge bg-success w-100 mb-1 py-1' style='font-size:11px;'>MIO a {row['Costo']}</span>" if mio else "<span class='badge bg-secondary w-100 mb-1 py-1' style='font-size:11px;'>ALTRI</span>"
            form_html = f"""
                <div style="width: 80px; float: right;">
                    {badge_mio}
                    <form action="/acquista" method="POST" class="m-0">
                        <input type="hidden" name="id_giocatore" value="{row['Id']}">
                        <input type="hidden" name="ruolo" value="{ruolo_selezionato}">
                        <input type="hidden" name="sort1" value="{ordinamento_1}">
                        <button type="submit" name="action" value="annulla" class="btn btn-outline-dark w-100" style="font-size: 11px; padding: 2px;">Annulla</button>
                    </form>
                </div>
            """
        else:
            riga_style = "background-color: #ffffff; font-weight: 500;"
            form_html = f"""
                <form action="/acquista" method="POST" class="m-0 d-flex flex-column gap-1 align-items-end" style="width: 85px; float: right;">
                    <input type="hidden" name="id_giocatore" value="{row['Id']}">
                    <input type="hidden" name="ruolo" value="{ruolo_selezionato}">
                    <input type="hidden" name="sort1" value="{ordinamento_1}">
                    
                    <button type="submit" name="action" value="altri" class="btn btn-warning fw-bold w-100 shadow-sm" style="font-size: 11px; padding: 3px;">ALTRI</button>
                    
                    <div class="input-group" style="height: 24px;">
                        <input type="number" name="costo" class="form-control text-center px-0 py-0 border-success" style="font-size: 12px; height: 100%; border-width: 2px;" placeholder="€" min="1">
                        <button type="submit" name="action" value="mio" class="btn btn-success fw-bold px-2 py-0 shadow-sm" style="font-size: 11px; height: 100%;">MIO</button>
                    </div>
                </form>
            """
            
        righe_html += f"""
        <tr style="{riga_style}" class="player-row border-bottom" data-nome="{row['Nome'].lower()}" data-acquistato="{acquistato}">
            <td class="align-middle lh-sm pt-2 pb-2">
                <span class="fw-bold text-dark" style="font-size: 15px;">{row['Nome']}</span><br>
                <small class="text-muted fw-bold" style="font-size:11px; text-transform: uppercase;">
                    {squadra} • <span class="{colore_tit}">{titolarita_perc}%</span>
                </small>
            </td>
            <td class="align-middle text-center" style="width: 50px;">
                {badge_html}
            </td>
            <td class="align-middle px-1" style="width: 95px;">
                {form_html}
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="it">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
            <title>Asta Live</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ background-color: #f0f2f5; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
                table td, table th {{ padding: 6px 4px !important; vertical-align: middle; border: none; }}
                .dashboard-box {{ background: white; border-radius: 8px; padding: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
                .dash-title {{ font-size: 9px; font-weight: bold; color: #6c757d; text-transform: uppercase; margin-bottom: 2px; }}
                .dash-val {{ font-size: 16px; font-weight: bold; margin: 0; line-height: 1.2; letter-spacing: -0.5px; }}
                input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button {{ -webkit-appearance: none; margin: 0; }}
            </style>
        </head>
        <body>
            <div class="sticky-top bg-light pb-2 shadow-sm border-bottom">
                <div class="container pt-2 px-2">
                    <div class="d-flex justify-content-between text-center mb-2 fw-bold" style="font-size: 11px;">
                        <span class="{'text-success' if miei_count['P'] == SLOT_MAX['P'] else 'text-muted'}">P: {miei_count['P']}/{SLOT_MAX['P']}</span>
                        <span class="{'text-success' if miei_count['D'] == SLOT_MAX['D'] else 'text-muted'}">D: {miei_count['D']}/{SLOT_MAX['D']}</span>
                        <span class="{'text-success' if miei_count['C'] == SLOT_MAX['C'] else 'text-muted'}">C: {miei_count['C']}/{SLOT_MAX['C']}</span>
                        <span class="{'text-success' if miei_count['A'] == SLOT_MAX['A'] else 'text-muted'}">A: {miei_count['A']}/{SLOT_MAX['A']}</span>
                    </div>
                    
                    <div class="row g-2 mb-2">
                        <div class="col-4">
                            <div class="dashboard-box"><p class="dash-title">Budget</p><p class="dash-val text-primary">{budget_rimasto}</p></div>
                        </div>
                        <div class="col-4">
                            <div class="dashboard-box"><p class="dash-title text-danger">Max Bid</p><p class="dash-val text-danger">{rilancio_max}</p></div>
                        </div>
                        <div class="col-4">
                            <div class="dashboard-box"><p class="dash-title">{label_ruolo}</p>{budget_ruolo_html}</div>
                        </div>
                    </div>
                    
                    <div class="d-flex gap-1 align-items-center">
                        <input type="text" id="searchInput" class="form-control form-control-sm" placeholder="🔍 Cerca..." onkeyup="filtraTabella()">
                        <div class="form-check form-switch m-0" style="min-width: 105px; padding-left: 2.5em;">
                            <input class="form-check-input" type="checkbox" id="hideAcquistati" onchange="filtraTabella()" style="margin-left: -2.5em;">
                            <label class="form-check-label fw-bold" style="font-size:10px; padding-top:2px;">Nascondi<br>Presi</label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="container py-2 px-2">
                <div class="d-flex justify-content-center gap-1 mb-2">
                    <a href="/?ruolo=P&sort1={ordinamento_1}" class="btn {'btn-warning' if ruolo_selezionato == 'P' else 'btn-outline-warning'} fw-bold flex-fill btn-sm">P</a>
                    <a href="/?ruolo=D&sort1={ordinamento_1}" class="btn {'btn-success' if ruolo_selezionato == 'D' else 'btn-outline-success'} fw-bold flex-fill btn-sm">D</a>
                    <a href="/?ruolo=C&sort1={ordinamento_1}" class="btn {'btn-primary' if ruolo_selezionato == 'C' else 'btn-outline-primary'} fw-bold flex-fill btn-sm">C</a>
                    <a href="/?ruolo=A&sort1={ordinamento_1}" class="btn {'btn-danger' if ruolo_selezionato == 'A' else 'btn-outline-danger'} fw-bold flex-fill btn-sm">A</a>
                    <a href="/?ruolo=Tutti&sort1={ordinamento_1}" class="btn {'btn-dark' if ruolo_selezionato == 'Tutti' else 'btn-outline-dark'} fw-bold flex-fill btn-sm">Tutti</a>
                </div>
                
                <div class="card shadow-sm border-0 mb-2 bg-white">
                    <div class="card-body p-2">
                        <div class="text-muted fw-bold text-center mb-1" style="font-size: 10px; text-transform: uppercase;">
                            Disponibili ({ruolo_selezionato})
                        </div>
                        <div class="d-flex justify-content-between">
                            {badge_liberi_html}
                        </div>
                    </div>
                </div>
                
                <div class="mb-2">
                    <form action="/" method="GET" class="m-0">
                        <input type="hidden" name="ruolo" value="{ruolo_selezionato}">
                        <select name="sort1" class="form-select form-select-sm fw-bold shadow-sm text-center" style="font-size: 13px;" onchange="this.form.submit()">
                            <option value="Appetibilita" {'selected' if ordinamento_1 == 'Appetibilita' else ''}>Ordina per: ★ APPETIBILITÀ</option>
                            <option value="{COLONNA_TITOLARITA}" {'selected' if ordinamento_1 == COLONNA_TITOLARITA else ''}>Ordina per: 🛡️ TITOLARITÀ (%)</option>
                            <option value="Qt.A" {'selected' if ordinamento_1 == 'Qt.A' else ''}>Ordina per: 💰 QUOTAZIONE</option>
                            <option value="FVM" {'selected' if ordinamento_1 == 'FVM' else ''}>Ordina per: 📊 VALORE (FVM)</option>
                        </select>
                    </form>
                </div>
                
                <div class="card shadow-sm border-0 mb-5">
                    <div class="card-body p-0">
                        <table class="table m-0" style="table-layout: fixed; width: 100%;">
                            <tbody>
                                {righe_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <script>
                function filtraTabella() {{
                    let input = document.getElementById("searchInput").value.toLowerCase();
                    let nascondi = document.getElementById("hideAcquistati").checked;
                    let righe = document.querySelectorAll(".player-row");
                    
                    righe.forEach(riga => {{
                        let nome = riga.getAttribute("data-nome");
                        let acquistato = riga.getAttribute("data-acquistato") === "True";
                        
                        let mostraPerRicerca = nome.includes(input);
                        let mostraPerFiltro = nascondi ? !acquistato : true;
                        
                        if (mostraPerRicerca && mostraPerFiltro) {{
                            riga.style.display = "";
                        }} else {{
                            riga.style.display = "none";
                        }}
                    }});
                }}
            </script>
        </body>
    </html>
    """
    return html

@app.route('/acquista', methods=['POST'])
def acquista():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return richiedi_login()

    id_giocatore = int(request.form['id_giocatore'])
    ruolo_attuale = request.form['ruolo']
    sort_attuale = request.form['sort1']
    azione = request.form['action'] 
    
    conn = sqlite3.connect(FILE_DB)
    cursor = conn.cursor()
    
    if azione == 'altri':
        cursor.execute("UPDATE giocatori SET Acquistato='SI', Mio='', Costo=0 WHERE Id=?", (id_giocatore,))
    elif azione == 'mio':
        costo_str = request.form.get('costo', '0')
        costo = int(costo_str) if costo_str.isdigit() else 1
        cursor.execute("UPDATE giocatori SET Acquistato='SI', Mio='SI', Costo=? WHERE Id=?", (costo, id_giocatore))
    elif azione == 'annulla':
        cursor.execute("UPDATE giocatori SET Acquistato='', Mio='', Costo=0 WHERE Id=?", (id_giocatore,))
        
    conn.commit()
    conn.close()
    
    return redirect(f'/?ruolo={ruolo_attuale}&sort1={sort_attuale}')

if __name__ == '__main__':
    app.run(port=2828)