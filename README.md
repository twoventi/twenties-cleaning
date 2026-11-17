# Twenties

Vedi cosa pesa. Decidi tu.

Programma per Windows e macOS. Mostra cartelle, file grandi, giochi, doppioni e archivi già estratti. Sposta nel Cestino solo quello che confermi. Si usa anche senza account.

- Sito: https://twoventi.github.io/twenties-cleaning/
- Download: https://github.com/twoventi/twenties-cleaning/releases/latest

## Aprire il file scaricato

Windows, se compare «Windows ha protetto il PC»: Ulteriori informazioni → Esegui comunque.

Mac: tasto destro sull'app → Apri.

Il controllo del file è in `SHA256SUMS`, accanto al download.

```
# Windows, PowerShell
Get-FileHash .\Twenties-Windows.exe -Algorithm SHA256

# Mac
shasum -a 256 Twenties-macOS.dmg
```

Il numero deve coincidere con la riga di quel file in `SHA256SUMS`.

## Per chi modifica il progetto

```
python3 scripts/personalize.py --user TUO_UTENTE_GITHUB --repo twenties-cleaning --name "Nome Cognome" --email tua@email
```

Poi push su `main`, GitHub Pages da `main` / `docs`, e un tag `v1.1.0` per la build. Escono `Twenties-Windows.exe` e, se il Mac di GitHub finisce in tempo, un `.dmg` solo (`Twenties-macOS.dmg`) con Intel e Apple Silicon insieme. Se il job Mac non parte, la release di Windows esce lo stesso.

```
python3 tests/smoke_test.py
python3 src/twenties_cleaning.py
```

Avvio da codice: [LEGGIMI.md](LEGGIMI.md). Licenza [MIT](LICENSE).

---

See what takes space. You decide.

A program for Windows and macOS. It shows folders, large files, games, duplicates and archives you already extracted. It moves to the Trash only what you confirm. You can use it without an account.

On Windows, if you see “Windows protected your PC”: More info → Run anyway.

On a Mac: right-click the app → Open.

Check the file against `SHA256SUMS` (`Get-FileHash` on Windows, `shasum -a 256` on a Mac). The Mac download is one disk image for both Intel and Apple Silicon. If that build does not finish, the Windows release is still published.
