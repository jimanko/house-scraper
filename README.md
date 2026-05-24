# house-scraper 🏠

Παρακολουθεί αυτόματα αγγελίες ακινήτων σε **spitogatos.gr** και **xe.gr** και σου στέλνει email κάθε φορά που εμφανίζονται νέες αγγελίες που ταιριάζουν με τα κριτήριά σου.

---

## Setup βήμα-βήμα

### 1. Fork / Clone

```bash
git clone https://github.com/YOUR_USERNAME/house-scraper.git
cd house-scraper
```

### 2. Επεξεργασία `config.yaml`

Άνοιξε το αρχείο `config.yaml` και ρύθμισε τις αναζητήσεις σου:

```yaml
searches:
  - name: "Spitogatos - Ενοικίαση Γαλάτσι"
    site: spitogatos
    url: "https://www.spitogatos.gr/enoikiasi-katoikies/galatsi"
    filters:
      max_price: 800    # μέγιστη τιμή σε €
      min_size: 60      # ελάχιστο εμβαδόν σε τ.μ.
```

**Πώς βρίσκεις το URL:**
1. Πήγαινε στο site (π.χ. spitogatos.gr ή xe.gr)
2. Κάνε αναζήτηση με τα φίλτρα που θέλεις (περιοχή, τύπος, τιμή κ.λπ.)
3. Αντέγραψε το URL από τη γραμμή διευθύνσεων του browser
4. Επικόλλησέ το στο `config.yaml`

Ορισε επίσης το email στο οποίο θέλεις να λαμβάνεις ειδοποιήσεις:
```yaml
email:
  to: "your@gmail.com"
```

### 3. Δημιουργία Gmail App Password

Το App Password επιτρέπει στο script να στέλνει email μέσω του Gmail σου χωρίς να χρησιμοποιεί τον κωδικό σου.

> **Προϋπόθεση:** Πρέπει να έχεις ενεργοποιημένο το **2-Step Verification** στο λογαριασμό σου.

1. Πήγαινε στη σελίδα: https://myaccount.google.com/apppasswords
2. Στο πεδίο "App name" γράψε `house-scraper`
3. Πάτα **Create**
4. Σημείωσε τον 16ψήφιο κωδικό που εμφανίζεται — **δεν φαίνεται ξανά**

### 4. Cookie για Spitogatos (απαιτείται)

Το spitogatos.gr χρησιμοποιεί σύστημα bot-protection που απαιτεί cookie από πραγματικό browser. Χωρίς αυτό το cookie, το spitogatos παραλείπεται αθόρυβα (το XE.gr συνεχίζει να δουλεύει κανονικά).

**Πώς το βρίσκεις:**
1. Άνοιξε το `https://www.spitogatos.gr/enoikiaseis-katoikies/galatsi` στο Chrome/Edge και περίμενε να φορτώσουν οι αγγελίες
2. Πάτα **F12** → tab **Application** → **Cookies** → `https://www.spitogatos.gr`
3. Βρες τη γραμμή με **Name** = `reese84` και αντέγραψε ολόκληρη την **Value**

> **Προσοχή:** Το cookie λήγει περίπου κάθε **ένα μήνα**. Όταν λήξει, θα εμφανίζεται μήνυμα `blocked by DataDome` στα logs και το spitogatos θα παραλείπεται. Απλά επανάλαβε αυτά τα βήματα και ενημέρωσε το secret.

### 5. Προσθήκη GitHub Secrets

Στο repo σου στο GitHub:

1. Πήγαινε **Settings → Secrets and variables → Actions**
2. Πάτα **New repository secret** και πρόσθεσε:

| Name | Value |
|------|-------|
| `GMAIL_USER` | το Gmail σου (π.χ. `yourname@gmail.com`) |
| `GMAIL_APP_PASSWORD` | ο 16ψήφιος κωδικός από το βήμα 4 Gmail |
| `SPITOGATOS_COOKIE` | `reese84=<η τιμή που αντέγραψες παραπάνω>` |

Εναλλακτικά με το GitHub CLI:
```bash
gh secret set GMAIL_USER
gh secret set GMAIL_APP_PASSWORD
gh secret set SPITOGATOS_COOKIE
```

### 6. Ενεργοποίηση Actions

1. Πήγαινε στο tab **Actions** του repo σου
2. Αν σου ζητηθεί, πάτα **"I understand my workflows, go ahead and enable them"**

### 7. Πρώτο τεστ

Τρέξε το workflow χειροκίνητα για να επαληθεύσεις ότι λειτουργεί:
1. Actions → **Scrape listings** → **Run workflow**
2. Παρακολούθησε τα logs σε πραγματικό χρόνο
3. Αν όλα πάνε καλά, θα λάβεις email με τις πρώτες αγγελίες (ή θα δεις "No new listings found" αν δεν υπάρχουν νέες)

---

## Ανανέωση Spitogatos cookie όταν λήξει

### Πότε χρειάζεται

Το cookie `reese84` λήγει περίπου **κάθε ένα μήνα**. Θα το καταλάβεις γιατί:
- Θα λάβεις **⚠️ alert email** από το scraper (αποστέλλεται 1 μέρα πριν τη λήξη και την ημέρα λήξης)
- Τα logs του Actions θα δείχνουν: `blocked by DataDome challenge`
- Τα spitogatos αποτελέσματα θα είναι πάντα 0

### Βήμα-βήμα ανανέωση

1. **Άνοιξε το spitogatos.gr στο Chrome/Edge** και κάνε login αν χρειαστεί.  
   Πήγαινε σε οποιαδήποτε σελίδα αναζήτησης, π.χ.:  
   `https://www.spitogatos.gr/enoikiaseis-katoikies/galatsi`  
   Περίμενε να φορτώσουν οι αγγελίες (σημαντικό — το cookie εκδίδεται μετά το JS challenge).

2. **Άνοιξε τα DevTools**: πάτα `F12` (ή `Ctrl+Shift+I`)

3. **Βρες το cookie**:  
   Tab **Application** → αριστερά **Storage → Cookies** → `https://www.spitogatos.gr`  
   Βρες τη γραμμή με **Name** = `reese84` και κάνε κλικ πάνω της.  
   Αντέγραψε ολόκληρη την **Value** (είναι μακριά συμβολοσειρά).

4. **Ενημέρωσε το GitHub Secret** — διάλεξε έναν από τους δύο τρόπους:

   **Μέσω GitHub UI** (πιο εύκολο):  
   Repo → **Settings → Secrets and variables → Actions** → `SPITOGATOS_COOKIE` → **Update**  
   Βάλε ως τιμή: `reese84=<η τιμή που αντέγραψες>`

   **Μέσω GitHub CLI** (αν έχεις εγκατεστημένο το `gh`):
   ```bash
   gh secret set SPITOGATOS_COOKIE
   # Θα σε ρωτήσει την τιμή — γράψε: reese84=<τιμή>
   ```

5. **Ενημέρωσε την ημερομηνία λήξης** στο `config.yaml`:
   ```yaml
   cookie_expiry:
     spitogatos: "YYYY-MM-DD"   # βάλε την ημερομηνία λήξης από το DevTools
   ```
   Η ημερομηνία φαίνεται στη στήλη **Expires** δίπλα στο cookie `reese84`.  
   Κάνε commit + push αυτή την αλλαγή στο repo.

6. **Επαλήθευση**: τρέξε το workflow χειροκίνητα (Actions → Run workflow) και βεβαιώσου ότι τα spitogatos logs δείχνουν αποτελέσματα και όχι `blocked`.

---

## Σημείωση για το cron schedule

Το GitHub Actions cron **δεν είναι ακριβές**. Το `*/30 * * * *` σημαίνει "κάθε 30 λεπτά το πολύ", αλλά υπό φορτίο οι runners μπορεί να καθυστερήσουν αρκετά λεπτά ή και περισσότερο. Αυτό είναι φυσιολογικό — το script απλώς τρέχει λίγο αργότερα από το αναμενόμενο.

---

## Πώς να προσθέσεις καινούριο site

1. Δημιούργησε νέο αρχείο `scrapers/mysite.py`:

```python
from .base import BaseScraper, Listing, _get
from bs4 import BeautifulSoup

class MySiteScraper(BaseScraper):
    def fetch(self, search_url: str) -> list[Listing]:
        resp = _get(search_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        # ... parse και επέστρεψε list[Listing]
        return []
```

2. Πρόσθεσε το στο `_SCRAPERS` dict στο `main.py`:

```python
from scrapers.mysite import MySiteScraper
_SCRAPERS = {
    "spitogatos": SpitogatosScraper(),
    "xe": XeScraper(),
    "mysite": MySiteScraper(),   # ← νέο
}
```

3. Χρησιμοποίησε `site: mysite` στο `config.yaml`

---

## Disclaimer

Η χρήση αυτού του εργαλείου γίνεται **με αποκλειστική ευθύνη του χρήστη**. Η αυτόματη ανάκτηση δεδομένων (scraping) από ιστοσελίδες ενδέχεται να παραβιάζει τους Όρους Χρήσης (ToS) των αντίστοιχων sites. Βεβαιώσου ότι η χρήση συμμορφώνεται με τους ισχύοντες κανονισμούς πριν χρησιμοποιήσεις το εργαλείο.
