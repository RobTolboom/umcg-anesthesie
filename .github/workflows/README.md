# GitHub Actions Workflows

## Update Publications from PubMed

**Bestand**: `update-publications.yml`

### Wat doet deze workflow?

Automatisch publicaties importeren vanuit PubMed en toevoegen aan de bibliografie.

### Wanneer draait het?

1. **Automatisch**: Elke maandag om 02:00 UTC (03:00 CET / 04:00 CEST)
2. **Handmatig**: Via de Actions tab in GitHub

### Handmatig triggeren

1. Ga naar **Actions** tab in GitHub
2. Klik op **Update Publications from PubMed** workflow
3. Klik op **Run workflow**
4. Kies opties:
   - **Since year**: Vanaf welk jaar (default: huidig jaar)
   - **Active only**: Alleen actieve leden (default: ja)
   - **Dry run**: Test zonder te committen (default: nee)
5. Klik op **Run workflow**

### Configuratie

De workflow gebruikt GitHub Secrets:
- `PUBMED_EMAIL`: Email voor PubMed API
- `PUBMED_API`: PubMed API key

Deze zijn geconfigureerd in: **Settings → Secrets and variables → Actions**

### Wat doet de workflow precies?

```
1. Checkout code
2. Setup Python 3.11
3. Run pubmed_importer.py
   - Met secrets voor email/API key
   - Voor actieve leden
   - Vanaf huidig jaar
   - Met 1 sec rate limiting
4. Parse bibliografie (parse_publications.sh)
5. Check voor wijzigingen
6. Commit en push als er wijzigingen zijn
```

### Output

Na elke run zie je in de Actions tab:
- Hoeveel publicaties gevonden
- Hoeveel nieuwe toegevoegd
- Of er een commit gemaakt is
- Details in de logs

### Schedule aanpassen

Om de timing te wijzigen, pas de cron in `update-publications.yml` aan:

```yaml
schedule:
  - cron: '0 2 * * 1'  # Maandag 02:00 UTC
```

Voorbeelden:
- `'0 2 * * 1'` - Elke maandag 02:00 UTC
- `'0 2 1 * *'` - Eerste dag van de maand 02:00 UTC
- `'0 2 * * 0'` - Elke zondag 02:00 UTC

### Rate Limiting

De workflow gebruikt `--rate-limit 1.0` (1 request per seconde) voor veilige batch processing. Dit is conservatief genoeg voor alle actieve leden zonder API limieten te raken.

### Troubleshooting

**Workflow draait niet automatisch:**
- Check of Actions enabled is in repository settings
- Check of de branch de default branch is

**API errors:**
- Verifieer dat secrets correct zijn ingesteld
- Check PubMed API status: https://www.ncbi.nlm.nih.gov/

**Geen nieuwe publicaties:**
- Dit is normaal als er geen nieuwe publicaties zijn sinds de laatste run
- Check de logs voor details

**Commit fails:**
- Check repository permissions
- Workflow heeft `contents: write` permission nodig

### Monitoring

Best practices:
1. Check eerste paar runs handmatig
2. Review commits gemaakt door github-actions[bot]
3. Monitor voor fouten in Actions tab
4. Bij problemen: schakel schedule uit en debug met manual runs

### Kosten

GitHub Actions is gratis voor public repositories. Voor private repositories:
- 2000 minuten per maand gratis
- Deze workflow gebruikt ~5-10 minuten per run
- Wekelijks = ~40 minuten per maand = ruim binnen free tier
