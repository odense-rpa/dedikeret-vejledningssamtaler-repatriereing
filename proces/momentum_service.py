from momentum_client.manager import MomentumClientManager
from odk_tools.tracking import Tracker


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