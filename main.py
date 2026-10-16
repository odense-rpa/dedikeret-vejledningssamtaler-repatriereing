import asyncio
import logging
import os
import sys
from datetime import date
from dateutil.relativedelta import relativedelta

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential, WorkItemStatus
from momentum_client.manager import MomentumClientManager
from proces.momentum_service import MomentumService
from proces.datafordeler_service import DatafordelerService
from odk_skat import EIndkomstKlient, EIndkomstKonfiguration
from datafordeler import Datafordeler
from proces.dwh_service import DWHService
from proces.models import Borger
from proces.skat_service import SkatService
from odk_tools.tracking import Tracker

momentum: MomentumClientManager
tracker: Tracker
datafordeler: Datafordeler
fordeler_service: DatafordelerService
indkomst_klient: EIndkomstKlient
konfiguration: EIndkomstKonfiguration
skat_service: SkatService
momentum_service: MomentumService

procesnavn = "Dedikeret vejledningssamtaler - Repatriering"


async def populate_queue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)
    
    dwh_borgere = None

    with dwh_service:
        logger.info("Hent DWH borgere")
        startdato = (date.today() - relativedelta(months=60)).strftime("%Y-%m-%d")
        dwh_borgere = dwh_service.hent_borgere(startdato)

    if dwh_borgere is None:
        raise ValueError("Failed to retrieve borgere from DWH")

    logger.info("Henter borgere fra Momentum")
    momentum_borgere = momentum_service.find_borgere()

    if momentum_borgere is None:
        raise ValueError("Fejl kunne ikke hente momentum borgere")
    
    # Process DWH borgere
    for dwh_borger in dwh_borgere:
        dwh_cpr = dwh_borger["Cpr"]  # type: ignore
        
        findes_i_momentum = dwh_cpr in momentum_borgere
        if findes_i_momentum:
            momentum_borgere.pop(dwh_cpr)  # Remove - O(1)
        
        borger = Borger(
            cpr=dwh_cpr,
            navn=dwh_borger["Navn"],  # type: ignore
            oprindelsesland=dwh_borger["Land"],  # type: ignore
            findes_i_dwh=True,
            findes_i_momentum=findes_i_momentum
        )
            
        workqueue.add_item(reference=dwh_cpr, data=borger.model_dump())
        logger.info(f"Added borger from DWH: {dwh_cpr}, findes i momentum: {findes_i_momentum}")
    
    # Process remaining Momentum borgere (not in DWH)
    for momentum_borger in momentum_borgere.values():
        momentum_cpr = momentum_borger['cpr']
        
        borger = Borger(
            cpr=momentum_cpr,
            navn=momentum_borger.get('displayName', ''),
            oprindelsesland="Ukendt",
            findes_i_dwh=False,
            findes_i_momentum=True
        )
        
        workqueue.add_item(reference=momentum_cpr,data=borger.model_dump())
        logger.info(f"Added borger from Momentum only: {momentum_cpr}")

async def process_workqueue(workqueue: Workqueue, sagsbehandler_initialer: str):
    logger = logging.getLogger(__name__)

    sagsbehandler = momentum.momentum_client.søg(sagsbehandler_initialer, "Caseworker")
    if sagsbehandler is not None and len(sagsbehandler) == 1:
        sagsbehandler = sagsbehandler[0]

    # sagsbehandler_rpa = momentum.momentum_client.søg("Odense RPA", "Caseworker")
    # if sagsbehandler_rpa is not None and len(sagsbehandler_rpa) == 1:
    #     sagsbehandler_rpa = sagsbehandler_rpa[0]

    for item in workqueue:
        with item:
            borger = Borger.model_validate(item.data)  # Item data deserialized from json as dict            
            try:                
                i_målgruppe = skat_service.kontroller_om_borger_i_målgruppe(borger.cpr)
                
                if not i_målgruppe and not borger.findes_i_momentum:
                    logger.info("Borger ej i målgruppe eller i momentum, stopper behandling")
                    tracker.track_partial_task(procesnavn)
                    continue

                momentum_borger = momentum.borgere.hent_borger(borger.cpr)

                if momentum_borger is None:
                    raise WorkItemError("Kunne ikke hente momentum borger")
                
                if i_målgruppe:
                    logger.info("Borger i målgruppe")
                    momentum_service.håndter_borger_i_målgruppe(momentum_borger, sagsbehandler, borger)
                else:
                    logger.info("Boger ikke længere i målgruppe")
                    momentum_service.håndter_borger_ikke_i_målgruppe(momentum_borger)

            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {borger}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":
    ats = AutomationServer.from_environment()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(console_handler)

    workqueue = ats.workqueue()

    # Initialize external systems for automation here..
    tracker_credentials = Credential.get_credential("Odense SQL Server")
    skat_credential = Credential.get_credential("Skat - Udrejsebreve") 

    tracker = Tracker(
        username=tracker_credentials.username,
        password=tracker_credentials.password
    )

    dwh_service = DWHService(
        tracker,
        tracker_credentials.username,
        password=tracker_credentials.password,
        server=tracker_credentials.data["server"],
        database=tracker_credentials.data["database"]
    )
    
    certifikat_sti = os.getenv("CERTIFIKATER", "/certifikater")
    datafordeler = Datafordeler(
        certifikat_sti=os.path.join(certifikat_sti, "datafordeler.crt"),
        certifikat_nøglefil=os.path.join(certifikat_sti, "datafordeler.key"),
    )
    
    momentum_credential = Credential.get_credential("Momentum - produktion")
    momentum = MomentumClientManager(
        base_url=momentum_credential.data["base_url"],
        client_id=momentum_credential.username,
        client_secret=momentum_credential.password,
        api_key=momentum_credential.data["api_key"],
        resource=momentum_credential.data["resource"],
    )


    momentum_service = MomentumService(
        momentum,
        tracker,
        procesnavn
    )
    
    fordeler_service = DatafordelerService(
        datafordeler
    )
    
    konfiguration = EIndkomstKonfiguration(
        se_nummer=skat_credential.data["se_nummer"],
        abonnement_type_kode=skat_credential.data["abonnement_type_kode"],
        abonnent_type_kode=skat_credential.data["abonnent_type_kode"],
        adgang_formaal_type_kode=skat_credential.data["adgang_formaal_type_kode"],
        noegle_adgangskode=skat_credential.password,
        noegle_sti=os.path.join(certifikat_sti, "skat-prod-noegle.pem"),
        certifikat_sti=os.path.join(certifikat_sti, "skat-prod-certifikat.pem")
    )
    
    indkomst_klient = EIndkomstKlient(
        konfiguration, miljoe="prod"
    )
    
    skat_service = SkatService(
        indkomst_klient
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue))
        exit(0)

    if "--sagsbehandler" in sys.argv:
        sagsbehandler_initialer = sys.argv[sys.argv.index("--sagsbehandler") + 1]
    else:
        sagsbehandler_initialer = os.environ["SAGSBEHANDLER"]
    
    # Process workqueue
    asyncio.run(process_workqueue(workqueue, sagsbehandler_initialer))
