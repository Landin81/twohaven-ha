# TwoHaven Nätverkslåda

Stänger av internet för spelkonsoler (Xbox, PlayStation) när barnets skärmtid i TwoHaven är slut, utanför schemat
eller när du låser. Inget annat i nätverket påverkas, och stoppar du tillägget fungerar allt som vanligt igen.

## Så kommer du igång

1. Skapa en nyckel i TwoHaven-appen: **Mer → Home Assistant → Skapa nyckel**.
2. Klistra in nyckeln under **Konfiguration → api_key** här i tillägget och starta det.
3. Öppna **Mer → Familj-funktioner → Spelkonsoler** i TwoHaven-appen. Efter en minut syns enheterna i ert nätverk.
4. Tryck **Koppla** vid konsolen och välj barnet.

## Bra att veta

- Spel som inte behöver internet fungerar fortfarande – det här stoppar onlinespel, chatt, YouTube och nedladdningar.
- Home Assistant bör helst sitta med nätverkskabel. Det fungerar oftast över wifi också.
- Har ert nätverk IPv6 kan konsolen ibland nå internet den vägen. Stäng i så fall av IPv6 för konsolen i routern.
- **interface**: lämna tomt så väljs nätverkskortet automatiskt (t.ex. `end0` eller `wlan0`).
