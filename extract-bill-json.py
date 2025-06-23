import os
import json
import csv
from datetime import datetime
from google import genai
from google.genai import types

def vypocitat_naklady(tokeny, model_name="gemini-2.5-flash-lite-preview-06-17"):
    """
    Vypočítá náklady na základě počtu tokenů a modelu.
    
    Args:
        tokeny: Počet tokenů
        model_nam                # Přidáme do reportu - rozdelíme tokeny a náklady na počet súborov
                tokeny_na_subor = celkove_tokeny / len(davka_obrazky)
                naklady_na_subor = celkove_naklady / len(davka_obrazky)
                
                data_reportu.append([
                    cas, 
                    os.path.basename(puvodni_obrazek), 
                    int(tokeny_na_subor),  # Zaokrúhlime na celé číslo
                    naklady_na_subor,     # Presné náklady na súbor
                    'USPECH_DAVKA', 
                    f'Dávka {len(davka_obrazky)} obrázkov - tokeny/náklady rozdelené na súbor'
                ])modelu
    
    Returns:
        float: Náklady v USD
    """
    # Oficiální ceny z https://ai.google.dev/pricing (v USD za 1M tokenů)
    # Aktualizované k 22.6.2025
    ceny_modelu = {
        "gemini-2.5-flash-lite-preview-06-17": 0.10,  # Input: $0.10, Output: $0.40 za 1M tokenů
        "gemini-2.5-flash": 0.30,  # Input: $0.30, Output: $2.50 za 1M tokenů  
        "gemini-2.0-flash": 0.10,  # Input: $0.10, Output: $0.40 za 1M tokenů
        "gemini-2.0-flash-lite": 0.075,  # Input: $0.075, Output: $0.30 za 1M tokenů
        "gemini-1.5-flash": 0.075,  # Input: $0.075, Output: $0.30 za 1M tokenů
        "gemini-1.5-flash-8b": 0.0375,  # Input: $0.0375, Output: $0.15 za 1M tokenů
        "gemini-1.5-pro": 1.25,  # Input: $1.25, Output: $5.00 za 1M tokenů
        "gemini-2.5-pro": 1.25  # Input: $1.25, Output: $10.00 za 1M tokenů
    }
    
    # Používame najnižšiu cenu (input) pre jednoduchosť - v skutočnosti by sme mali rozlišovať input/output
    cena_za_milion = ceny_modelu.get(model_name, 0.10)  # default cena
    naklady_usd = (tokeny / 1_000_000) * cena_za_milion
    return naklady_usd

def ulozit_report_spotreby(adresar, data_reportu):
    """
    Uloží report o spotřebě tokenů a nákladech do CSV souboru.
    
    Args:
        adresar: Adresář kde se má uložit report
        data_reportu: Seznam s daty ve formátu [čas, soubor, tokeny, náklady_usd, status]
    """
    report_soubor = os.path.join(adresar, "report_spotreby.csv")
    
    # Zkontrolujeme, zda soubor existuje
    soubor_existuje = os.path.exists(report_soubor)
    
    with open(report_soubor, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Napíšeme hlavičku jen pokud soubor neexistuje
        if not soubor_existuje:
            writer.writerow(['cas', 'soubor', 'tokeny', 'naklady_usd', 'status', 'poznamka'])
        
        # Napíšeme data
        for radek in data_reportu:
            writer.writerow(radek)

def nacti_api_klic(soubor="api_key.txt"):
    """Bezpečně načte API klíč z textového souboru."""
    try:
        with open(soubor, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Chyba: Soubor '{soubor}' s API klíčem nebyl nalezen.")
        print("Prosím, vytvořte jej a vložte do něj svůj API klíč.")
        return None

def extrahovat_data_z_uctenky(nazev_obrazku):
    """
    Načte obrázek účtenky, pošle ho Google AI a uloží výsledek do JSON souboru se stejným názvem.
    """
    print("Načítám API klíč...")
    api_key = nacti_api_klic()
    if not api_key:
        return

    try:
        print(f"Načítám obrázek '{nazev_obrazku}'...")
        with open(nazev_obrazku, "rb") as f:
            obrazek_data = f.read()
    except FileNotFoundError:
        print(f"Chyba: Obrázek '{nazev_obrazku}' nebyl nalezen v tomto adresáři.")
        return
    
    # Vytvoříme název výstupního JSON souboru ze stejného adresáře a názvu jako obrázek
    zakladni_nazev = os.path.splitext(nazev_obrazku)[0]  # Odstraní příponu (.png, .jpg, atd.)
    nazev_vystupu = f"{zakladni_nazev}.json"
    adresar = os.path.dirname(nazev_obrazku) or "."

    print("Inicializuji Google AI klienta...")
    client = genai.Client(api_key=api_key)

    model = "gemini-2.5-flash-lite-preview-06-17"
    
    # <<< ZMĚNA: Místo base64 kódu se nyní načítají data obrázku ze souboru
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    mime_type="image/png", # Ujistěte se, že typ odpovídá vašemu obrázku (např. image/jpeg)
                    data=obrazek_data
                ),
                types.Part.from_text(text="""# ROLE A CÍL
Jsi autonomní systém pro inteligentní extrakci dat z dokumentů. Tvým úkolem je analyzovat přiložený obrázek účtenky, porozumět její struktuře a převést VŠECHNY informace do logicky uspořádaného formátu JSON. Každá účtenka je jiná, proto se nespoléhej na pevně danou šablonu, ale na svou schopnost porozumět kontextu.

# METODIKA PRÁCE
Postupuj jako člověk, který se snaží data uspořádat do přehledné struktury:
1.  **Zmapuj Dokument:** Projdi si celou účtenku a identifikuj vizuálně a logicky oddělené bloky informací (např. hlavička s prodejcem, seznam položek, souhrn plateb, detaily o transakci, daňový rozpis, čárový kód atd.).
2.  **Přesně Přepisuj:** Při čtení dat buď maximálně přesný. Zkontroluj si dvakrát složitá slova a čísla.
3.  **Logicky Zoskupuj:** Vytvoř JSON pole, kde každý objekt reprezentuje jeden logický blok, který jsi identifikoval v kroku 1.
4.  **Sám Vytvoř Popisky:** Pro každý blok vytvoř popisný název (`\"typ\"`) a pro každou informaci uvnitř bloku vytvoř jasný a logický klíč (např. `\"sazba_dph\"`, `\"celkova_castka\"`, `\"nazev_polozky\"`). Klíče by měly být konzistentní a srozumitelné.
5.  **Nezapomeň na Nic:** Ujisti se, že jsi přepsal VŠECHNY informace z účtenky, včetně číselných kódů, poznámek a dalších detailů.

# PŘÍKLAD MYŠLENÍ (ne formátu!)
- \"Tohle je jasně hlavička, nazvu ji 'informace_o_prodejci'.\"
- \"Tady začíná seznam zboží. Každý řádek bude samostatný objekt typu 'polozka_nakupu'.\"
- \"Aha, sekce o DPH. Nazvu ji 'danovy_rozpis' a uvnitř budou klíče 'sazba', 'zaklad', 'dan'.\"
- \"Na konci je dlouhé číslo pod čárami. To je asi interní kód nebo EAN. Nazvu ho 'identifikator_dokladu'.\"
- \"Informace o platbě kartou jsou pohromadě, vytvořím pro ně blok 'detaily_platebni_transakce'.\"

# ZÁVĚREČNÝ POKYN
Aplikuj tuto metodiku na přiloženou účtenku. Vytvoř logický, přehledný a kompletní JSON přepis. Nesnaž se napodobit žádný konkrétní příklad, ale vytvoř tu nejlepší možnou strukturu pro data, která vidíš. Začni generovat:"""),
            ],
        ),
    ]

    print("Odesílám požadavek a čekám na odpověď...")
    
    # <<< ZMĚNA: Používáme `generate_content` pro získání celé odpovědi najednou
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents
        )
        
        # Získáme počet tokenů a vypočítáme náklady
        tokeny = response.usage_metadata.total_token_count
        naklady_usd = vypocitat_naklady(tokeny, model)
        
        print(f"Spotřebováno tokenů: {tokeny}")
        print(f"Náklady: ${naklady_usd:.6f} USD")
        
        # <<< ZMĚNA: Ukládáme výstup do souboru
        # Odstraníme z odpovědi případné značky pro kód ```json a ```
        cisty_json_text = response.text.replace("```json\n", "").replace("\n```", "").strip()

        with open(nazev_vystupu, "w", encoding="utf-8") as f:
            f.write(cisty_json_text)
        
        # Uložíme report o spotřebě
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = [[cas, os.path.basename(nazev_obrazku), tokeny, naklady_usd, 'USPECH', '']]
        ulozit_report_spotreby(adresar, data_reportu)
        
        print(f"Hotovo! Data byla úspěšně extrahována a uložena do souboru '{nazev_vystupu}'.")
        print(f"Report o spotřebě uložen do '{os.path.join(adresar, 'report_spotreby.csv')}'")

    except Exception as e:
        # V případě chyby také uložíme do reportu
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = [[cas, os.path.basename(nazev_obrazku), 0, 0.0, 'CHYBA', str(e)]]
        ulozit_report_spotreby(adresar, data_reportu)
        print(f"Nastala chyba při komunikaci s Google AI: {e}")

def zpracovat_davku_uctenek(adresar="example", pripony=(".png", ".jpg", ".jpeg"), velikost_davky=5):
    """
    Zpracuje obrázky účtenek v dávkách zadané velikosti.
    
    Args:
        adresar: Adresář s obrázky
        pripony: Podporované přípony souborů
        velikost_davky: Kolik obrázků zpracovat najednou (default: 5)
    """
    print(f"Hledám obrázky v adresáři '{adresar}'...")
    
    # Najdeme všechny soubory s podporovanými příponami
    obrazky = []
    for soubor in os.listdir(adresar):
        if soubor.lower().endswith(pripony):
            cesta_k_souboru = os.path.join(adresar, soubor)
            obrazky.append(cesta_k_souboru)
    
    if not obrazky:
        print(f"V adresáři '{adresar}' nebyly nalezeny žádné obrázky s příponami {pripony}")
        return
    
    print(f"Nalezeno {len(obrazky)} obrázků: {[os.path.basename(img) for img in obrazky]}")
    print(f"Zpracování v dávkách po {velikost_davky} obrázcích...")
    
    # Načteme API klíč
    print("Načítám API klíč...")
    api_key = nacti_api_klic()
    if not api_key:
        return
    
    # Inicializujeme klienta
    print("Inicializuji Google AI klienta...")
    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash-lite-preview-06-17"
    
    # Zpracujeme obrázky v dávkách
    celkem_zpracovano = 0
    
    for i in range(0, len(obrazky), velikost_davky):
        davka = obrazky[i:i + velikost_davky]
        cislo_davky = (i // velikost_davky) + 1
        celkem_davek = (len(obrazky) + velikost_davky - 1) // velikost_davky
        
        print(f"\n--- Zpracovávám dávku {cislo_davky}/{celkem_davek} ({len(davka)} obrázků) ---")
        
        # Zpracujeme jednu dávku
        if zpracovat_jednu_davku(davka, client, model, adresar):
            celkem_zpracovano += len(davka)
    
    print(f"\nHotovo! Celkem zpracováno {celkem_zpracovano} obrázků z {len(obrazky)}.")

def zpracovat_jednu_davku(davka_obrazky, client, model, adresar):
    """
    Zpracuje jednu dávku obrázků.
    
    Returns:
        tuple: (úspěch: bool, celkové_tokeny: int, celkové_náklady: float)
    """
    # Připravíme prompt pro dávkové zpracování
    davkovy_prompt = """# ROLE A CÍL
Jsi expertní systém pro dávkovou extrakci dat z více dokumentů najednou. Tvým úkolem je analyzovat VŠECHNY přiložené obrázky účtenek. Pro KAŽDÝ obrázek musíš extrahovat veškeré informace a vytvořit pro něj samostatný JSON objekt. Všechny tyto JSON objekty pak zabal do jednoho hlavního JSON pole.

# METODIKA PRÁCE
1. **Iteruj přes obrázky:** Postupně projdi každý obrázek, který ti byl poslán.
2. **Analyzuj každý obrázek samostatně:** Pro každý jednotlivý obrázek aplikuj následující logiku:
   - Zmapuj dokument a identifikuj bloky informací
   - Přesně přepisuj všechna data
   - Vytvoř logicky strukturovaný JSON objekt
   - Přidej identifikátor: Do JSON objektu přidej klíč "obrazek_index" s pořadovým číslem obrázku (0, 1, 2...)
3. **Zkompletuj výstup:** Vytvoř pole JSON objektů ve formátu: [{"obrazek_index": 0, "data": {...}}, {"obrazek_index": 1, "data": {...}}, ...]

# ZÁVĚREČNÝ POKYN
Aplikuj tuto metodiku na VŠECHNY přiložené obrázky. Vytvoř JEDEN JSON výstup obsahující pole objektů, jeden pro každý obrázek."""
    
    # Připravíme obsah pro API
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=davkovy_prompt)])]
    
    # Přidáme všechny obrázky do jednoho requestu
    print("Načítám obrázky v dávce...")
    for i, obrazek_cesta in enumerate(davka_obrazky):
        try:
            with open(obrazek_cesta, "rb") as f:
                obrazek_data = f.read()
            
            # Určíme MIME typ podle přípony
            pripona = os.path.splitext(obrazek_cesta)[1].lower()
            if pripona in ['.jpg', '.jpeg']:
                mime_type = "image/jpeg"
            elif pripona == '.png':
                mime_type = "image/png"
            else:
                mime_type = "image/png"  # default
            
            contents[0].parts.append(types.Part.from_bytes(mime_type=mime_type, data=obrazek_data))
            print(f"  - Přidán obrázek {i+1}/{len(davka_obrazky)}: {os.path.basename(obrazek_cesta)}")
            
        except Exception as e:
            print(f"Chyba při načítání obrázku '{obrazek_cesta}': {e}")
            continue
    
    print("Odesílám dávkový požadavek a čekám na odpověď...")
    
    try:
        response = client.models.generate_content(model=model, contents=contents)
        
        # Získáme počet tokenů a vypočítáme náklady
        celkove_tokeny = response.usage_metadata.total_token_count
        celkove_naklady = vypocitat_naklady(celkove_tokeny, model)
        
        print(f"Celkem tokenů pro dávku: {celkove_tokeny}")
        print(f"Celkové náklady dávky: ${celkove_naklady:.6f} USD")
        
        # POZNÁMKA: Gemini API neposkytuje rozloženie tokenov na jednotlivé obrázky v dávke
        # Preto uvedieme celkové tokeny a poznámku, že sú rozdelené na dávku
        print(f"⚠️  Tokeny sa týkajú celej dávky {len(davka_obrazky)} obrázkov, nie jednotlivých súborov")
        
        # Očistíme odpověď od značek kódu
        cisty_json_text = response.text.replace("```json\n", "").replace("\n```", "").replace("```json", "").replace("```", "").strip()
        
        # Parsujeme JSON odpověď
        vysledky = json.loads(cisty_json_text)
        
        if not isinstance(vysledky, list):
            print("Chyba: Odpověď od AI není ve formátu pole.")
            return False, 0, 0.0
        
        # Uložíme každý výsledek do samostatného JSON souboru
        print(f"Ukládám výsledky do {len(vysledky)} JSON souborů...")
        
        # Pripravíme data pre report
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = []
        
        uspesne_zpracovano = 0
        for vysledek in vysledky:
            obrazek_index = vysledek.get('obrazek_index')
            if obrazek_index is None or obrazek_index >= len(davka_obrazky):
                print(f"Varování: Neplatný index obrázku v odpovědi: {obrazek_index}")
                continue
            
            # Získáme původní cestu k obrázku a vytvoříme název JSON souboru
            puvodni_obrazek = davka_obrazky[obrazek_index]
            zakladni_nazev = os.path.splitext(puvodni_obrazek)[0]
            json_soubor = f"{zakladni_nazev}.json"
            
            # Uložíme data (bez indexu) do JSON souboru
            data = vysledek.get('data', vysledek)  # Pokud není 'data', použijeme celý objekt
            if 'obrazek_index' in data:
                del data['obrazek_index']  # Odstraníme index z finálních dat
            
            try:
                with open(json_soubor, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"  - Uloženo: {os.path.basename(json_soubor)}")
                
                # Přidáme do reportu - používáme celkové údaje pre celú dávku
                data_reportu.append([
                    cas, 
                    os.path.basename(puvodni_obrazek), 
                    celkove_tokeny,  # Celkové tokeny pro celou dávku
                    celkove_naklady, # Celkové náklady pre celú dávku
                    'USPECH_DAVKA', 
                    f'Dávka {len(davka_obrazky)} obrázkov - tokeny/náklady sú pre celú dávku'
                ])
                uspesne_zpracovano += 1
                
            except Exception as e:
                print(f"Chyba při ukládání {json_soubor}: {e}")
                data_reportu.append([
                    cas, 
                    os.path.basename(puvodni_obrazek), 
                    0, 
                    0.0, 
                    'CHYBA_UKLADANI', 
                    str(e)
                ])
        
        # Uložíme report
        ulozit_report_spotreby(adresar, data_reportu)
        
        print(f"Dávka dokončena! Zpracováno {uspesne_zpracovano}/{len(vysledky)} obrázků.")
        return True, celkove_tokeny, celkove_naklady
        
    except json.JSONDecodeError as e:
        print(f"Chyba při parsování JSON odpovědi: {e}")
        print("Surová odpověď:")
        print(response.text)
        
        # Uložíme chybu do reportu pro všechny soubory v dávce
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = []
        for obrazek_cesta in davka_obrazky:
            data_reportu.append([
                cas, 
                os.path.basename(obrazek_cesta), 
                0, 
                0.0, 
                'CHYBA_JSON', 
                str(e)
            ])
        ulozit_report_spotreby(adresar, data_reportu)
        return False, 0, 0.0
        
    except Exception as e:
        print(f"Nastala chyba při komunikaci s Google AI: {e}")
        
        # Uložíme chybu do reportu pro všechny soubory v dávce
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = []
        for obrazek_cesta in davka_obrazky:
            data_reportu.append([
                cas, 
                os.path.basename(obrazek_cesta), 
                0, 
                0.0, 
                'CHYBA_API', 
                str(e)
            ])
        ulozit_report_spotreby(adresar, data_reportu)
        return False, 0, 0.0

def zpracovat_davku_jednotlivo(adresar="example", pripony=(".png", ".jpg", ".jpeg")):
    """
    Spracuje obrázky jednotlivo pre presnejšie sledovanie tokenov a nákladov.
    Pomalšie, ale poskytuje presné údaje pre každý súbor.
    
    Args:
        adresar: Adresář s obrázky
        pripony: Podporované přípony souborů
    """
    print(f"Hledám obrázky v adresáři '{adresar}'...")
    
    # Najdeme všechny soubory s podporovanými příponami
    obrazky = []
    for soubor in os.listdir(adresar):
        if soubor.lower().endswith(pripony):
            cesta_k_souboru = os.path.join(adresar, soubor)
            obrazky.append(cesta_k_souboru)
    
    if not obrazky:
        print(f"V adresáři '{adresar}' nebyly nalezeny žádné obrázky s příponami {pripony}")
        return
    
    print(f"Nalezeno {len(obrazky)} obrázků: {[os.path.basename(img) for img in obrazky]}")
    print("Zpracovávám každý obrázek jednotlivo pre presné sledovanie tokenů...")
    
    celkove_tokeny = 0
    celkove_naklady = 0.0
    
    # Zpracujeme každý obrázek jednotlivo
    for i, obrazek_cesta in enumerate(obrazky, 1):
        print(f"\n--- Zpracovávám obrázek {i}/{len(obrazky)}: {os.path.basename(obrazek_cesta)} ---")
        
        # Spracujeme jednotlivý obrázek
        tokeny, naklady = zpracovat_jeden_obrazek_s_metrami(obrazek_cesta)
        if tokeny > 0:
            celkove_tokeny += tokeny
            celkove_naklady += naklady
    
    print(f"\n🎯 SÚHRN:")
    print(f"Celkom spracovaných obrázkov: {len(obrazky)}")
    print(f"Celkové tokeny: {celkove_tokeny}")
    print(f"Celkové náklady: ${celkove_naklady:.6f} USD")
    print(f"Priemer na obrázok: {celkove_tokeny//len(obrazky) if obrazky else 0} tokenov, ${celkove_naklady/len(obrazky) if obrazky else 0:.6f} USD")

def zpracovat_jeden_obrazek_s_metrami(nazev_obrazku):
    """
    Spracuje jeden obrázek a vráti tokeny a náklady.
    
    Returns:
        tuple: (tokeny: int, náklady: float)
    """
    # Načteme API klíč
    api_key = nacti_api_klic()
    if not api_key:
        return 0, 0.0

    try:
        with open(nazev_obrazku, "rb") as f:
            obrazek_data = f.read()
    except FileNotFoundError:
        print(f"Chyba: Obrázek '{nazev_obrazku}' nebyl nalezen.")
        return 0, 0.0
    
    # Vytvoríme názov výstupného JSON súboru
    zakladni_nazev = os.path.splitext(nazev_obrazku)[0]
    nazev_vystupu = f"{zakladni_nazev}.json"
    adresar = os.path.dirname(nazev_obrazku) or "."

    # Inicializujeme klienta
    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash-lite-preview-06-17"
    
    # Určíme MIME typ
    pripona = os.path.splitext(nazev_obrazku)[1].lower()
    if pripona in ['.jpg', '.jpeg']:
        mime_type = "image/jpeg"
    elif pripona == '.png':
        mime_type = "image/png"
    else:
        mime_type = "image/png"  # default
    
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(mime_type=mime_type, data=obrazek_data),
                types.Part.from_text(text="""# ROLE A CÍL
Jsi autonomní systém pro inteligentní extrakci dat z dokumentů. Tvým úkolem je analyzovat přiložený obrázek účtenky, porozumět její struktuře a převést VŠECHNY informace do logicky uspořádaného formátu JSON. Každá účtenka je jiná, proto se nespoléhej na pevně danou šablonu, ale na svou schopnost porozumět kontextu.

# METODIKA PRÁCE
Postupuj jako člověk, který se snaží data uspořádat do přehledné struktury:
1.  **Zmapuj Dokument:** Projdi si celou účtenku a identifikuj vizuálně a logicky oddělené bloky informací (např. hlavička s prodejcem, seznam položek, souhrn plateb, detaily o transakci, daňový rozpis, čárový kód atd.).
2.  **Přesně Přepisuj:** Při čtení dat buď maximálně přesný. Zkontroluj si dvakrát složitá slova a čísla.
3.  **Logicky Zoskupuj:** Vytvoř JSON pole, kde každý objekt reprezentuje jeden logický blok, který jsi identifikoval v kroku 1.
4.  **Sám Vytvoř Popisky:** Pro každý blok vytvoř popisný název (`\"typ\"`) a pro každou informaci uvnitř bloku vytvoř jasný a logický klíč (např. `\"sazba_dph\"`, `\"celkova_castka\"`, `\"nazev_polozky\"`). Klíče by měly být konzistentní a srozumitelné.
5.  **Nezapomeň na Nic:** Ujisti se, že jsi přepsal VŠECHNY informace z účtenky, včetně číselných kódů, poznámek a dalších detailů.

# PŘÍKLAD MYŠLENÍ (ne formátu!)
- \"Tohle je jasně hlavička, nazvu ji 'informace_o_prodejci'.\"
- \"Tady začíná seznam zboží. Každý řádek bude samostatný objekt typu 'polozka_nakupu'.\"
- \"Aha, sekce o DPH. Nazvu ji 'danovy_rozpis' a uvnitř budou klíče 'sazba', 'zaklad', 'dan'.\"
- \"Na konci je dlouhé číslo pod čárami. To je asi interní kód nebo EAN. Nazvu ho 'identifikator_dokladu'.\"
- \"Informace o platbě kartou jsou pohromadě, vytvořím pro ně blok 'detaily_platebni_transakce'.\"

# ZÁVĚREČNÝ POKYN
Aplikuj tuto metodiku na přiloženou účtenku. Vytvoř logický, přehledný a kompletní JSON přepis. Nesnaž se napodobit žádný konkrétní příklad, ale vytvoř tu nejlepší možnou strukturu pro data, která vidíš. Začni generovat:"""),
            ],
        ),
    ]

    try:
        response = client.models.generate_content(model=model, contents=contents)
        
        # Získáme presné údaje o tokenoch
        tokeny = response.usage_metadata.total_token_count
        naklady_usd = vypocitat_naklady(tokeny, model)
        
        print(f"📊 Tokeny: {tokeny}, Náklady: ${naklady_usd:.6f} USD")
        
        # Uložíme výstup
        cisty_json_text = response.text.replace("```json\n", "").replace("\n```", "").strip()
        with open(nazev_vystupu, "w", encoding="utf-8") as f:
            f.write(cisty_json_text)
        
        # Uložíme do reportu
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = [[cas, os.path.basename(nazev_obrazku), tokeny, naklady_usd, 'USPECH_JEDNOTLIVO', 'Spracované jednotlivo - presné údaje']]
        ulozit_report_spotreby(adresar, data_reportu)
        
        print(f"✅ Uloženo: {os.path.basename(nazev_vystupu)}")
        return tokeny, naklady_usd
        
    except Exception as e:
        print(f"❌ Chyba: {e}")
        
        # Uložíme chybu do reportu
        cas = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_reportu = [[cas, os.path.basename(nazev_obrazku), 0, 0.0, 'CHYBA', str(e)]]
        ulozit_report_spotreby(adresar, data_reportu)
        return 0, 0.0

if __name__ == "__main__":
    # Volba: zpracovat jeden obrázek nebo všechny v adresáři
    print("1 - Zpracovat jeden obrázek")
    print("2 - Zpracovat všechny obrázky v adresáři naraz (dávka - rychlejšie, ale nepresné tokeny)")
    print("3 - Zpracovat všechny obrázky jednotlivo (pomalšie, ale presné tokeny pre každý súbor)")
    
    volba = input("Vaše volba (1, 2 nebo 3): ").strip()
    
    if volba == "1":
        # Původní funkcionalita - jeden obrázek
        jmeno_souboru_s_obrazkem = "example/uctenka.png"
        extrahovat_data_z_uctenky(jmeno_souboru_s_obrazkem)
    elif volba == "2":
        # Nová funkcionalita - dávkové zpracování
        adresar = input("Zadejte adresář (nebo stiskněte Enter pro 'example'): ").strip()
        if not adresar:
            adresar = "example"
        
        # Dotaz na velikost dávky
        try:
            velikost_str = input("Zadejte velikost dávky (nebo stiskněte Enter pro default 5): ").strip()
            if velikost_str:
                velikost_davky = int(velikost_str)
                if velikost_davky <= 0:
                    print("Velikost dávky musí být kladné číslo. Používám default 5.")
                    velikost_davky = 5
            else:
                velikost_davky = 5
        except ValueError:
            print("Neplatné číslo. Používám default velikost dávky 5.")
            velikost_davky = 5
        
        zpracovat_davku_uctenek(adresar, velikost_davky=velikost_davky)
    elif volba == "3":
        # Nová funkcionalita - spracovanie jednotlivo
        adresar = input("Zadejte adresář (nebo stiskněte Enter pro 'example'): ").strip()
        if not adresar:
            adresar = "example"
        
        zpracovat_davku_jednotlivo(adresar)
    else:
        print("Neplatná volba.")