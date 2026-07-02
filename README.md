# Dedikeret vejledningssamtale – Repatriering

Identificerer borgere i målgruppen for repatrieringsvejledning ved at sammenholde data fra DWH og Momentum og placerer dem i en arbejdskø til videre sagsbehandling.

## Hvad gør robotten?

1. Henter udenlandske borgere (ikke-EU/EØS, 18+) fra DWH med opholdsstartdato mere end 60 måneder siden — EU/EØS-lande samt Ukraine er filtreret fra.
2. Henter borgere fra Momentum med aktive supplerende repatrierings-sager (supplementalCaseTypeId `312b9bb4-686d-ec11-9898-001dd8b71e89`).
3. Sammenholder de to lister og markerer, om borgeren optræder i DWH, Momentum eller begge.
4. Tilføjer borgere til arbejdskøen med CPR, navn, oprindelsesland og statusflags.
5. Behandling af arbejdskøen er endnu ikke implementeret og er under aktiv udvikling.

## Forudsætninger

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) til pakkehåndtering
- Adgang til **Automation Server** (arbejdskø)
- Adgang til **DWH** (Odense SQL Server – RPA_Dataudveksling_DWH)
- Adgang til **Momentum** (produktion)

## Installation

```sh
uv sync
```

## Konfiguration

Credentials registreres i Automation Server:

- `Odense SQL Server`
- `Momentum - produktion`

Valgfri miljøvariabel ud over standard ATS-variable:

| Variabel | Beskrivelse |
|---|---|
| `ATS_WORKQUEUE_OVERRIDE` | Overstyr arbejdskø-ID (bruges sjældent ved test) |

## Kørsel

```sh
uv run python main.py --queue   # Fyld arbejdskøen med borgere fra DWH og Momentum
uv run python main.py           # Behandl arbejdskøen (endnu ikke implementeret)
```

## Afhængigheder

| Pakke | Formål |
|---|---|
| `automation-server-client` | Klient til RPA Automation Server – arbejdskøer, credentials og workitems |
| `momentum-client` | Klient til Momentum sagsbehandlingssystem – hentning af borgere og sager |
| `odk-tools` | Odense Kommune-værktøjer inkl. Tracker til ODK SQL-sporing |
| `pymssql` | Forbindelse til Microsoft SQL Server (DWH) |
| `python-dateutil` | Dato-beregninger, herunder relativedelta til beregning af 60-måneders grænsen |

## GDPR og sikkerhed

Processen behandler følgende personoplysninger for udenlandske borgere (ikke-EU/EØS) over 18 år bosiddende i Odense Kommune: CPR-numre, navne, adresser, postnr., postdistrikt, statsborgerskabsland, alder, opholdsstartdato, opholdsslutdato og uddannelse.

Data hentes fra DWH og Momentum, behandles udelukkende i arbejdskøen i Automation Server og gemmes ikke lokalt. Adgang til arbejdskøen styres via Automation Server-rettigheder.
