# Twenties

**IT** · [English below](#english)

Vedi cosa pesa. Decidi tu.

App **gratuita e open source** per Windows e macOS. Mostra cartelle, file grandi, giochi, doppioni (hash del contenuto) e archivi già estratti, e spiega il perché di ogni etichetta. Sposta nel Cestino solo ciò che confermi. Non ottimizza nulla da sola e non invia elenchi di file.

Si usa subito, anche senza account. L'account locale o Google è facoltativo e resta su questo computer. Chi aveva già un account lo ritrova: la cartella dati si chiama ancora `TwentiesCleaning`.

- Sito, privacy, termini e cookie: **https://twoventi.github.io/twenties-cleaning/**
- Download: [ultima versione](https://github.com/twoventi/twenties-cleaning/releases/latest) (con `SHA256SUMS` per verificare i file)
- Lingua: italiano o inglese, in base al sistema. Si cambia dalle impostazioni.

## Per gli utenti
Scarica il file per il tuo sistema e aprilo. Compare la finestra di Twenties. I programmi pubblicati non hanno una firma a pagamento, quindi Windows e macOS possono avvisare la prima volta: le istruzioni sono nelle [domande frequenti](https://twoventi.github.io/twenties-cleaning/#faq). I file si controllano con `SHA256SUMS`.

L'avviso di una versione nuova è spento. Se lo accendi, Twenties legge solo il numero dell'ultima release pubblica su GitHub. Non parte telemetria.

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
git tag v1.1.0
git push origin v1.1.0
```
GitHub Actions costruisce `Twenties-Windows.exe` e i `.dmg` (Intel e, se il runner c'è, Apple Silicon), prova che il programma si avvii, crea `SHA256SUMS` e pubblica tutto in *Releases*. Se il runner Apple Silicon non è disponibile, escono comunque Windows e Intel. Controlla la scheda **Actions**.

### Prova in locale
```
python3 tests/smoke_test.py      # senza account, mappa, lingue, aggiornamenti simulati
python3 src/twenties_cleaning.py # avvio da codice (vedi LEGGIMI.md)
python3 scripts/make_assets.py   # rigenera le illustrazioni del sito
```

### Cosa è stato scelto
- La finestra è dell'app. L'accesso con Google, se lo usi, si apre nel browser di sistema: Google non lo accetta dentro la finestra.
- Nessun dato di analisi esce dal computer. L'unico contatto esterno è il controllo versione, e solo dopo il consenso.
- Il promemoria dello Scarto è spento. Se lo accendi, mostra un'anteprima e sposta nel Cestino solo dopo la conferma.
- Il sito non usa cookie né servizi esterni: per questo non c'è un banner dei cookie.

## Licenza
[MIT](LICENSE). Icona e illustrazioni sono originali e hanno la stessa licenza.

---

<a id="english"></a>
## English

See what takes space. You decide.

A **free, open source** app for Windows and macOS. It shows folders, large files, games, duplicates (a hash of the content) and archives you already extracted, and it says why each label is there. It moves to the Trash only what you confirm. It does not optimize anything by itself and it does not upload file lists.

You can use it immediately, with no account. A local or Google account is optional and stays on this computer. An account you already had is still there: the data folder is still named `TwentiesCleaning`.

- Website, privacy, terms and cookies: **https://twoventi.github.io/twenties-cleaning/**
- Downloads: [latest release](https://github.com/twoventi/twenties-cleaning/releases/latest) (with `SHA256SUMS` to verify the files)
- Language: Italian or English, from the system language. You can change it in settings.

The published files have no paid code signature, so Windows and macOS may warn on first launch; see the [FAQ](https://twoventi.github.io/twenties-cleaning/?lang=en#faq). Check the files against `SHA256SUMS`. The “new version” notice is off until you turn it on; then Twenties only reads the latest public release number from GitHub. To publish: run `scripts/personalize.py`, push to GitHub, enable Pages (main / docs), then push a tag such as `v1.1.0`.

License: [MIT](LICENSE).
