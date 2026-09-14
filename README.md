# CZ/SK School & Work Calendar pro Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/joshuaaaaa/HA---CZ-SK-Kalendar)](https://github.com/joshuaaaaa/HA---CZ-SK-Kalendar/releases)

Dynamický kalendář a senzory školních a pracovních dnů pro **Českou republiku** a **Slovensko**.

<img width="344" height="528" alt="image" src="https://github.com/user-attachments/assets/9ea62046-44b4-4a91-b8e6-d83d405d14e7" />


## Funkce

### Automatické rozpoznání
- **Pracovní dny** - detekce, zda je dnes pracovní den (není víkend ani svátek)
- **Školní dny** - detekce, zda mají děti školu (není víkend, svátek ani prázdniny)
- **Státní svátky** - včetně automatického výpočtu pohyblivých svátků (Velikonoce)
- **Školní prázdniny** - všechny typy prázdnin s regionálním dělením

### Podporované prázdniny
| Prázdniny | Česká republika | Slovensko |
|-----------|-----------------|-----------|
| Letní | 1.7. - 31.8. | 1.7. - 31.8. |
| Podzimní | čtvrtek a pátek v týdnu s 29.10. | 30.10. - 31.10. |
| Vánoční | 23.12. - 2.1. | 22.12. - 7.1. |
| Pololetní | pátek po konci 1. pololetí | pondělí po konci 1. pololetí |
| Jarní | podle okresu (6 skupin, rotace) | podle regionu (západ/střed/východ) |
| Velikonoční | čtvrtek - pondělí | čtvrtek - úterý |

### Regionální podpora jarních prázdnin

#### Česká republika (77 okresů v 6 skupinách)
Jarní prázdniny v ČR se řídí podle **okresů** (ne krajů). Okresy jsou rozděleny do 6 skupin, které rotují v 6 týdnech od prvního pondělí v únoru:

| Skupina | Okresy |
|---------|--------|
| 1. týden | Chomutov, Jeseník, Jičín, Mladá Boleslav, Most, Olomouc, Opava, Prachatice, Příbram, Rychnov n.K., Strakonice, Šumperk, Tábor, Ústí n.L. |
| 2. týden | Benešov, Beroun, České Budějovice, Český Krumlov, Klatovy, Pardubice, Chrudim, Rokycany, Svitavy, Ústí n.O., Ostrava-město, Prostějov |
| 3. týden | Praha 1-5, Blansko, Brno-město, Brno-venkov, Břeclav, Hodonín, Vyškov, Znojmo, Domažlice, Tachov, Louny, Karviná |
| 4. týden | Praha 6-10, Cheb, Karlovy Vary, Sokolov, Nymburk, Jindřichův Hradec, Litoměřice, Děčín, Přerov, Frýdek-Místek |
| 5. týden | Praha-východ, Praha-západ, Mělník, Rakovník, Plzeň-město, Plzeň-jih, Plzeň-sever, Hradec Králové, Teplice, Nový Jičín, Uherské Hradiště, Vsetín, Zlín, Trutnov, Kroměříž |
| 6. týden | Česká Lípa, Jablonec n.N., Liberec, Semily, Havlíčkův Brod, Jihlava, Pelhřimov, Třebíč, Žďár n.S., Kladno, Kolín, Kutná Hora, Písek, Náchod, Bruntál |

#### Slovensko (8 krajů ve 3 skupinách)
Jarní prázdniny na Slovensku trvají jeden týden a jsou rozděleny do 3 turnusů od třetího pondělí v únoru:

| Turnus | Kraje |
|--------|-------|
| 1. týden | Bratislavský, Nitrianský, Trnavský (západ) |
| 2. týden | Banskobystrický, Trenčianský, Žilinský (střed) |
| 3. týden | Prešovský, Košický (východ) |

## Instalace

**Požadavky:** Home Assistant 2024.12.0 nebo novější.

### HACS (doporučeno)

1. Otevřete HACS v Home Assistant
2. Klikněte na "Integrations"
3. Klikněte na tři tečky vpravo nahoře → "Custom repositories"
4. Přidejte URL: `https://github.com/joshuaaaaa/HA---CZ-SK-Kalendar`
5. Vyberte kategorii "Integration"
6. Klikněte "Add"
7. Vyhledejte "CZ/SK Calendar" a nainstalujte
8. Restartujte Home Assistant

### Ruční instalace

1. Stáhněte složku `custom_components/cz_sk_calendar`
2. Zkopírujte ji do `<config>/custom_components/`
3. Restartujte Home Assistant

## Konfigurace

1. Přejděte do Nastavení → Zařízení a služby
2. Klikněte "Přidat integraci"
3. Vyhledejte "CZ/SK School & Work Calendar"
4. Vyberte zemi (Česká republika / Slovensko)
5. Vyberte váš **okres** (CZ) nebo **kraj** (SK) pro správné jarní prázdniny

### Vlastní seznamy: narozeniny a rodinné svátky
V nastavení integrace (Možnosti) můžete zadat **seznam narozenin** a **seznam rodinných svátků**.
Každá položka musí mít datum.

Formát (jeden záznam na řádek, nebo více záznamů na jednom řádku):
- `DD.MM | Název` (opakované každý rok)
- `YYYY-MM-DD | Název` (jednorázově)
- Jako oddělovač data a názvu lze použít i `-` nebo `;`
- Více záznamů na jednom řádku lze oddělit `|`, čárkou, středníkem i mezerou
  (`16-09-Marie 30-09-Jeroným`)

Název záznamu obsahuje **jen jméno / popis události** – datum se do něj
nepřidává. Pokud datum do názvu zadáte znovu (`16-09 | Marie 16-09`),
integrace ho z názvu odstraní, aby se ve stavu senzoru nezobrazovalo dvakrát.
Datum příští události najdete v senzorech `sensor.next_birthday_date`
a `sensor.next_family_holiday_date` a v atributu `date`.

Příklad — více záznamů na jednom řádku oddělených `|`:
```
03.02 | Narozeniny máma | 07.08 | Narozeniny táta | 08.09 | Narozeniny babička
```

Lze i kombinovat formáty a míchat `DD.MM` s `YYYY-MM-DD`:
```
03.02 | Narozeniny máma | 2026-11-15 | Výročí svatby
```

Vlastní události se zobrazují jak v **senzorech** (next_birthday, next_birthday_date, days_to_birthday atd.), tak v **kalendáři** (entita "Vlastní události").

### Nastavení připomínek
V možnostech integrace nastavíte:
- **Kolik dní předem připomínat** (`reminder_days`)
- **Připomínat denně v okně** (`reminder_daily`) – pokud je zapnuto, dostanete upozornění každý den v okně, jinak pouze jednou v den „X dní před“

## Vytvořené entity

> **Pozn. k ID entit:** zobrazovaná jména jsou česká/slovenská podle zvolené
> země, ale `entity_id` je záměrně anglické a stejné pro CZ i SK – jinak by
> každá instalace měla jiná ID. Pokud jste integraci používali před verzí
> 1.1.0, vaše entity si ponechají původní ID odvozená z názvu
> (např. `sensor.pracovni_den`); přejmenovat je můžete v *Nastavení →
> Zařízení a služby → Entity*.

### Senzory

| Senzor | Popis | Hodnota |
|--------|-------|---------|
| `sensor.workday` | Je dnes pracovní den? | `True` / `False` |
| `sensor.school_day` | Je dnes školní den? | `True` / `False` |
| `sensor.holiday` | Je dnes svátek? | `True` / `False` |
| `sensor.vacation` | Jsou dnes prázdniny? | `True` / `False` |
| `sensor.holiday_name` | Název dnešního svátku | text nebo `None` |
| `sensor.vacation_name` | Název aktuálních prázdnin | text nebo `None` |
| `sensor.special_day` | Název dnešního významného dne | text nebo `None` |
| `sensor.next_birthday` | Název příštích narozenin | text nebo `None` |
| `sensor.next_birthday_date` | Datum příštích narozenin | datum (`2026-09-16`) nebo `None` |
| `sensor.days_to_birthday` | Dní do příštích narozenin | číslo nebo `None` |
| `sensor.next_family_holiday` | Název příštího rodinného svátku | text nebo `None` |
| `sensor.next_family_holiday_date` | Datum příštího rodinného svátku | datum (`2026-09-16`) nebo `None` |
| `sensor.days_to_family_holiday` | Dní do příštího rodinného svátku | číslo nebo `None` |
| `sensor.next_holiday` | Název příštího svátku | text |
| `sensor.next_special_day` | Název příštího významného dne | text |
| `sensor.next_vacation` | Název příštích prázdnin | text |
| `sensor.days_to_holiday` | Dní do příštího svátku | číslo |
| `sensor.days_to_special_day` | Dní do příštího významného dne | číslo |
| `sensor.days_to_vacation` | Dní do příštích prázdnin | číslo |
| `sensor.nameday` | Jmeniny / meniny dneška | text nebo `None` |
| `sensor.nameday_tomorrow` | Jmeniny / meniny zítřka | text nebo `None` |
| `sensor.nameday_day_after_tomorrow` | Jmeniny / meniny pozítřka | text nebo `None` |
| `sensor.today_day_name` | Název dnešního dne v týdnu | text |
| `sensor.tomorrow_day_name` | Název zítřejšího dne v týdnu | text |
| `sensor.today_birthday` | Dnešní narozeniny | text nebo `None` |
| `sensor.today_family_holiday` | Dnešní rodinný svátek | text nebo `None` |
| `sensor.workdays_to_weekend` | Pracovních dní do víkendu | číslo |
| `sensor.school_year` | Aktuální školní rok | text, např. `2026/2027` |
| `sensor.workdays_in_month` | Počet pracovních dní v měsíci | číslo |
| `sensor.school_days_in_month` | Počet školních dní v měsíci | číslo |
| `sensor.vacation_remaining` | Zbývá dní aktuálních prázdnin | číslo |

### Binární senzory

Stejné informace jsou dostupné i jako `binary_sensor` s hodnotami `on` / `off`,
což se lépe používá v podmínkách automatizací:

| Entita | Popis |
|--------|-------|
| `binary_sensor.workday` | Je dnes pracovní den? |
| `binary_sensor.school_day` | Je dnes školní den? |
| `binary_sensor.holiday` | Je dnes svátek? |
| `binary_sensor.vacation` | Jsou dnes prázdniny? |
| `binary_sensor.weekend` | Je dnes víkend? |
| `binary_sensor.special_day` | Je dnes významný den? |

### Jmeniny / meniny

Senzory jmenin zobrazují **všechna jména daného dne**. Slovenský kalendář jich má
na řadě dní víc než jedno (např. 2. 9. „Linda, Rebeka“) – stav senzoru pak
obsahuje všechna, oddělená čárkou. Jednotlivá jména najdete i v atributech:

| Atribut | Popis |
|---------|-------|
| `names` | Seznam jmen, např. `["Linda", "Rebeka"]` |
| `names_count` | Počet jmen daného dne |
| `date` | Datum, ke kterému se senzor vztahuje |
| `offset_days` | 0 = dnes, 1 = zítra, 2 = pozítří |

Kromě senzorů jsou jmeniny dostupné i jako samostatný kalendář
(`calendar.namedays`, zobrazený jako „Jmeniny“ / „Meniny“) – obsahuje událost pro každý den
v roce s názvem daného dne. Kombinovaný kalendář svátků a prázdnin zůstává beze
změny, aby ho jmeniny nezaplnily.

```yaml
# Všechna jména zítřejšího dne
{{ states('sensor.nameday_tomorrow') }}

# Jen první jméno
{{ state_attr('sensor.nameday_tomorrow', 'names')[0] }}
```

### Zjištění jmenin/menín pro libovolné datum (service)

Senzory `sensor.nameday*` ukazují jen dnešek, zítřek a pozítří. Pro **libovolné datum**
(např. narozeninový kalkulátor, plánování dopředu) použijte službu (action)
`cz_sk_calendar.get_nameday`:

```yaml
action: cz_sk_calendar.get_nameday
data:
  date: "2026-03-19"
  country: "CZ"   # volitelné, výchozí je země první nakonfigurované integrace
response_variable: vysledek
```

Vrací:
```yaml
date: "2026-03-19"
country: "CZ"
nameday: "Josef"
names: ["Josef"]
```

Lze zavolat i ve skriptu/automatizaci a výsledek dál zpracovat pomocí `response_variable`.

Hotový příklad skriptu, který takto zjistí jmeniny/meniny na celý týden dopředu
(7x zavolá službu a výsledky spojí do jedné notifikace), najdete v
[`examples/meniny_na_tyzden.yaml`](examples/meniny_na_tyzden.yaml).

### Příklad automatizace: narozeniny 3 dny dopředu
```yaml
automation:
  - alias: "Narozeniny za 3 dny"
    trigger:
      - platform: numeric_state
        entity_id: sensor.days_to_birthday
        below: 4
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.days_to_birthday', 'should_notify') }}
    action:
      - service: notify.mobile_app
        data:
          title: "Blíží se narozeniny"
          message: >
            {{ state_attr('sensor.days_to_birthday', 'next_birthday') }}
```

### Kalendáře

| Kalendář | Popis |
|----------|-------|
| `calendar.holidays` | Pouze státní svátky |
| `calendar.vacations` | Pouze školní prázdniny |
| `calendar.combined` | Kombinovaný kalendář |
| `calendar.custom_events` | Narozeniny a rodinné svátky |
| `calendar.namedays` | Jmeniny / meniny – událost na každý den v roce |

## Příklady automatizací

### Budík pouze ve školní dny
```yaml
automation:
  - alias: "Školní budík"
    trigger:
      - platform: time
        at: "06:30:00"
    condition:
      - condition: state
        entity_id: binary_sensor.school_day
        state: "on"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.bedroom
        data:
          media_content_id: "alarm.mp3"
          media_content_type: "music"
```

### Oznámení o blížících se prázdninách
```yaml
automation:
  - alias: "Oznámení o prázdninách"
    trigger:
      - platform: numeric_state
        entity_id: sensor.days_to_vacation
        below: 8
    action:
      - service: notify.mobile_app
        data:
          title: "Prázdniny se blíží!"
          message: >
            Za {{ states('sensor.days_to_vacation') }} dní začínají
            {{ state_attr('sensor.next_vacation', 'friendly_name') }}
```

### Jiný režim topení o prázdninách
```yaml
automation:
  - alias: "Prázdninový režim topení"
    trigger:
      - platform: state
        entity_id: binary_sensor.vacation
        to: "on"
    action:
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thermostat
        data:
          preset_mode: "away"
```

## Pohyblivé svátky

Integrace automaticky vypočítává datum Velikonoc pomocí algoritmu Computus (Anonymní Gregoriánský algoritmus), který je platný pro libovolný rok gregoriánského kalendáře.

Od data Velikonoční neděle se odvozují:
- **Velký pátek** (CZ/SK) - 2 dny před Velikonoční nedělí
- **Velikonoční pondělí** (CZ/SK) - 1 den po Velikonoční neděli

## Podpora

Máte-li problémy nebo návrhy na vylepšení, vytvořte [issue na GitHubu](https://github.com/joshuaaaaa/HA---CZ-SK-Kalendar/issues).

## Licence

MIT License - viz soubor [LICENSE](LICENSE)

## http://buymeacoffee.com/jakubhruby

<img width="150" height="150" alt="qr-code" src="https://github.com/user-attachments/assets/2581bf36-7f7d-4745-b792-d1abaca6e57d" />
