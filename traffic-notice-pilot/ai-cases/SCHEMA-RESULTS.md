# Andre måling: JSON-skjema og presisert prompt

Modell: qwen2.5-coder:7b. Én kjøring per sak på de samme fire manuelt omskrevne testtekstene. Resultatene kommer fra Kais PowerShell-kjøring.

| Sak | Sitatkontroll | Manuell vurdering |
| --- | --- | --- |
| Koigen | Godkjent | Sted og arbeidsperiode er riktige. Tiltaket mangler skiltet omlegging. |
| Gåsbuvegen | Godkjent | Stedsnavn ble funnet, men endepunktene havnet i berørte. Tiltak og tidsrom deler opp setningen om at trafikkvakter slipper fram buss og utrykningskjøretøy i perioder. Gangadkomst er fortsatt ukjent. |
| Basarundergangen | Godkjent | Bilstengingen ble hentet. Svaret utelot at gående og syklende kunne passere, og den historiske konteksten. |
| CC Hamar | Avvist | «Holdeplassen» har stor H. Kilden har liten h. Valideringen stoppet ved dette feltet. |

Sitatkontroll: 3 av 4, mot 1 av 4 i første måling. Ingen av de fire svarene dekket hele forventningen. Vi endret både prompt og format, så målingen viser ikke hvilken endring som hjalp. Den sier heller ikke hvor godt modellen gjør det på hele artikler.
