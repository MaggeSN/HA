# Filstruktur
Her står det litt om hvor de forskjellige funksjonene finnes.

Python script med algoritme basert på nettleien, og kode for på- og avskruing av enheter finnes i mappen "python_scripts" i filen "energy_control_simulering.py"

Script for automasjoner er lagret i automations.yaml. Algoritmen som er basert på strømpriser for bereder og elbil finnes også i automations.yaml.
Egendefinerte sensorer er lagret i template.yaml

Lovelace forsiden finnes i .storage/lovelace. Det trengs Apexcharts, som er en tredjeparts-integrasjon i HomeAssistant, før Lovelace forsiden kan brukes. Apexcharts kan lastes ned gjennom Home Assistant Community Store (HACS) https://www.smarthomescene.com/guides/apexcharts-card-advanced-graphs-for-your-home-assistant-ui/

Noen id'eer for entiteter som HAN-sensoren er unik for denne løsningen og må endres om det skal brukes i et annet system. 
