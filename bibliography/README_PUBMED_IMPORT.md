# PubMed Bibliography Importer

Automatisch publicaties importeren vanuit PubMed voor alle groepsleden.

## Overzicht

Het `pubmed_importer.py` script haalt automatisch publicaties op uit PubMed voor alle leden van de groep en voegt ze toe aan het `umcg-anes.bib` bestand. Het script:

- Leest alle member informatie uit `content/pages/members/*.md` bestanden
- Zoekt publicaties in PubMed via ORCID IDs (meest betrouwbaar) of auteursnamen
- Converteert PubMed data naar BibTeX formaat
- Detecteert duplicaten (via PMID) en voorkomt dubbele entries
- **Update bestaande entries** als er wijzigingen zijn in PubMed (nieuwe functionaliteit!)
- Voegt nieuwe publicaties toe aan `content/umcg-anes.bib`

## Vereisten

- Python 3.6 of hoger
- Internetverbinding
- PubMed API toegang:
  - **Email adres** (vereist door NCBI)
  - **API key** (optioneel maar aanbevolen voor snellere queries)

## PubMed API Key verkrijgen

Voor snellere queries (10 requests/seconde i.p.v. 3):

1. Ga naar https://www.ncbi.nlm.nih.gov/account/
2. Log in of maak een NCBI account aan
3. Ga naar "Settings" → "API Key Management"
4. Klik op "Create an API Key"
5. Kopieer de API key

## Gebruik

### Test eerst de API verbinding

Voordat je begint, test of PubMed API bereikbaar is:

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw.email@radboudumc.nl \
  --api-key JOUW_API_KEY \
  --test
```

Als dit werkt zie je: `✓ PubMed API is accessible!`

### Basis gebruik met dry-run (aanbevolen voor eerste keer)

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw.email@radboudumc.nl \
  --api-key JOUW_API_KEY \
  --dry-run
```

Dit toont wat er zou worden toegevoegd zonder het bestand te wijzigen.

### Alleen actieve leden

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw.email@radboudumc.nl \
  --api-key JOUW_API_KEY \
  --active-only
```

### Publicaties vanaf een bepaald jaar

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw.email@radboudumc.nl \
  --api-key JOUW_API_KEY \
  --since 2024
```

### Voor één specifiek lid

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw.email@radboudumc.nl \
  --api-key JOUW_API_KEY \
  --member "Bram van Ginneken" \
  --dry-run
```

### Aantal resultaten beperken

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw.email@radboudumc.nl \
  --api-key JOUW_API_KEY \
  --max-results 50 \
  --since 2023
```

## Opties

| Optie | Beschrijving |
|-------|-------------|
| `--dry-run` | Toon wat toegevoegd zou worden zonder bestand te wijzigen |
| `--member NAME` | Alleen importeren voor specifiek lid (bijv. "Bram van Ginneken") |
| `--since YEAR` | Alleen publicaties vanaf jaar YEAR (bijv. 2020) |
| `--email EMAIL` | Email voor PubMed API (vereist door NCBI) |
| `--api-key KEY` | PubMed API key voor snellere queries (10 req/sec) |
| `--max-results N` | Maximum resultaten per auteur (default: 100) |
| `--active-only` | Alleen actieve leden verwerken |
| `--rate-limit N` | Seconden tussen API requests (default: 1.0) |

## Rate Limiting

Het script respecteert PubMed API limieten met conservatieve defaults:

- **Met API key**: 1.0 seconde tussen requests (standaard)
- **Zonder API key**: 1.5 seconden tussen requests (standaard)
- **PubMed maximum**: 10 req/sec met API key, 3 req/sec zonder

### Waarom conservatief?

Met 356 groepsleden en meerdere API calls per lid is het belangrijk om:
1. Niet tegen API limieten aan te lopen
2. Een "good citizen" te zijn voor NCBI servers
3. Te voorkomen dat je account geblokkeerd wordt
4. Stabiele imports te garanderen

### Custom rate limiting

Voor snellere imports (op eigen risico):

```bash
# Sneller: 0.5 seconden tussen requests (2 req/sec)
python3 bibliography/pubmed_importer.py \
  --rate-limit 0.5 \
  --email jouw@email.nl \
  --api-key JOUW_KEY
```

### Geschatte runtime

Voor alle 356 members:
- Met 1 sec rate limit: ~10-20 minuten (2 calls per member = 712 sec)
- Met 0.5 sec rate limit: ~5-10 minuten
- Afhankelijk van resultaten per lid

**Tip**: Gebruik `--active-only` om tijd te besparen bij reguliere updates.

## Workflow

### 1. Test eerst met dry-run

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw@email.nl \
  --api-key JOUW_KEY \
  --since 2024 \
  --dry-run
```

Review de output om te zien welke publicaties gevonden zijn.

### 2. Voer import uit

Verwijder `--dry-run` om daadwerkelijk te importeren:

```bash
python3 bibliography/pubmed_importer.py \
  --email jouw@email.nl \
  --api-key JOUW_KEY \
  --since 2024
```

### 3. Parse de bibliografie

Na het importeren, parse de nieuwe entries:

```bash
./parse_publications.sh
```

Dit genereert de JSON bestanden en markdown pagina's.

### 4. Review en commit

```bash
git diff content/umcg-anes.bib
git add content/umcg-anes.bib content/*.json
git commit -m "Add new publications from PubMed (2024)"
git push
```

## Member bestand vereisten

Voor beste resultaten, zorg dat member bestanden bevatten:

```yaml
name: Volledige Naam
orcid: https://orcid.org/0000-0000-0000-0000
pub_name: Publicatie Naam  # optioneel, als afwijkend van name
active: yes
```

### Zoek strategie

Het script zoekt publicaties in deze volgorde:

1. **Via ORCID** (als beschikbaar) - meest betrouwbaar
2. **Via naam** - gebruikt `pub_name` of valt terug op `name`

ORCID is veel betrouwbaarder dan naam matching, dus het is aan te raden om ORCID toe te voegen aan member bestanden.

## Duplicate detectie en Updates

Het script detecteert duplicaten op basis van PMID (PubMed ID):

- **Nieuwe publicaties**: PMIDs die nog niet in `umcg-anes.bib` staan worden toegevoegd
- **Bestaande publicaties**: PMIDs die al bestaan worden gecontroleerd op updates
  - Het script haalt de laatste versie op uit PubMed
  - Vergelijkt key fields: titel, auteurs, journal, jaar, volume, pages, DOI, abstract
  - Als er significante wijzigingen zijn, wordt de entry ge-update
  - De BibTeX key blijft ongewijzigd om links te behouden

Dit betekent dat als een publicatie in PubMed wordt gecorrigeerd (bijv. auteur toegevoegd, abstract toegevoegd, DOI gewijzigd), deze wijzigingen automatisch worden doorgevoerd in jullie bibliografie.

## BibTeX formaat

Geïmporteerde entries krijgen:

- Unieke BibTeX keys (bijv. `Smith24a`, `Smith24b`)
- Alle beschikbare metadata: auteurs, titel, journal, jaar, volume, issue, pages
- PMID en DOI links
- Abstract (indien beschikbaar)
- `optnote = {DIAG, RADIOLOGY}` voor categorisatie

## Tips

### Regelmatige updates

Voor regelmatige updates, gebruik `--since` om alleen recente publicaties te importeren:

```bash
# Maandelijkse update (alleen actieve leden, sneller)
python3 bibliography/pubmed_importer.py \
  --email jouw@email.nl \
  --api-key JOUW_KEY \
  --since 2024 \
  --active-only

# Dit duurt ongeveer 5-10 minuten voor ~100 actieve leden
```

**Let op**: Bij regelmatige updates zal het script ook bestaande publicaties uit de opgegeven periode controleren op updates. Als een publicatie in PubMed is gewijzigd (bijv. een erratum, toegevoegde metadata), wordt deze automatisch bijgewerkt in `umcg-anes.bib`.

### Alleen updates controleren

Als je alleen wilt controleren of bestaande publicaties zijn bijgewerkt in PubMed, zonder nieuwe toe te voegen, gebruik dan een heel oud jaar:

```bash
# Check alle bestaande publicaties op updates
python3 bibliography/pubmed_importer.py \
  --email jouw@email.nl \
  --api-key JOUW_KEY \
  --since 1990 \
  --dry-run

# Voer daadwerkelijk updates door
python3 bibliography/pubmed_importer.py \
  --email jouw@email.nl \
  --api-key JOUW_KEY \
  --since 1990
```

### Automatisering met GitHub Actions

Er is een GitHub Actions workflow beschikbaar die automatisch wekelijks publicaties importeert:

- **Locatie**: `.github/workflows/update-publications.yml`
- **Schedule**: Elke maandag om 02:00 UTC
- **Handmatig**: Via Actions tab in GitHub
- **Documentatie**: `.github/workflows/README.md`

De workflow gebruikt repository secrets:
- `PUBMED_EMAIL`: Je PubMed email
- `PUBMED_API`: Je PubMed API key

**Handmatig triggeren:**
1. Ga naar Actions tab in GitHub
2. Selecteer "Update Publications from PubMed"
3. Klik "Run workflow"
4. Kies opties en start

### Automatisering met cron (lokaal)

Voor lokale automatisering kun je een cron job instellen:

```bash
# crontab -e
# Run eerste dag van de maand om 2 AM
0 2 1 * * cd /path/to/umcg-anesthesie && python3 bibliography/pubmed_importer.py --email your@email.nl --api-key YOUR_KEY --since 2024 --active-only
```

### Grote imports

Voor het importeren van veel publicaties (bijv. eerste keer):

1. Begin met één lid: `--member "Naam"`
2. Test met `--dry-run`
3. Gebruik `--max-results` om te beperken
4. Importeer in batches per jaar: `--since 2023`, `--since 2022`, etc.

## Troubleshooting

### "HTTP Error 403: Forbidden"

- Zorg dat je een `--email` parameter meegeeft
- Overweeg een API key aan te vragen voor betere toegang

### Geen publicaties gevonden voor bepaald lid

- Check of ORCID correct is in member bestand
- Check of `pub_name` correct gespeld is
- Test handmatig in PubMed: https://pubmed.ncbi.nlm.nih.gov/

### Te veel duplicaten

Als een lid onder meerdere naamvarianten publiceert:

1. Voeg correcte ORCID toe aan member bestand
2. Of gebruik specifieke `pub_name` in member bestand

### Rate limiting

**PubMed limieten:**
- Met API key: max 10 requests/seconde
- Zonder API key: max 3 requests/seconde

**Script defaults (conservatief):**
- Met API key: 1 request/seconde (10x veiliger dan maximum)
- Zonder API key: 1 request per 1.5 seconden

Dit voorkomt problemen bij batch imports met veel leden. Je kunt dit aanpassen met `--rate-limit` als je weet wat je doet.

## Geavanceerd gebruik

### Configuratie bestand

Je kunt een `.env` bestand maken in de root:

```bash
# .env
PUBMED_EMAIL=jouw@email.nl
PUBMED_API_KEY=jouw_api_key
```

Dan kun je het script aanroepen zonder parameters:

```python
# Voeg toe aan pubmed_importer.py om .env te lezen
from dotenv import load_dotenv
load_dotenv()
```

### Custom filtering

Het script kan aangepast worden om:

- Alleen bepaalde publication types te importeren
- Affiliatie filtering (alleen Radboudumc publicaties)
- Keyword filtering
- Citation threshold filtering

## Contact

Voor vragen of problemen, neem contact op met de repository maintainers.

## Zie ook

- PubMed E-utilities documentatie: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- ORCID: https://orcid.org/
- BibTeX format: http://www.bibtex.org/Format/
