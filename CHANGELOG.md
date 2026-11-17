# Changelog

## 1.1.0
- Il nome nell'app, nella finestra e nei file scaricabili è Twenties. Il repository e la cartella dati restano quelli di prima, così un account già creato non si perde.
- Si usa subito, anche senza account. L'account locale o Google è facoltativo.
- Mappa delle cartelle analizzate, ad anelli o a riquadri, con il perché dell'etichetta. Si può aprire la cartella o spostarla nel Cestino, dopo una conferma.
- Tre schermate all'inizio, solo la prima volta: cosa fa, cosa non tocca, dove finiscono i file.
- Italiano e inglese. All'avvio segue la lingua del sistema; si cambia dalle impostazioni.
- Avviso di una versione nuova, spento finché non lo accendi. Legge solo il numero dell'ultima release pubblica. Nessuna telemetria.
- Stima dello Scarto, separata da doppioni e archivi. I doppioni restano un confronto sull'hash dell'intero file.
- Libreria dei giochi: peso, ultimo accesso, launcher.
- Promemoria del solo Scarto, spento di default, sempre con anteprima e solo verso il Cestino.
- Cronologia degli spostamenti, con annulla quando il Cestino lo consente ancora.

## 1.0.3
- L'app si apre in una finestra propria. Chiudendo la finestra il programma termina.
- L'accesso con Google resta nel browser di sistema (Google non accetta il login dentro la finestra). Poi la finestra risulta già connessa.
- Se la finestra non è disponibile, per esempio manca WebView2 su Windows, si apre il browser e compare un messaggio.
- Se il programma è già aperto, non ne parte una seconda copia: viene riportata avanti la finestra esistente. Se a tenere la porta è una versione vecchia, compare un errore invece della schermata vecchia.

## 1.0.0
- Nuovo: accesso con Google nelle versioni ufficiali (solo identificativo, email e nome; nessun altro servizio Google).
- Prima versione pubblica, con installer per Windows e macOS (build automatica su GitHub).
- Nuovo: pulsante **Elimina account** che cancella account, sessioni e richieste di reset dal file locale.
- Nuovo: versione impacchettata senza terminale: i messaggi tecnici vanno in `app.log` nella cartella dati.
- Cambiato: senza server di posta il recupero password non è disponibile; l'app lo spiega e indica come ripartire.
- Cambiato: il link di reset non viene mai scritto in un file di log.
- Sito con informativa privacy, termini di servizio e cookie policy (italiano e inglese).
