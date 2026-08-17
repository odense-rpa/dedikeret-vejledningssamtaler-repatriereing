import pymssql

from odk_tools.tracking import Tracker

class DWHService:
    def __init__(
            self,
            tracker: Tracker,
            username: str,
            password: str,
            server: str,
            database: str
            ):
        self.tracker = tracker
        self.username = username
        self.password = password
        self.server = server
        self.database = database
        self._connection = None

    def __enter__(self):
        if not self._connection:
            self._connection = pymssql.connect(
                server=self.server,
                user=self.username,
                password=self.password,
                database=self.database,
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._connection:
            self._connection.close()

    def close(self):
        if self._connection:
            self._connection.close()

    def hent_borgere(self, startdato: str):
        query = """
        SELECT
            [Cpr]
            ,[Adresseringsnavn] AS Navn
            ,[Standardadresse] AS Adresse
            ,[Postnr]
            ,[Postdistrikt]
            ,[Land_statsborger] AS Land
            ,[Alder_aar] AS Alder
            ,DATEADD(hour, 2, CAST([Dato_ophold_start] AS DATETIME)) AS Opholdsstartdato
            ,DATEADD(hour, 2, CAST([Dato_ophold_slut] AS DATETIME)) AS Opholdsslutdato
            ,[Uddannelse]
        FROM [RPA_Dataudveksling_DWH].[dbo].[udenlandske_Borgere_18plus]
        WHERE [Dato_ophold_start] < %s 
        AND Land_statsborger NOT IN (
            'Azorerne',
            'Balearerne',
            'Belgien',
            'Bulgarien',
            'Ceuta',
            'Cypern',
            'Danmark',
            'Estland',
            'Finland',
            'Frankrig',
            'Grækenland',
            'Guadeloupe',
            'Guyana',
            'Holland',
            'Nederlandene',
            'Irland',
            'Island',
            'Italien',
            'Kroatien',
            'Letland',
            'Liechtenstein',
            'Litauen',
            'Luxembourg',
            'Madeira',
            'Malta',
            'Martinique',
            'Norge',
            'Polen',
            'Portugal',
            'Reunion',
            'Rumænien',
            'Slovakiet',
            'Slovenien',
            'Spanien',
            'Sverige',
            'Tjekkiet',
            'Tyskland',
            'Ungarn',
            'Østrig',
            'Ålandsøerne',
            'Ukraine'
        )
        """
        
        cursor = self._connection.cursor(as_dict=True)
        cursor.execute(query, (startdato,))
        results = cursor.fetchall()
        cursor.close()
        
        return results

