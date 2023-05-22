sum_energiforbruk = 0
tellevariabel = 0
tids_intervall = 120 #sekunder
total_tid = 3600 #sekunder
endelig_effektgrense = float(hass.states.get('input_number.valgt_timegrense').state)*1000
ant_sjekker = total_tid // tids_intervall



# Funksjonen kjører en algoritme som holder snittforbruket gjennom en time under 5kWh.
def oppdater_energikontroll(hass, nåværende_effektforbruk):
    #Globale variabler som er lagret i configuration.yaml 
    sum_energiforbruk = float(hass.states.get("input_number.sum_energiforbruk_simulering").state)
    tellevariabel = float(hass.states.get("input_number.tellevariabel_simulering").state)
    
    if tellevariabel == ant_sjekker - 1: # tilbakestiller scriptet når en time har gått.
        tellevariabel = 0
        sum_energiforbruk = 0
        neste_maksgrense = endelig_effektgrense
        gjenstående_energi_budsjett = endelig_effektgrense
        hass.services.call("automation", "turn_off", {"entity_id": "automation.simulering"})
        
    else:    
        nåværende_energiforbruk = nåværende_effektforbruk * (tids_intervall / total_tid) # Konverterer til Wh

        sum_energiforbruk = sum_energiforbruk + nåværende_energiforbruk # Summerer slik at jeg får simulert totalforbruk gjennom timen
        #sum_energiforbruk = float(hass.states.get("sensor.energiforbruk_denne_timen").state) # Denne leser totalforbruk gjennom HAN-sensoren, og egner seg mer til en reell implementering
        tellevariabel = tellevariabel + 1
        gjenstående_energi_budsjett = endelig_effektgrense - sum_energiforbruk
        remaining_checks = ant_sjekker - tellevariabel 
        
        neste_maksgrense = gjenstående_energi_budsjett / remaining_checks 
        neste_maksgrense = neste_maksgrense / (tids_intervall/ total_tid) - 300 # Konverterer tilbake til watt # Legger til sikkerhetsmargin på 300W


        effektregulering(hass, neste_maksgrense, nåværende_effektforbruk)

    hass.services.call("input_number", "set_value", {"entity_id": "input_number.neste_maksgrense_simulering", "value": "{:.2f}".format(neste_maksgrense)})
    hass.services.call("input_number", "set_value", {"entity_id": "input_number.gjenstaende_energi_budsjett_simulering", "value": "{:.2f}".format(gjenstående_energi_budsjett)})
    hass.services.call("input_number", "set_value", {"entity_id": "input_number.sum_energiforbruk_simulering", "value": "{:.2f}".format(sum_energiforbruk)})
    hass.services.call("input_number", "set_value", {"entity_id": "input_number.tellevariabel_simulering", "value": tellevariabel})
        


def effektregulering(hass, neste_maksgrense, nåværende_effektforbruk):
    

    enheter = hent_enheter(hass) #henter liste med dictionaries av hver enhet
    enheter.sort(key=lambda x: (x["prioritet"], x["effektforbruk"])) #Sorterer først ut fra ascending priority også ascending effektforbruk.

    if nåværende_effektforbruk > neste_maksgrense: 
        required_reduction = nåværende_effektforbruk - neste_maksgrense
        skru_av_enheter(hass, enheter, required_reduction)
    elif nåværende_effektforbruk < neste_maksgrense:# and tellevariabel < 3/4 * ant_sjekker: # cooldown: for å ikke skru på enheter ved slutten av en time. 
        skru_på_enheter(hass, enheter, neste_maksgrense)    
        


def skru_av_enheter(hass, enheter, required_reduction):

    laveste_prioritet = 10
    min_vektfaktor = float("inf")
    beste_kandidat = None
    differanse = 1


    for device in enheter:
        device_state = hass.states.get(device["entitet_id"]).state
        enhet_prioritet = device["prioritet"]

        if device_state == "on" and enhet_prioritet != 10: # Enheter med prioritet 10 tas ikke med
            enhet_prioritet = math.pow(enhet_prioritet, 2) # Eksponentiell prioritet

            # Lagrer enheten med lavest prioritet
            if device["prioritet"] < laveste_prioritet:
                laveste_prioritet = device["prioritet"]

            differanse = required_reduction - device["effektforbruk"]

            # Mindre hastverk å skru av enheten om det ikke fører til at effektforbruket kommer seg under grensen.
            if differanse > 0:
                differanse = differanse + 1000
            else:
                differanse = abs(differanse)
                
            vektfaktor = differanse * enhet_prioritet

            if enhet_prioritet == 1: # Skru av enheter med prioritet 1 først
                beste_kandidat = device
                break

            # Enheten med minst vektfaktor blir beste kandidat
            # Enheten må også ha prioritet som ikke er 5 større enn enheten med lavest prioritet
            # Det betyr f.eks. at en enhet med prioritet 2 alltid blir valgt over en enhet med prioritet 7
            if vektfaktor < min_vektfaktor and device["prioritet"] - laveste_prioritet < 5:
                min_vektfaktor = vektfaktor
                beste_kandidat = device

    # Om en enhet er valgt som beste kandidat
    if beste_kandidat is not None:
        # Skru av enhet
        hass.services.call("input_boolean", "turn_off", {"entity_id": beste_kandidat["entitet_id"]})

        # Denne viser at det var algoritmen som skrudde av enheten, og ikke brukeren
        # Funksjonen hindrer at enheten skrur seg på av algoritmen om det var brukeren selv som skrudde enheten av
        hass.services.call("input_boolean", "turn_off", {"entity_id": beste_kandidat["algoritme_id"]})
    
    # Om varsel ikke allerede har blitt sendt ut denne timen
    elif hass.states.get("input_boolean.varsel_sendt_ut").state == "off":
        # Sender varsel om at energiforbruket kan overstige grensen
        service_data = {"message": f"Energiforbruket er i fare for å overstige {endelig_effektgrense/1000}kWh denne timen"}
        hass.services.call("notify", "mobile_app_magnuss_iphone", service_data)
        hass.services.call("notify", "mobile_app_theodor_skarstein_iphone", service_data)
        # Boolsk flagg
        hass.services.call("input_boolean", "turn_on", {"entity_id": "input_boolean.varsel_sendt_ut"})


def skru_på_enheter(hass, enheter, neste_maksgrense):

    maks_vektfaktor = -1
    beste_kandidat = None
    hoyeste_prioritet = -1
    differanse = 1

    for device in enheter: #Løkke som sjekker alle enheter i algoritme
        device_state = hass.states.get(device["algoritme_id"]).state
        enhet_prioritet = device["prioritet"]

        if device_state == "off" and enhet_prioritet != 1: # Avskrudde enheter og enheter med prio 1 skal ikke skrus på.
            enhet_prioritet = math.pow(enhet_prioritet, 2) #Gjør prioriteten til enhetene eksponentiell

            if enhet_prioritet == 100: # Hvis det er en enhet med prioritet 10, skru den på umiddelbart og gå ut av løkka.
                beste_kandidat = device
                break

            if device["prioritet"] > hoyeste_prioritet: #Lagrer enhet med høyest prioritet
                hoyeste_prioritet = device["prioritet"]

            margin = 1.4 * device["effektforbruk"] + 650 # Margin øker lineært med effektforbruk 
            differanse = neste_maksgrense - (nåværende_effektforbruk + margin)

            if differanse < 0: # ikke skru på enheten om det fører til at vi går over effektgrensen.
                differanse = -1

            vektfaktor = differanse * enhet_prioritet


            if vektfaktor > maks_vektfaktor and hoyeste_prioritet - device["prioritet"] < 5: # Høyere vektfaktor->bedre kandidat for å skru på.
                maks_vektfaktor = vektfaktor
                beste_kandidat = device

    if beste_kandidat is not None:
        hass.services.call("input_boolean", "turn_on", {"entity_id": beste_kandidat["entitet_id"]})
        hass.services.call("input_boolean", "turn_on", {"entity_id": beste_kandidat["algoritme_id"]})


def hent_enheter(hass):

    # Funksjon som implementerer enheter hardkodet i script.
    # Kan endre dette til å dynamisk legge inn nye enheter, men dette er en løsning for simulering.

    varmtvannsbereder_prioritet = float(hass.states.get("input_number.varmtvannsbereder_prioritet").state) # 1-10
    varmekabler_prioritet = float(hass.states.get("input_number.varmekabler_prioritet").state) # 1-10
    varmeovn_1_prioritet = float(hass.states.get("input_number.varmeovn_1_prioritet").state)
    varmeovn_2_prioritet = float(hass.states.get("input_number.varmeovn_2_prioritet").state)
    varmeovn_3_prioritet = float(hass.states.get("input_number.varmeovn_3_prioritet").state)
    varmeovn_4_prioritet = float(hass.states.get("input_number.varmeovn_4_prioritet").state)

    # Elbillader skal ikke inngå i algoritmen for på- og avskruing
    if hass.states.get("input_boolean.elbil_lader_paa").state == 'on':
        elbil_lader_prioritet = 10
    else:
        elbil_lader_prioritet = 1
        
    enheter = [
    {
        "effektforbruk": 2000,
        "prioritet": varmtvannsbereder_prioritet,
        "entitet_id": "input_boolean.varmtvannstank_paa",
        "algoritme_id": "input_boolean.algoritme_varmtvannstank"
    },
    {
        "effektforbruk": 1500,
        "prioritet": varmekabler_prioritet,
        "entitet_id": "input_boolean.varmekabler_paa",
        "algoritme_id": "input_boolean.algoritme_varmekabler"
    },
    {
        "effektforbruk": 1000,
        "prioritet": varmeovn_1_prioritet,
        "entitet_id": "input_boolean.varmeovn_1_paa",
        "algoritme_id": "input_boolean.algoritme_varmeovn_1"
    },
    {
        "effektforbruk": 500,
        "prioritet": varmeovn_2_prioritet,
        "entitet_id": "input_boolean.varmeovn_2_paa",
        "algoritme_id": "input_boolean.algoritme_varmeovn_2"
    },
    {
        "effektforbruk": 500,
        "prioritet": varmeovn_3_prioritet,
        "entitet_id": "input_boolean.varmeovn_3_paa",
        "algoritme_id": "input_boolean.algoritme_varmeovn_3" 
    },
    {
        "effektforbruk": 300,
        "prioritet": varmeovn_4_prioritet,
        "entitet_id": "input_boolean.varmeovn_4_paa",
        "algoritme_id": "input_boolean.algoritme_varmeovn_4" 
    },   
        {
        "effektforbruk": 7000,
        "prioritet": elbil_lader_prioritet,
        "entitet_id": "input_boolean.elbil_lader_paa",
        "algoritme_id": "input_boolean.algoritme_elbil_lader" 
    }   
    # ...
    ]

    return enheter


aut1 = hass.states.get('automation.skru_pa_enheter_ved_timeskifte').state
aut2 = hass.states.get('automation.skru_pa_enheter_simulasjon_1_time').state

# Sjekker hvilken av de to simuleringene (automasjonene) som er på
if aut2 == "on": # Simulering med dynamisk effektgrense
    effekt = float(hass.states.get("sensor.gjennomsnitt_30_siste_malinger_w_han_sensor").state)
    hass.states.set('input_number.na_forbruk_hvert_2_min', effekt)
    nåværende_effektforbruk = float(hass.states.get("sensor.navaerende_effektforbruk").state)
    oppdater_energikontroll(hass, nåværende_effektforbruk)

else:# elif aut1 == "on": # Simulering med selvvalgt effektgrense
    effektgrense = float(hass.states.get('input_number.grense_effektforbruk_simulering').state)
    nåværende_effektforbruk = float(hass.states.get("sensor.effektforbruk_simulerte_enheter").state)
    effektregulering(hass, effektgrense, nåværende_effektforbruk)



