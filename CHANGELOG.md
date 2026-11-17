# Changelog

## 1.1.0
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
