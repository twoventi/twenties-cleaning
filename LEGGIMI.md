# Twenties Cleaning

> Questa guida è per chi avvia il programma **da codice sorgente**. Se hai scaricato il .exe o il .dmg dalle Releases, aprilo: compare la finestra dell'app. Non serve Python.

## Avvio da codice sorgente

Serve Python 3.8 o più recente.

```
pip install -r requirements.txt
python src/twenties_cleaning.py
```

Su Mac il comando è `python3` (oppure doppio clic su `run_mac.command`). Su Windows puoi usare `run_windows.bat`.

Si apre una finestra intitolata **Twenties Cleaning**. Chiudendola, il programma termina e libera la porta.

- Per usare il browser al posto della finestra: `python src/twenties_cleaning.py --browser`
- Per i test automatici, senza finestra e senza browser: `python src/twenties_cleaning.py --headless` (oppure la variabile `TC_HEADLESS=1`)

Se la finestra non si apre (su Windows manca WebView2, già presente su Windows 11), il programma lo dice e apre il browser.

- **Mac**, cartelle protette: Impostazioni di Sistema › Privacy e sicurezza › **Accesso completo al disco** → aggiungi Terminale (se avvii da script) oppure Twenties Cleaning.
  Al primo spostamento nel Cestino macOS chiede di far controllare Finder: consenti.
  Se usi Python di python.org e Google dà errore di certificati: esegui `Install Certificates.command` nella cartella Python.
- **Windows**: per leggere anche le cartelle protette, avvia il programma come Amministratore.

Se compare «è già aperto» o «porta occupata», c'è già una copia in esecuzione (anche una versione vecchia). Chiudila da Gestione attività (Windows) o Monitoraggio Attività (Mac) e riapri. Non parte una seconda copia, così non vedi la schermata vecchia.

## Credenziali Google in locale

L'accesso con Google è facoltativo. Le versioni ufficiali lo hanno già dentro (dai secret di GitHub, non dal codice). In locale puoi dare le tue credenziali in uno di questi modi, **senza committarle**:

1. Variabili d'ambiente `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`.
2. File `src/_google_config.py` (è nel `.gitignore`):

```python
CLIENT_ID = "....apps.googleusercontent.com"
CLIENT_SECRET = "...."
```

In Google Cloud Console crea un ID client OAuth di tipo «Applicazione web» e aggiungi questo URI di reindirizzamento:

`http://127.0.0.1:8765/auth/google/callback`

Il consenso di Google si apre nel browser di sistema: Google blocca il login dentro la finestra dell'app. Quando hai finito, la finestra di Twenties Cleaning risulta già connessa. Puoi chiudere la scheda del browser.

In alternativa vale ancora il file `.env` nella cartella dati (Mac: `~/Library/Application Support/TwentiesCleaning/`, Windows: `%APPDATA%\TwentiesCleaning\`) con le stesse due variabili.

## Reset password

Senza server di posta il link compare nel Terminale (solo se avvii da codice; nell'app scaricabile non è disponibile) (valido 15 minuti, monouso). Per l'email aggiungi a `.env`:
`SMTP_HOST`, `SMTP_PORT` (587 o 465), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.

## HTTPS

Il programma ascolta solo su 127.0.0.1. Per attivare HTTPS: `brew install mkcert && mkcert -install && mkcert 127.0.0.1`, poi
`TC_TLS_CERT=127.0.0.1.pem TC_TLS_KEY=127.0.0.1-key.pem python3 src/twenties_cleaning.py`
