from flask import Flask, request, Response, redirect
import pandas as pd
import sqlite3
import json

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
    
    tab = request.args.get('tab', 'asta')
    
    conn = sqlite3.connect(FILE_DB)
    df_check = pd.read_sql_query('SELECT COUNT(*) as cnt FROM giocatori WHERE R="P" AND Mio="SI"', conn)
    conn.close()
    num_portieri_miei = df_check.iloc[0]['cnt']
    
    if tab == 'portieri' and num_portieri_miei < 3:
        return pagina_portieri()
    elif tab == 'rosa':
        return pagina_rosa()
    else:
        return pagina_asta()

def pagina_asta():
    conn = sqlite3.connect(FILE_DB)
    df = pd.read_sql_query('SELECT * FROM giocatori', conn)
    conn.close()
    
    ruolo_selezionato = request.args.get('ruolo', 'P')
    ordinamento_1 = request.args.get('sort1', 'Appetibilita')
    solo_preferiti = request.args.get('preferiti', '0') == '1'

    COLONNA_RUOLO = 'R'
    COLONNA_TITOLARITA = 'Tit'

    if COLONNA_TITOLARITA not in df.columns:
        df[COLONNA_TITOLARITA] = 100
    df[COLONNA_TITOLARITA] = pd.to_numeric(df[COLONNA_TITOLARITA], errors='coerce').fillna(100).astype(int)
    
    if 'Preferito' not in df.columns:
        df['Preferito'] = ''

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

    # Calcolo slot rimanenti per il ruolo selezionato
    slot_ruolo_rimasti = SLOT_MAX[ruolo_selezionato] - miei_count[ruolo_selezionato]
    budget_ruolo_corrente = budget_ideale_dinamico[ruolo_selezionato] - spesa_ruoli[ruolo_selezionato]

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
        
    if solo_preferiti:
        df_tabella = df_tabella[df_tabella['Preferito'] == 'SI']
        
    if ordinamento_1 == COLONNA_TITOLARITA:
        ordinamento_2 = 'Appetibilita'
    elif ordinamento_1 == 'Qt.A':
        ordinamento_2 = 'Appetibilita'
    else:
        ordinamento_2 = 'Qt.A'
        
    df_tabella = df_tabella.sort_values(by=[ordinamento_1, ordinamento_2], ascending=[False, False])
    
    df_visibile = df_tabella.head(150) 
    righe_html = ""
    
    # Funzione di calcolo prezzo massimo consigliato per giocatore
    def calcola_prezzo_max(row, bdgt_rim, slot_rim):
        if slot_rim <= 0:
            return 1
        base_slot = max(1, bdgt_rim / slot_rim)
        appet = int(row['Appetibilita'])
        pesi_appet = {0: 0.2, 1: 0.3, 2: 0.6, 3: 1.0, 4: 1.5, 5: 2.3}
        fattore_appet = pesi_appet.get(appet, 1.0)
        
        # Titolarità incide in piccolissima parte (±10% max)
        tit = int(row[COLONNA_TITOLARITA])
        fattore_tit = 1.0 + ((tit - 50) / 500.0)
        
        prezzo_consigliato = int(base_slot * fattore_appet * fattore_tit)
        return max(1, min(prezzo_consigliato, budget_rimasto, rilancio_max))

    for _, row in df_visibile.iterrows():
        appet = int(row['Appetibilita'])
        acquistato = row['Acquistato'] == 'SI'
        mio = row['Mio'] == 'SI'
        preferito = row['Preferito'] == 'SI'
        titolarita_perc = int(row[COLONNA_TITOLARITA])
        squadra = str(row['Squadra']) if pd.notna(row['Squadra']) else ''
        
        # Calcolo prezzo massimo specifico per questo giocatore
        prezzo_max_consigliato = calcola_prezzo_max(row, budget_ruolo_corrente, slot_ruolo_rimasti)
        
        if titolarita_perc > 70:
            colore_tit = "text-success fw-bold"
        elif titolarita_perc >= 30:
            colore_tit = "text-warning fw-bold"
        else:
            colore_tit = "text-danger fw-bold"
        
        bg_stella = colori_badge_stella.get(appet, '#6c757d')
        txt_stella = 'text-dark' if appet == 3 else 'text-white'
        
        if appet == 0:
            badge_html = f"<span class='badge bg-secondary' style='font-size: 13px; padding: 5px 8px;'>★ 0</span>"
        else:
            badge_html = f"<span class='badge {txt_stella}' style='background-color: {bg_stella}; font-size: 13px; padding: 5px 8px;'>★ {appet}</span>"
        
        icona_preferito = "❤️" if preferito else "🤍"
        form_preferito = f"""
        <form action="/preferito" method="POST" class="d-inline m-0 p-0">
            <input type="hidden" name="id_giocatore" value="{row['Id']}">
            <input type="hidden" name="ruolo" value="{ruolo_selezionato}">
            <input type="hidden" name="sort1" value="{ordinamento_1}">
            <input type="hidden" name="preferiti" value="{1 if solo_preferiti else 0}">
            <button type="submit" class="btn btn-sm p-0 border-0" style="font-size: 14px; line-height: 1;" title="Wishlist">{icona_preferito}</button>
        </form>
        """

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
                        <input type="hidden" name="tab" value="asta">
                        <input type="hidden" name="preferiti" value="{1 if solo_preferiti else 0}">
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
                    <input type="hidden" name="tab" value="asta">
                    <input type="hidden" name="preferiti" value="{1 if solo_preferiti else 0}">
                    
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
                {form_preferito} <span class="fw-bold text-dark" style="font-size: 15px;">{row['Nome']}</span><br>
                <small class="text-muted fw-bold" style="font-size:11px; text-transform: uppercase;">
                    {squadra} • <span class="{colore_tit}">{titolarita_perc}%</span> • <span class="text-primary fw-bold">Max: {prezzo_max_consigliato}€</span>
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

    attivo_pref_btn = "btn-danger" if solo_preferiti else "btn-outline-danger"
    url_pref = "/?preferiti=0" if solo_preferiti else "/?preferiti=1"

    nav_portieri_html = ""
    if miei_count['P'] < 3:
        nav_portieri_html = """
        <li class="nav-item">
            <a class="nav-link text-white fw-bold py-1" href="/?tab=portieri">🧤 Portieri</a>
        </li>
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
            <!-- NAVIGATION TABS -->
            <ul class="nav nav-pills nav-fill bg-dark py-2 px-1 sticky-top shadow">
                <li class="nav-item">
                    <a class="nav-link active fw-bold py-1" href="/?tab=asta">⚡ Asta Live</a>
                </li>
                {nav_portieri_html}
                <li class="nav-item">
                    <a class="nav-link text-white fw-bold py-1" href="/?tab=rosa">📋 La Mia Rosa</a>
                </li>
            </ul>

            <div class="sticky-top bg-light pb-2 shadow-sm border-bottom" style="top: 45px;">
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
                        <a href="{url_pref}&ruolo={ruolo_selezionato}&sort1={ordinamento_1}&tab=asta" class="btn {attivo_pref_btn} btn-sm fw-bold px-2 py-1 shadow-sm" style="font-size: 11px; white-space: nowrap;">❤️ Wishlist</a>
                        <div class="form-check form-switch m-0" style="min-width: 95px; padding-left: 2.2em;">
                            <input class="form-check-input" type="checkbox" id="hideAcquistati" onchange="filtraTabella()" style="margin-left: -2.2em;">
                            <label class="form-check-label fw-bold" style="font-size:9px; padding-top:2px;">Nascondi<br>Presi</label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="container py-2 px-2">
                <div class="d-flex justify-content-center gap-1 mb-2">
                    <a href="/?ruolo=P&sort1={ordinamento_1}&preferiti={1 if solo_preferiti else 0}&tab=asta" class="btn {'btn-warning' if ruolo_selezionato == 'P' else 'btn-outline-warning'} fw-bold flex-fill btn-sm">P</a>
                    <a href="/?ruolo=D&sort1={ordinamento_1}&preferiti={1 if solo_preferiti else 0}&tab=asta" class="btn {'btn-success' if ruolo_selezionato == 'D' else 'btn-outline-success'} fw-bold flex-fill btn-sm">D</a>
                    <a href="/?ruolo=C&sort1={ordinamento_1}&preferiti={1 if solo_preferiti else 0}&tab=asta" class="btn {'btn-primary' if ruolo_selezionato == 'C' else 'btn-outline-primary'} fw-bold flex-fill btn-sm">C</a>
                    <a href="/?ruolo=A&sort1={ordinamento_1}&preferiti={1 if solo_preferiti else 0}&tab=asta" class="btn {'btn-danger' if ruolo_selezionato == 'A' else 'btn-outline-danger'} fw-bold flex-fill btn-sm">A</a>
                </div>
                
                <div class="card shadow-sm border-0 mb-2 bg-white">
                    <div class="card-body p-2">
                        <div class="text-muted fw-bold text-center mb-1" style="font-size: 10px; text-transform: uppercase;">
                            Disponibili ({ruolo_selezionato}) {'- [WISHWATCH ACCESO]' if solo_preferiti else ''}
                        </div>
                        <div class="d-flex justify-content-between">
                            {badge_liberi_html}
                        </div>
                    </div>
                </div>
                
                <div class="mb-2">
                    <form action="/" method="GET" class="m-0">
                        <input type="hidden" name="ruolo" value="{ruolo_selezionato}">
                        <input type="hidden" name="tab" value="asta">
                        <input type="hidden" name="preferiti" value="{1 if solo_preferiti else 0}">
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

def pagina_rosa():
    conn = sqlite3.connect(FILE_DB)
    df = pd.read_sql_query('SELECT * FROM giocatori WHERE Mio="SI"', conn)
    conn.close()
    
    colore_ruolo_badge = {'P': 'bg-warning text-dark', 'D': 'bg-success', 'C': 'bg-primary', 'A': 'bg-danger'}
    righe_rosa = ""
    spesa_totale = df['Costo'].sum() if not df.empty else 0
    
    if df.empty:
        righe_rosa = "<tr><td colspan='4' class='text-center text-muted py-4'>Non hai ancora acquistato nessun giocatore.</td></tr>"
    else:
        for _, row in df.iterrows():
            r = row['R']
            badge_r = colore_ruolo_badge.get(r, 'bg-secondary')
            righe_rosa += f"""
            <tr class="border-bottom">
                <td class="align-middle text-center" style="width: 45px;"><span class="badge {badge_r} fw-bold">{r}</span></td>
                <td class="align-middle">
                    <span class="fw-bold text-dark">{row['Nome']}</span><br>
                    <small class="text-muted" style="font-size: 11px;">{row['Squadra']}</small>
                </td>
                <td class="align-middle text-center fw-bold text-success" style="width: 60px;">{row['Costo']} €</td>
                <td class="align-middle text-center" style="width: 50px;">
                    <form action="/acquista" method="POST" class="m-0">
                        <input type="hidden" name="id_giocatore" value="{row['Id']}">
                        <input type="hidden" name="ruolo" value="P">
                        <input type="hidden" name="sort1" value="Appetibilita">
                        <input type="hidden" name="tab" value="rosa">
                        <button type="submit" name="action" value="annulla" class="btn btn-outline-danger btn-sm px-1 py-0" style="font-size: 10px;">X</button>
                    </form>
                </td>
            </tr>
            """

    conn = sqlite3.connect(FILE_DB)
    df_check = pd.read_sql_query('SELECT COUNT(*) as cnt FROM giocatori WHERE R="P" AND Mio="SI"', conn)
    conn.close()
    num_portieri_miei = df_check.iloc[0]['cnt']

    nav_portieri_html = ""
    if num_portieri_miei < 3:
        nav_portieri_html = """
        <li class="nav-item">
            <a class="nav-link text-white fw-bold py-1" href="/?tab=portieri">🧤 Portieri</a>
        </li>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="it">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
            <title>La Mia Rosa</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ background-color: #f0f2f5; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
                table td, table th {{ padding: 8px 4px !important; vertical-align: middle; }}
            </style>
        </head>
        <body>
            <ul class="nav nav-pills nav-fill bg-dark py-2 px-1 sticky-top shadow">
                <li class="nav-item">
                    <a class="nav-link text-white fw-bold py-1" href="/?tab=asta">⚡ Asta Live</a>
                </li>
                {nav_portieri_html}
                <li class="nav-item">
                    <a class="nav-link active fw-bold py-1" href="/?tab=rosa">📋 La Mia Rosa</a>
                </li>
            </ul>

            <div class="container py-3">
                <div class="card shadow-sm border-0 mb-3 bg-white">
                    <div class="card-body p-3 text-center">
                        <h6 class="text-muted fw-bold mb-1" style="font-size: 11px; text-transform: uppercase;">Spesa Totale Rosa</h6>
                        <h3 class="fw-bold text-primary mb-0">{spesa_totale} <span style="font-size: 16px;">/ {BUDGET_TOTALE} €</span></h3>
                    </div>
                </div>

                <div class="card shadow-sm border-0 mb-3 bg-white">
                    <div class="card-body p-2 text-center">
                        <form action="/reset_asta" method="POST" id="formReset">
                            <button type="button" onclick="confermaReset()" class="btn btn-outline-danger btn-sm fw-bold w-100 py-2">🗑️ Reset Totale Asta (Azzera Tutto)</button>
                        </form>
                    </div>
                </div>

                <div class="card shadow-sm border-0 mb-5">
                    <div class="card-body p-0">
                        <table class="table m-0">
                            <tbody>
                                {righe_rosa}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <script>
                function confermaReset() {{
                    let conferma = confirm("⚠️ ATTENZIONE: Vuoi davvero azzerare TUTTI gli acquisti dell'asta (miei e di altri)? L'operazione non è reversibile!");
                    if (conferma) {{
                        document.getElementById('formReset').submit();
                    }}
                }}
            </script>
        </body>
    </html>
    """
    return html

def pagina_portieri():
    conn = sqlite3.connect(FILE_DB)
    df = pd.read_sql_query('SELECT * FROM giocatori WHERE R="P"', conn)
    conn.close()
    
    df['Mio'] = df['Mio'].fillna('').astype(str).str.strip().str.upper()
    miei_portieri = df[df['Mio'] == 'SI']
    
    squadre_serie_a = [
        'ATA', 'BOL', 'CAG', 'COM', 'FIO', 'FRO', 'GEN', 'INT', 'JUV', 'LAZ',
        'LEC', 'MIL', 'MON', 'NAP', 'PAR', 'ROM', 'SAS', 'TOR', 'UDI', 'VEN',
    ]
    
    def ottieni_punteggio_griglia(sq1, sq2):
        with open('griglia_portieri.json', 'r') as f:
            accoppiamenti = json.load(f)
        return accoppiamenti[squadre_serie_a.index(sq1)][squadre_serie_a.index(sq2)]

    consigli_html = ""
    
    if miei_portieri.empty:
        consigli_html = """
        <div class="alert alert-warning text-center fw-bold py-4 shadow-sm" role="alert">
            ⚠️ Non hai ancora acquistato nessun portiere!<br>
            <small class="text-muted fw-normal">Segna almeno un portiere come <b>"MIO"</b> nella sezione <b>Asta Live</b> per vedere qui i migliori abbinamenti in automatico.</small>
        </div>
        """
    else:
        for _, mio_p in miei_portieri.iterrows():
            squadra_scelta = str(mio_p['Squadra']).strip()
            consigli_html += f"""
            <div class="card shadow-sm border-0 mb-3 bg-white border-start border-success border-4">
                <div class="card-body p-3">
                    <h5 class="fw-bold text-success mb-1">🛡️ Il tuo portiere: {mio_p['Nome']} ({squadra_scelta})</h5>
                    <p class="text-muted small mb-2">I migliori partner basati sulla tua griglia:</p>
            """
            
            risultati = []
            for sq in squadre_serie_a:
                if sq.lower() == squadra_scelta.lower(): 
                    continue
                
                portieri_sq = df[df['Squadra'].str.strip().str.lower() == sq.lower()]
                if portieri_sq.empty: 
                    continue
                
                p_tit = portieri_sq.sort_values(by='Qt.A', ascending=False).iloc[0]
                punteggio = ottieni_punteggio_griglia(squadra_scelta, sq)
                stato_acquisto = str(p_tit['Acquistato']).strip().upper() == 'SI'
                
                risultati.append({
                    'squadra': sq,
                    'nome': p_tit['Nome'],
                    'qt': p_tit['Qt.A'],
                    'punteggio': punteggio,
                    'preso': stato_acquisto
                })
                
            risultati = sorted(risultati, key=lambda x: x['punteggio'], reverse=True)
            
            for res in risultati[:6]:
                p = res['punteggio']
                if p >= 90:
                    colore_badge_griglia = "background-color: #198754; color: white;"
                elif p >= 85:
                    colore_badge_griglia = "background-color: #d1e7dd; color: #0f5132;"
                else:
                    colore_badge_griglia = "background-color: #ffc107; color: #000;"
                
                badge_stato = "<span class='badge bg-secondary'>Preso (Altri)</span>" if res['preso'] else "<span class='badge bg-success'>LIBERO! 🟢</span>"
                bg_riga = "background-color: #f8f9fa; opacity: 0.6;" if res['preso'] else "background-color: #fff;"
                
                consigli_html += f"""
                <div class="card mb-2 shadow-sm border-0" style="{bg_riga}">
                    <div class="card-body p-2 d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-0 fw-bold">{res['nome']} <span class="text-muted">({res['squadra']})</span></h6>
                            <small class="text-muted">Quotazione: <b>{res['qt']}</b></small>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge fw-bold px-2 py-1 shadow-sm" style="{colore_badge_griglia} font-size: 13px;">{p}</span>
                            {badge_stato}
                        </div>
                    </div>
                </div>
                """
            consigli_html += "</div></div>"

    html = f"""
    <!DOCTYPE html>
    <html lang="it">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
            <title>Tabella Portieri</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ background-color: #f0f2f5; font-size: 14px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            </style>
        </head>
        <body>
            <ul class="nav nav-pills nav-fill bg-dark py-2 px-1 sticky-top shadow">
                <li class="nav-item">
                    <a class="nav-link text-white fw-bold py-1" href="/?tab=asta">⚡ Asta Live</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link active fw-bold py-1" href="/?tab=portieri">🧤 Portieri</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link text-white fw-bold py-1" href="/?tab=rosa">📋 La Mia Rosa</a>
                </li>
            </ul>

            <div class="container py-3">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 class="fw-bold text-primary m-0">Abbinamento Portieri 🛡️</h5>
                </div>
                <div>
                    {consigli_html}
                </div>
            </div>
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
    tab_attuale = request.form.get('tab', 'asta')
    preferiti = request.form.get('preferiti', '0')
    
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
    
    return redirect(f'/?tab={tab_attuale}&ruolo={ruolo_attuale}&sort1={sort_attuale}&preferiti={preferiti}')

@app.route('/preferito', methods=['POST'])
def preferito():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return richiedi_login()

    id_giocatore = int(request.form['id_giocatore'])
    ruolo_attuale = request.form['ruolo']
    sort_attuale = request.form['sort1']
    preferiti = request.form['preferiti']
    
    conn = sqlite3.connect(FILE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT Preferito FROM giocatori WHERE Id=?", (id_giocatore,))
    attuale = cursor.fetchone()[0]
    nuovo_stato = '' if attuale == 'SI' else 'SI'
    
    cursor.execute("UPDATE giocatori SET Preferito=? WHERE Id=?", (nuovo_stato, id_giocatore))
    conn.commit()
    conn.close()
    
    return redirect(f'/?tab=asta&ruolo={ruolo_attuale}&sort1={sort_attuale}&preferiti={preferiti}')

@app.route('/reset_asta', methods=['POST'])
def reset_asta():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return richiedi_login()

    conn = sqlite3.connect(FILE_DB)
    cursor = conn.cursor()
    cursor.execute("UPDATE giocatori SET Acquistato='', Mio='', Costo=0")
    conn.commit()
    conn.close()

    return redirect('/?tab=rosa')

if __name__ == '__main__':
    app.run(port=2828)