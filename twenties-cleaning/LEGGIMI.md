# Twenties Cleaning

> Questa guida è per chi avvia il programma **da codice sorgente**. Se hai scaricato il .exe o il .dmg dalle Releases, non serve Python: vedi il README.

## Avvio da codice sorgente
- **Mac**: doppio clic su `run_mac.command` (la prima volta: tasto destro → Apri). Serve Python 3 (python.org).
  Per leggere anche le cartelle protette: Impostazioni di Sistema › Privacy e sicurezza › **Accesso completo al disco** → aggiungi Terminale.
  Al primo spostamento nel Cestino macOS chiede di far controllare Finder al Terminale: consenti.
  Se usi Python di python.org e Google dà errore di certificati: esegui `Install Certificates.command` nella cartella Python.
- **Windows**: doppio clic su `run_windows.bat`, oppure `python src\twenties_cleaning.py` (meglio come Amministratore).

## Accesso con Google (attivo nelle versioni ufficiali; qui sotto, se vuoi usare le tue credenziali)
1. Google Cloud Console → Credenziali → ID client OAuth → tipo "Applicazione web" (o "App desktop").
2. URI di reindirizzamento autorizzato: `http://127.0.0.1:8765/auth/google/callback` (con HTTPS: `https://...`).
3. Crea il file `.env` nella cartella dati (Mac: `~/Library/Application Support/TwentiesCleaning/`, Windows: `%APPDATA%\TwentiesCleaning\`):
```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```
Nelle versioni ufficiali le credenziali sono incorporate dalla build (dai secret di GitHub), non dal codice.

## Reset password
Senza server di posta il link compare nel Terminale (solo se avvii da codice; nell'app scaricabile non è disponibile) (valido 15 minuti, monouso). Per l'email aggiungi a `.env`:
`SMTP_HOST`, `SMTP_PORT` (587 o 465), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.

## HTTPS
Il programma ascolta solo su 127.0.0.1. Per attivare HTTPS: `brew install mkcert && mkcert -install && mkcert 127.0.0.1`, poi
`TC_TLS_CERT=127.0.0.1.pem TC_TLS_KEY=127.0.0.1-key.pem python3 src/twenties_cleaning.py`
