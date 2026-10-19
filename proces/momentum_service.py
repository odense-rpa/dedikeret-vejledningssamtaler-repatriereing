from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from proces.models import Borger
from automation_server_client import WorkItemError
from odk_tools.tracking import Tracker
import logging

logger = logging.getLogger(__name__)

OPGAVE_TITEL_PRÆFIKSER = (
    "Afhold dedikeret vejledningssamtale om repatirering - Statsborgerskab",  # TODO: Fjern stavefejl
    "Afhold dedikeret vejledningssamtale om repatriering - Statsborgerskab",
)

OPGAVE_LUK_PRÆFIKSER = (
    "Afhold dedikeret vejledningssamtale om repatirering",  # TODO: Fjern stavefejl
    "Afhold dedikeret vejledningssamtale om repatriering",
)
BREV_OPGAVE_TITEL = "Brev sendt omkring repatriering - robot"

LUKKEKODE_NAVN = "Ej i målgruppe for repatriering"

class MomentumService:
    def __init__(
            self,
            momentum: MomentumClientManager,
            tracker: Tracker,
            procesnavn: str
            ):
        
        self.momentum = momentum
        self.tracker = tracker
        self.procesnavn = procesnavn
        self.LUKKEKODE_IY = self._find_lukkekode(LUKKEKODE_NAVN)

    def _find_lukkekode(self, navn: str) -> str:
        gruppe = self.momentum.taksonomier.find_taksonomi_gruppe("CLOSING_CAUSE_TYPE")
        if gruppe is None:
            raise ValueError("Taksonomigruppen CLOSING_CAUSE_TYPE blev ikke fundet")

        koder = [t["code"] for t in gruppe.get("taxons", []) if t.get("name") == navn]

        if len(koder) != 1:
            raise ValueError(f"Forventede præcis én lukkekode med navnet '{navn}', fandt {len(koder)}")

        return koder[0]

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
    
    def håndter_borger_i_målgruppe(self, momentum_borger: dict, sagsbehandler, borger: Borger):


        supplerende_sager = self.momentum.borgere.hent_supplerendesager(momentum_borger)

        har_repatrierings_sag = False
        logger.info("Kontrollere supplerende sager")
        if supplerende_sager is not None:
            for sag in supplerende_sager:
                # Denne sag tjekkes der for og hvis den findes på borger skal behandling stoppes.
                if sag.get("name") == "Repatriering - diversesag" and sag.get("endDate") is None:
                    logger.info("Specifik sag fundet, stopper behandling")
                    return None
                # Tjekker om denne sag findes, ellers skal den oprettes.
                if sag.get("name") == "Dedikeret vejledningssamtale om repatriering - diversesag" and sag.get("endDate") is None:
                    logger.info("Borger har allerede repatrieringssag")
                    har_repatrierings_sag = True

        målgrupper = self.momentum.borgere.hent_målgrupper(momentum_borger)

        if målgrupper is not None:
            alle_lukket = all(mg.get("closingReasonCode") is not None for mg in målgrupper)
            if alle_lukket:
                logger.info("Borger har ingen målgruppe, opretter 'ingen ydelse' målgruppe")
                self.momentum.borgere.opret_målgruppe(momentum_borger, "NB", date.today(), sagsbehandler)
        
        if not har_repatrierings_sag:
            logger.info("Borger har ikke repatrieringssag, opretter sagen")
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
                logger.info("Borger allerede igangværende opgave, og skal derfor ikke have brev")
                break
            if status == "Gennemført" and datetime.fromisoformat(opgave["deadline"]).replace(tzinfo=None) >= to_år_siden:
                findes_opgave = True
                logger.info("Borger har en opgave der er gennemført for mindre end 2 år siden, og skal derfor ikke have brev")
                break

        if not findes_opgave:
            forfaldsdato = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + relativedelta(months=1)
            opgavenavn = f"Afhold dedikeret vejledningssamtale om repatirering - Statsborgerskab: {borger.oprindelsesland} - Odense RPA"
            beskrivelse = "Denne borger er i målgruppe for indkaldelse til møde om repatriering"
            logger.info("Borger har ikke repatrieringsopgave, der er oprettes en")
            self.momentum.opgaver.opret_opgave(momentum_borger, [sagsbehandler], forfaldsdato, opgavenavn, beskrivelse)

            try:
                logger.info("Forsøger at oprette brev: 'Repatriering - Information om rettigheder - ODK.O.013'")
                brev = self.momentum.borgere.opret_brev(
                    momentum_borger, 
                    sagsbehandler, 
                    titel="Dedikeret vejledningsamtale",
                    brevskabelonsnavn="Repatriering - Information om rettigheder - ODK.O.013")
            except Exception as e:
                raise WorkItemError(f"Fejl i oprettelse af brevet: {e}")

            try:
                logger.info("Forsøger at sende brevet")
                self.momentum.borgere.send_brev(
                    momentum_borger, 
                    str(brev), 
                    "Dedikeret vejledningssamtale om repatriering - diversesag")
            except Exception as e:
                raise WorkItemError(f"Fejl i send brev, men brevet er oprettet: {e}")

            logger.info("Brev oprettet og sendt")

            logger.info("Tilføjer agenda til borger")            
            self.momentum.borgere.tilføj_agenda_til_borger(momentum_borger, "Dedikeret vejledningssamtale – repatriering")
            self.tracker.track_task(self.procesnavn)
        else:
            self.momentum.borgere.tilføj_agenda_til_borger(momentum_borger, "Dedikeret vejledningssamtale – repatriering")
            self.tracker.track_partial_task(self.procesnavn)

    def håndter_borger_ikke_i_målgruppe(self, momentum_borger: dict):
        logger.info("Kontrollerer målgrupper")
        målgrupper = self.momentum.borgere.hent_målgrupper(momentum_borger)

        if not målgrupper:
            logger.info("Borger har ingen målgrupper, intet at rydde op")
            return

        for målgruppe in målgrupper:
            
            målgruppens_opretter = self.hent_aktør(målgruppe.get("createdById"))
            if (
                målgruppe.get("title") == "IY - Ingen ydelse"
                and not målgruppe.get("closingReasonCode")
                and målgruppens_opretter.get("displayName") == "Odense RPA"
            ):
                logger.info("Borger har åben 'IY - Ingen ydelse' målgruppe oprettet af Odense RPA, lukker den")

                self.momentum.taksonomier.find_taksonomi_gruppe("CLOSING_CAUSE_TYPE")
                
                self.momentum.borgere.luk_målgruppe(
                    momentum_borger,
                    målgruppe,
                    self.LUKKEKODE_IY,
                    "Borger er ikke i målgruppe for dedikeret vejledningssamtale",
                    date.today(),
                )

        logger.info("Kontrollerer supplerende sager")
        supplerende_sager = self.momentum.borgere.hent_supplerendesager(momentum_borger)

        for sag in supplerende_sager or []:
            if (
                (sag.get("title") or "").lower() == "dedikeret vejledningssamtale om repatriering - diversesag"
                and not sag.get("endDate")
            ):
                logger.info("Borger har åben repatrieringssag, lukker den")
                self.momentum.borgere.luk_supplerende_sag(
                    momentum_borger,
                    sag,
                    "Borger er ikke i målgruppe for dedikeret vejledningssamtale",
                    date.today(),
                )

        logger.info("Kontrollerer opgaver")
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

            logger.info("Aflyser opgave: %s", titel)
            self.momentum.opgaver.opdater_opgave_status(
                opgave["id"],
                self.momentum.opgaver.Status.aflyst,
            )

        logger.info("Borger er ikke i målgruppe, oprydning færdig")
        self.tracker.track_task(self.procesnavn)

    def hent_aktør(self, id: str) -> dict:
        aktør = self.momentum.momentum_client.get(f"/actors/{id}/details")

        if aktør is None:
            raise ValueError("Aktør ikke fundet")

        return aktør.json()