# Changelog

## 2.0.0
Rispetto alla 1.0.3.

- Il nome visibile è Twenties. La cartella dati resta `TwentiesCleaning`, così un account già creato non si perde.
- Si usa senza account. Account locale o Google sono facoltativi.
- Mappa delle cartelle, ad anelli o a riquadri, con il motivo dell'etichetta. Si apre la cartella o si sposta nel Cestino, dopo una conferma.
- Tre schermate solo la prima volta: cosa fa, cosa non tocca, dove finiscono i file.
- Italiano e inglese, dalla lingua del sistema.
- Avviso di una versione nuova, spento finché non lo accendi. Nessuna telemetria.
- Stima dello scarto, separata da doppioni e archivi. I doppioni restano un confronto sull'hash del file.
- Elenco giochi: peso, ultimo accesso, launcher.
- Promemoria del solo scarto, spento, sempre con anteprima e solo verso il Cestino.
- Cronologia degli spostamenti, con annulla quando il Cestino lo permette.
- Un solo file Mac per Intel e Apple Silicon. Se quel job non parte, la release di Windows esce lo stesso.

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
