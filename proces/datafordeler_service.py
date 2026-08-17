from datafordeler import Datafordeler
from datetime import date

class DatafordelerService:
    def __init__(
        self,
        datafordeler: Datafordeler
        ):
        self.datafordeler = datafordeler
    
    #Dette skal ikke bruges her, dette skal over i processen Udrejsebreve...
    
    def beregn_alder(self, cpr: str) -> int:
        """Calculate age in years from CPR number."""
        # Extract date parts from CPR (DDMMYY format)
        day = int(cpr[0:2])
        month = int(cpr[2:4])
        year_2digit = int(cpr[4:6])
        seventh_digit = int(cpr[6])
        
        # Determine century based on 7th digit and year
        if seventh_digit >= 4 and year_2digit <= 36:
            birth_year = 2000 + year_2digit
        else:
            birth_year = 1900 + year_2digit
        
        birth_date = date(birth_year, month, day)
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        return age
    
    def find_person_oplysninger(self, cpr: str) -> tuple[list[str], dict, str]:
        ægtefælle_cpr = ""
        børne_cpr = []
        adresseoplysninger = {}
        
        
        cpr = cpr.replace("-","")
        
        personoplysninger = self.datafordeler.hent_personoplysninger(cpr)
        
        civilstande = personoplysninger["Person"]["Civilstande"]
        
        for ægteskab in civilstande:
            if(ægteskab["Civilstand"]["status"] == "aktuel" and ægteskab["Civilstand"]["Civilstandstype"] == "gift" and "Aegtefaelle" in ægteskab["Civilstand"]):
                ægtefælle_cpr = ægteskab["Civilstand"]["Aegtefaelle"]["AegtefaellePersonnummer"]
                break
        
        adresser = personoplysninger["Person"]["Adresseoplysninger"]
        
        adresseoplysninger = next((adresse["Adresseoplysninger"] for adresse in adresser if adresse["Adresseoplysninger"]["status"] == "aktuel"), {})
        
        if "Boern" in personoplysninger["Person"]:
            alle_børn = personoplysninger["Person"]["Boern"]
        else:
            alle_børn = {}
        
        for barn in alle_børn:
            barn_cpr = barn["Barnoplysning"]["Barn"]["barnPersonnummer"]
            alder = self.beregn_alder(barn_cpr)
            
            if alder > 17:
                continue
            
            # Get barn's current address
            barn_adresse = barn["Barnoplysning"]["Barn"]["Adresseoplysninger"]
            
            parent_cpr_adr = adresseoplysninger["CprAdresse"]
            barn_cpr_adr = barn_adresse["CprAdresse"]
            
            # Check if the three fields match
            if parent_cpr_adr["husnummer"] == barn_cpr_adr["husnummer"] and parent_cpr_adr["vejadresseringsnavn"] == barn_cpr_adr["vejadresseringsnavn"] and parent_cpr_adr["postdistrikt"] == barn_cpr_adr["postdistrikt"]:
                børne_cpr.append(barn_cpr)
            
        
        return børne_cpr, adresseoplysninger, ægtefælle_cpr