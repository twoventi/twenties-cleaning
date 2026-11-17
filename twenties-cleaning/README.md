# Twenties Cleaning

**IT** · [English below](#english)

App **gratuita e open source** per Windows e macOS che mostra cosa occupa spazio sul computer (cartelle, file grandi, giochi, doppioni, archivi già estratti) e sposta nel Cestino solo ciò che scegli tu. Funziona offline e non invia dati a nessuno.

- Sito, privacy, termini e cookie: **https://{{GITHUB_USER}}.github.io/{{REPO}}/**
- Download: [ultima versione](https://github.com/{{GITHUB_USER}}/{{REPO}}/releases/latest) (con `SHA256SUMS` per verificare i file)
- Interfaccia dell'app in italiano.

## Per gli utenti
Scarica il file per il tuo sistema, aprilo e segui la pagina che compare nel browser. I programmi non hanno la firma a pagamento, quindi Windows e macOS mostrano un avviso la prima volta: le istruzioni sono nelle [domande frequenti](https://{{GITHUB_USER}}.github.io/{{REPO}}/#faq).

## Per chi pubblica o modifica il progetto

### 1. Personalizza i segnaposto (una volta sola)
```
python3 scripts/personalize.py --user TUO_UTENTE_GITHUB --repo {{REPO}} --name "Nome Cognome" --email tua@email
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
python3 tests/smoke_test.py      # registra, entra, elimina l'account
python3 src/twenties_cleaning.py # avvio da codice (vedi LEGGIMI.md)
python3 scripts/make_assets.py   # rigenera icone e illustrazioni originali
```

### Cosa è stato scelto
- L'app apre il browser predefinito (non una finestra propria): l'accesso con Google non funziona nelle finestre incorporate.
- Nessuna firma a pagamento: i file sono verificabili con `SHA256SUMS`. Se un giorno vuoi eliminare gli avvisi, servono Apple Developer Program (99 $/anno) e un certificato di firma per Windows.
- Nessun controllo automatico degli aggiornamenti (nessun dato esce dal computer): gli utenti seguono le *Releases* con **Watch › Custom › Releases**.
- Il sito non usa cookie né servizi esterni: per questo non c'è un banner dei cookie.

## Licenza
[MIT](LICENSE). Icone e illustrazioni sono originali e hanno la stessa licenza.

---

<a id="english"></a>
## English

A **free, open source** app for Windows and macOS that shows what is taking up disk space (folders, large files, games, duplicates, already-extracted archives) and moves only what you choose to the Recycle Bin. It works offline and sends no data anywhere. The app interface is in Italian.

- Website, privacy, terms and cookies: **https://{{GITHUB_USER}}.github.io/{{REPO}}/**
- Downloads: [latest release](https://github.com/{{GITHUB_USER}}/{{REPO}}/releases/latest) (with `SHA256SUMS` to verify the files)

The programs have no paid code signature, so Windows and macOS show a warning on first launch; see the [FAQ](https://{{GITHUB_USER}}.github.io/{{REPO}}/?lang=en#faq). To publish: run `scripts/personalize.py`, push to GitHub, enable Pages (main / docs), then push a tag like `v1.0.0` to build the releases.

License: [MIT](LICENSE).
