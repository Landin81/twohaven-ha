# TwoHaven för Home Assistant

Styr barnens skärmtid från ditt smarta hem: se hur mycket tid som är kvar, ge bonustid för sysslor, lås vid middagen och stäng av internet vid läggdags. Kräver ett konto i [TwoHaven](https://twohaven.se).

*English below.*

## Installera

[![Öppna i HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Landin81&repository=twohaven-ha&category=integration)

1. Tryck på knappen ovan (eller i HACS: ⋮ → **Anpassade repositorier** → `https://github.com/Landin81/twohaven-ha`, typ **Integration**).
2. Installera **TwoHaven** och starta om Home Assistant.
3. I TwoHaven-appen: **Mer → Home Assistant → Skapa ny nyckel**. Kopiera nyckeln.
4. I Home Assistant: **Inställningar → Enheter och tjänster → Lägg till integration → TwoHaven**. Klistra in nyckeln.

Klart! Varje barn blir en enhet med:

| Entitet | Vad |
|---|---|
| Skärmtid kvar idag / Skärmtid idag / Bonus idag | Minuter |
| Sysslor att kolla | Antal sysslor som väntar på ditt svar |
| Aktiv app | Appen som används just nu |
| Låst / Online | Binära sensorer |
| Lås enheterna | Brytare – på = alla barnets enheter låsta |
| Internet | Brytare – av = internet avstängt |
| Bonus +15 min / Spela ljud | Knappar |

## Sysslor med kontroll 🧹

Barnet kryssar i "Bäddat sängen" på surfplattan i hallen och får 10 minuter direkt. Du får en notis i mobilen: **👍 Stämmer** eller **👎 Fusk**. Vid fusk tas tiden tillbaka och dubbla tiden dras. Du kan också svara på Översikt i TwoHaven-appen.

[![Importera blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FLandin81%2Ftwohaven-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Ftwohaven%2Fchore_check.yaml)

1. Skapa en hjälpare av typen **Växel**, t.ex. "Sam – bäddat sängen".
2. Importera blueprinten ovan och skapa en automation: välj växeln, skriv barnets namn, syssla, minuter och välj din mobil.
3. Lägg växeln på instrumentpanelen. Den bockas ur automatiskt vid midnatt.

## Åtgärder (för egna automationer)

| Åtgärd | Exempel |
|---|---|
| `twohaven.give_bonus` | `child: sam`, `minutes: 10`, `reason: Läst en bok`, `once: true` |
| `twohaven.chore` | `child: sam`, `name: Dukat`, `minutes: 15`, `penalty_factor: 2` – returnerar `chore.id` |
| `twohaven.approve_chore` / `twohaven.reject_chore` | `chore_id: 12` |
| `twohaven.lock` / `twohaven.unlock` | `child: sam`, `minutes: 30` (0 = tills vidare), valfritt `device` |
| `twohaven.open` | Öppna tillfälligt: `child: sam`, `minutes: 30` |
| `twohaven.internet` | `child: sam`, `off: true` |
| `twohaven.ring` | Spela ljud på barnets enheter |

Händelser: `twohaven_chore_claimed` och `twohaven_chore_decided`.

Exempel – lås när larmet slås på för natten:

```yaml
triggers:
  - trigger: state
    entity_id: alarm_control_panel.hemma
    to: armed_night
actions:
  - action: twohaven.lock
    data: { child: sam }
```

Skydd: högst 120 minuter per gång och 240 bonusminuter per barn och dag via Home Assistant. Allt syns i TwoHavens logg.

---

## English

Control your children's screen time from your smart home: see time left, give bonus time for chores, lock devices at dinner and turn off the internet at bedtime. Requires a [TwoHaven](https://twohaven.se) account.

**Install:** add this repository in HACS (button above, or ⋮ → Custom repositories → `https://github.com/Landin81/twohaven-ha`, type Integration), install **TwoHaven**, restart, then add the integration and paste an API key from the TwoHaven app (**More → Home Assistant → Create new key**).

Each child becomes a device with sensors (time left, used, bonus, chores to check, current app), binary sensors (locked, online), switches (lock devices, internet) and buttons (+15 min, play sound).

**Chores with a check:** the child ticks "Made the bed" and gets the time right away; you get a notification with 👍 True / 👎 Cheating. Cheating takes the time back and deducts double. Import the blueprint above.

**Actions:** `twohaven.give_bonus`, `twohaven.chore`, `twohaven.approve_chore`, `twohaven.reject_chore`, `twohaven.lock`, `twohaven.unlock`, `twohaven.open`, `twohaven.internet`, `twohaven.ring`. Events: `twohaven_chore_claimed`, `twohaven_chore_decided`.

## Licens / License

MIT
