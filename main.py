import asyncio
import logging
import sys
import pydoc
from datetime import date
from dateutil.relativedelta import relativedelta

from automation_server_client import AutomationServer, Workqueue, WorkItemError, Credential, WorkItemStatus
from momentum_client.manager import MomentumClientManager
from proces.momentum_service import MomentumService
from proces.dwh_service import DWHService
from proces.models import Borger
from odk_tools.tracking import Tracker

momentum: MomentumClientManager
tracker: Tracker


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




async def process_workqueue(workqueue: Workqueue):
    logger = logging.getLogger(__name__)

    logger.info("Hello from process workqueue!")

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict
 
            try:
                # Process the item here
                pass
            except WorkItemError as e:
                # A WorkItemError represents a soft error that indicates the item should be passed to manual processing or a business logic fault
                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    # Initialize external systems for automation here..
    tracker_credentials = Credential.get_credential("Odense SQL Server")

    tracker = Tracker(
        username=tracker_credentials.username,
        password=tracker_credentials.password
    )

    dwh_service = DWHService(
        tracker,
        tracker_credentials.username,
        tracker_credentials.password
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
        tracker
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
