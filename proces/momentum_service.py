from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from proces.models import Borger
from automation_server_client import WorkItemError

OPGAVE_TITEL_PRÆFIKSER = (
    "Afhold dedikeret vejledningssamtale om repatirering - Statsborgerskab",  # TODO: Fjern stavefejl
    "Afhold dedikeret vejledningssamtale om repatriering - Statsborgerskab",
)

OPGAVE_LUK_PRÆFIKSER = (
    "Afhold dedikeret vejledningssamtale om repatirering",  # TODO: Fjern stavefejl
    "Afhold dedikeret vejledningssamtale om repatriering",
)
BREV_OPGAVE_TITEL = "Brev sendt omkring repatriering - robot"

LUKKEKODE_IY = ""  # TODO: Udfyld taksonomikode for lukkeårsag

class MomentumService:
    def __init__(
            self,
            momentum: MomentumClientManager,
            tracker: Tracker
            ):
        
        self.momentum = momentum
        self.tracker = tracker

    
    def find_borgere(self) -> dict[str, dict] | None:

        query: dict = {
            "columns": [
                "displayName",
                "cpr",
                "targetGroupCode",
                "activeTags",
                "activeSupplementalCases/supplementalCaseTypeId"
            ],
            "sort": [
                {
                    "fieldName": "displayName",
                    "ascending": True
                }
            ],
            "filters": [
                {
                    "customFilter": "",
                    "fieldName": "targetGroupCode",
                    "values": []
                },
                {
                    "fieldName": "activeSupplementalCases/supplementalCaseTypeId",
                    "values": ["312b9bb4-686d-ec11-9898-001dd8b71e89"]
                }
            ],
            "searchFieldsDetails": [],
            "impersonateCaseworkerId": "2d7cb6f2-15b9-4969-af82-6f1c2a8abab4",
            "term": "*"
        }

        result = self.momentum.borgere.hent_borgere(filters=query["filters"])
        
        if result is None or 'data' not in result:
            return None
        
        # Convert to dict keyed by CPR
        borgere = {borger['cpr']: borger for borger in result['data']}

        return borgere
    
    def håndter_borger_i_målgruppe(self, momentum_borger: dict, sagsbehandler: dict, borger: Borger):


        supplerende_sager = self.momentum.borgere.hent_supplerendesager(momentum_borger)

        har_repatrierings_sag = False
        if supplerende_sager is not None:
            for sag in supplerende_sager:
                # Denne sag tjekkes der for og hvis den findes på borger skal behandling stoppes.
                if sag.get("title") == "Repatriering - diversesag" and not sag.get("closingReasonCode"):
                    return None
                # Tjekker om denne sag findes, ellers skal den oprettes.
                if sag.get("title") == "Dedikeret vejledningssamtale om repatriering - diversesag" and not sag.get("closingReasonCode"):
                    har_repatrierings_sag = True

        målgrupper = self.momentum.borgere.hent_målgrupper(momentum_borger)

        if målgrupper is not None:
            for målgruppe in målgrupper:
                if not målgruppe.get("closingReasonCode"):
                    self.momentum.borgere.opret_målgruppe(momentum_borger, "NB", date.today(), sagsbehandler)
        
        if not har_repatrierings_sag:
            self.momentum.borgere.opret_supplerendesag(momentum_borger, "Dedikeret vejledningssamtale om repatriering - diversesag", date.today(), sagsbehandler)


        opgaver = self.momentum.opgaver.hent_opgaver(momentum_borger)

        to_år_siden = datetime.now() - relativedelta(months=24)

        findes_opgave = False

        for opgave in opgaver:
            titel = opgave.get("title") or ""
            if opgave.get("createdByName") != "Odense RPA":
                continue
            if not titel.startswith(OPGAVE_TITEL_PRÆFIKSER) or not titel.endswith("Odense RPA"):
                continue

            status = opgave.get("stateName")
            if status in ("Planlagt", "I gang"):
                findes_opgave = True
                break
            if status == "Gennemført" and datetime.fromisoformat(opgave["deadline"]).replace(tzinfo=None) >= to_år_siden:
                findes_opgave = True
                break

        if not findes_opgave:
            forfaldsdato = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + relativedelta(months=1)
            opgavenavn = f"Afhold dedikeret vejledningssamtale om repatirering - Statsborgerskab: {borger.oprindelsesland} - Odense RPA"
            beskrivelse = "Denne borger er i målgruppe for indkaldelse til møde om repatriering"
            self.momentum.opgaver.opret_opgave(momentum_borger, [sagsbehandler], forfaldsdato, opgavenavn, beskrivelse)

        try:
            brev = self.momentum.borgere.opret_brev(
                momentum_borger, 
                sagsbehandler, 
                titel="Dedikeret vejledningsamtale",
                brevskabelonsnavn="Repatriering - Information om rettigheder - ODK.O.013")
        except Exception as e:
            raise WorkItemError(f"Fejl i oprettelse af brevet: {e}")

        try:
            self.momentum.borgere.send_brev(
                momentum_borger, 
                str(brev), 
                "Dedikeret vejledningssamtale om repatriering - diversesag")
        except Exception as e:
            raise WorkItemError(f"Fejl i send brev, men brevet er oprettet: {e}")
        
        agenda = self.momentum.borgere.tilføj_agenda_til_borger(momentum_borger, "Dedikeret vejledningssamtale – repatriering")

    def håndter_borger_ikke_i_målgruppe(self, momentum_borger: dict):
        målgrupper = self.momentum.borgere.hent_målgrupper(momentum_borger)

        if not målgrupper:
            return

        for målgruppe in målgrupper:
            
            målgruppens_opretter = self.hent_aktør(målgruppe.get("createdById"))
            if (
                målgruppe.get("title") == "IY - Ingen ydelse"
                and not målgruppe.get("closingReasonCode")
                and målgruppens_opretter.get("displayName") == "Odense RPA"
            ):
                self.momentum.borgere.luk_målgruppe(
                    momentum_borger,
                    målgruppe,
                    LUKKEKODE_IY,
                    "Borger er ikke i målgruppe for dedikeret vejledningssamtale",
                    date.today(),
                )

        supplerende_sager = self.momentum.borgere.hent_supplerendesager(momentum_borger)

        for sag in supplerende_sager or []:
            if (
                (sag.get("title") or "").lower() == "dedikeret vejledningssamtale om repatriering - diversesag"
                and not sag.get("endDate")
            ):
                self.momentum.borgere.luk_supplerende_sag(
                    momentum_borger,
                    sag,
                    "Borger er ikke i målgruppe for dedikeret vejledningssamtale",
                    date.today(),
                )

        opgaver = self.momentum.opgaver.hent_opgaver(momentum_borger)

        for opgave in opgaver or []:
            # Første stadie
            if opgave.get("createdByName") != "Odense RPA":
                continue
            if opgave.get("stateName") not in ("Planlagt", "I gang"):
                continue

            # Andet stadie
            titel = opgave.get("title") or ""
            er_samtale_opgave = titel.startswith(OPGAVE_LUK_PRÆFIKSER) and titel.endswith("Odense RPA")
            if not (er_samtale_opgave or titel == BREV_OPGAVE_TITEL):
                continue

            self.momentum.opgaver.opdater_opgave_status(
                opgave["id"],
                self.momentum.opgaver.Status.aflyst,
            )

    def hent_aktør(self, id: str) -> dict:
        aktør = self.momentum.momentum_client.get(f"/actors/{id}/details")

        if aktør is None:
            raise ValueError("Aktør ikke fundet")

        return aktør.json()