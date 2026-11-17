# Twenties

Per chi avvia il programma dal codice. Se hai scaricato l'exe o il dmg, aprilo e basta.

```
pip install -r requirements.txt
python src/twenties_cleaning.py
```

Su Mac il comando è `python3`, oppure `run_mac.command`. Su Windows c'è `run_windows.bat`.

La finestra si chiama Twenties. Chiudendola, il programma termina. Si può scansionare senza account.

- Browser al posto della finestra: `python src/twenties_cleaning.py --browser`
- Senza finestra, per i test: `python src/twenties_cleaning.py --headless`

Se la finestra non si apre, manca WebView2 (su Windows 11 c'è già). In quel caso si apre il browser.

Su Mac, per le cartelle protette: Impostazioni di Sistema, Privacy e sicurezza, Accesso completo al disco. Al primo spostamento nel Cestino, consenti il controllo di Finder.

I percorsi con spazi, OneDrive e lettere accentate vanno bene.

Se dice che è già aperto, chiudi l'altra copia da Gestione attività o da Monitoraggio Attività.

## Dati

La cartella si chiama ancora `TwentiesCleaning`, così un account vecchio resta dov'era.

- Mac: `~/Library/Application Support/TwentiesCleaning/`
- Windows: `%APPDATA%\TwentiesCleaning\`

L'account è facoltativo. Email e password, se le crei, restano in quel file.

Google, se lo configuri, si apre nel browser di sistema. In locale: variabili `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`, oppure `src/_google_config.py` (è nel `.gitignore`). In Google Cloud l'URI di reindirizzamento è `http://127.0.0.1:8765/auth/google/callback`.

## Impostazioni

Lingua: quella del sistema, italiano o inglese. Si cambia in Impostazioni.

Avviso di versione: spento. Se lo accendi, legge solo il numero dell'ultima release su GitHub.

Promemoria scarto: spento. Se lo accendi, mostra un elenco e sposta nel Cestino solo se confermi.

La cronologia tiene gli spostamenti. Annulla rimette il file al posto quando il Cestino lo permette ancora.

## Posta e HTTPS

Senza server di posta, il link per la password compare nel terminale solo se avvii da codice. Vale 15 minuti, una volta sola. Per l'email, nel `.env` della cartella dati: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.

Il programma ascolta solo su 127.0.0.1. Per HTTPS: `mkcert -install && mkcert 127.0.0.1`, poi `TC_TLS_CERT` e `TC_TLS_KEY`.
