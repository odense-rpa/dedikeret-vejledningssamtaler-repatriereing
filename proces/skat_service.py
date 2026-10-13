import logging
from odk_skat import EIndkomstKlient
from datetime import date
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

class SkatService:
    def __init__(
        self,
        skat_klient: EIndkomstKlient
        ):
        self.skat_klient = skat_klient
    
    def kontroller_om_borger_i_målgruppe(self, cpr:str) -> bool:
        
        indkomster = self.skat_klient.hent_indkomst_oplysninger(cpr, medarbejder_id="roboa", fra_dato=date.today() - relativedelta(months=36), til_dato=date.today())
        logger.info("eIndkomst: %d indkomstrækker hentet", len(indkomster))

        konthjælpsydelser: list[dict] = []
        
        # Tjek om der er 'Folke-, førtids- og seniorpension', hvis ja ikke i målgruppe
        for indkomst in indkomster:
            indkomst["Skattemåned"] = indkomst["Lønperiode start"].strftime("%m-%Y")
            indkomstart_19 = (indkomst.get("Indkomstart_19") or "").casefold()

            if indkomstart_19 == "folke-, førtids- og seniorpension":
                logger.info("Borger har folke-, førtids- eller seniorpension: ikke i målgruppe")
                return False

            if (indkomst.get("Indkomstart") or "").casefold() == "kontanthjælp" and (indkomst['A-indkomst'] > 0 or indkomst['A-indkomst uden AM-bidrag'] > 0 or indkomst['B-indkomst'] > 0):
                if indkomstart_19 == "kommunalt ressourceforløbsydelse":
                    continue
                else:
                    konthjælpsydelser.append(indkomst)
        
        antal_måneder = len(set(ydelse['Skattemåned'] for ydelse in konthjælpsydelser))
        i_målgruppe = 18 <= antal_måneder
        logger.info("Måneder med kontanthjælp: %d (kræver 18), i målgruppe: %s", antal_måneder, i_målgruppe)
        return i_målgruppe