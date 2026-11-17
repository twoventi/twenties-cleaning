# Twenties Cleaning

**IT** · [English below](#english)

App **gratuita e open source** per Windows e macOS che mostra cosa occupa spazio sul computer (cartelle, file grandi, giochi, doppioni, archivi già estratti) e sposta nel Cestino solo ciò che scegli tu. Funziona offline e non invia dati a nessuno.

- Sito, privacy, termini e cookie: **https://twoventi.github.io/twenties-cleaning/**
- Download: [ultima versione](https://github.com/twoventi/twenties-cleaning/releases/latest) (con `SHA256SUMS` per verificare i file)
- Interfaccia dell'app in italiano.

## Per gli utenti
Scarica il file per il tuo sistema e aprilo: compare la finestra dell'app. Se su Windows manca WebView2, un messaggio lo dice e si apre il browser. I programmi non hanno la firma a pagamento, quindi Windows e macOS mostrano un avviso la prima volta: le istruzioni sono nelle [domande frequenti](https://twoventi.github.io/twenties-cleaning/#faq).

## Per chi pubblica o modifica il progetto

### 1. Personalizza i segnaposto (una volta sola)
```
python3 scripts/personalize.py --user TUO_UTENTE_GITHUB --repo twenties-cleaning --name "Nome Cognome" --email tua@email
```
Questo inserisce nome, email e indirizzi in sito, licenza e sicurezza. Rilancia lo script solo su una copia pulita.

### 2. Pubblica su GitHub
1. Crea un repository **pubblico** su GitHub con lo stesso nome indicato sopra.
2. Dalla cartella del progetto: `git init`, `git add .`, `git commit -m "Prima versione"`, `git branch -M main`, `git remote add origin https://github.com/TUO_UTENTE/NOME_REPO.git`, `git push -u origin main`.
3. Su GitHub: **Settings › Pages › Build and deployment › Deploy from a branch › main / docs › Save**. Il sito sarà online in pochi minuti.

### 3. Crea una versione scaricabile
```
git tag v1.0.0
git push origin v1.0.0
```
GitHub Actions costruisce `.exe` (Windows) e `.dmg` (Mac Apple Silicon e Intel), prova che ogni programma si avvii, crea `SHA256SUMS` e pubblica tutto in *Releases*. Controlla la scheda **Actions**: se un passaggio fallisce, il log dice quale.

### Prova in locale
```
pip install -r requirements.txt
python3 tests/smoke_test.py      # registra, entra, elimina l'account (senza finestra)
python3 src/twenties_cleaning.py # finestra dell'app (vedi LEGGIMI.md)
python3 scripts/make_assets.py   # rigenera icone e illustrazioni originali
```

Le credenziali Google, se ti servono in locale, stanno nelle variabili `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` oppure in `src/_google_config.py` (è nel `.gitignore`). Vedi LEGGIMI.md.

### Cosa è stato scelto
- L'app ha una finestra propria. L'accesso con Google si apre nel browser di sistema, perché Google blocca il login nelle finestre incorporate; al termine la finestra dell'app risulta connessa. Se la finestra non è disponibile, si usa il browser.
- Nessuna firma a pagamento: i file sono verificabili con `SHA256SUMS`. Se un giorno vuoi eliminare gli avvisi, servono Apple Developer Program (99 $/anno) e un certificato di firma per Windows.
- Nessun controllo automatico degli aggiornamenti (nessun dato esce dal computer): gli utenti seguono le *Releases* con **Watch › Custom › Releases**.
- Il sito non usa cookie né servizi esterni: per questo non c'è un banner dei cookie.

## Licenza
[MIT](LICENSE). Icone e illustrazioni sono originali e hanno la stessa licenza.

---

<a id="english"></a>
## English

A **free, open source** app for Windows and macOS that shows what is taking up disk space (folders, large files, games, duplicates, already-extracted archives) and moves only what you choose to the Recycle Bin. It works offline and sends no data anywhere. The app interface is in Italian.

- Website, privacy, terms and cookies: **https://twoventi.github.io/twenties-cleaning/**
- Downloads: [latest release](https://github.com/twoventi/twenties-cleaning/releases/latest) (with `SHA256SUMS` to verify the files)

The programs have no paid code signature, so Windows and macOS show a warning on first launch; see the [FAQ](https://twoventi.github.io/twenties-cleaning/?lang=en#faq). The app opens in its own window. Google sign-in opens in the system browser (Google blocks embedded login); the app window then shows you as signed in. If the window cannot open, the browser is used instead. To publish: run `scripts/personalize.py`, push to GitHub, enable Pages (main / docs), then push a tag like `v1.0.0` to build the releases. From source: `pip install -r requirements.txt` then `python src/twenties_cleaning.py`. Local Google credentials: environment variables `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, or `src/_google_config.py` (gitignored).

License: [MIT](LICENSE).
