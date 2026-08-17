from odk_skat import EIndkomstKlient
from datetime import date
from dateutil.relativedelta import relativedelta

class SkatService:
    def __init__(
        self,
        skat_klient: EIndkomstKlient
        ):
        self.skat_klient = skat_klient
    
    def kontroller_om_borger_i_målgruppe(self, cpr:str) -> bool:
        
        indkomster = self.skat_klient.hent_indkomst_oplysninger(cpr, medarbejder_id="roboa", fra_dato=date.today() - relativedelta(months=36), til_dato=date.today())
        
        konthjælpsydelser: list[dict] = []
        
        # Tjek om der er 'Folke-, førtids- og seniorpension', hvis ja ikke i målgruppe
        for indkomst in indkomster:
            indkomst["Skattemåned"] = indkomst["Lønperiode start"].strftime("%m-%Y")
            if indkomst["Indkomstart_19"] == 'Folke-, førtids- og seniorpension':
                return False
            
            if indkomst['Indkomstart'] == 'kontanthjælp' and (indkomst['A-indkomst'] > 0 or indkomst['A-indkomst uden AM-bidrag'] > 0 or indkomst['B-indkomst'] > 0):
                if indkomst['Indkomstart_19'] == 'Kommunalt ressourceforløbsydelse':
                    continue
                else:
                    konthjælpsydelser.append(indkomst)
        
        if 18 <= len(set(ydelse['Skattemåned'] for ydelse in konthjælpsydelser)):
            return True
        
        return False