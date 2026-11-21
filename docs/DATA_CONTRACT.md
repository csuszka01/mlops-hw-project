# Adatszerződés és modellelfogadási szabályok

Az oszlopok jelentését az `DATA_DICTIONARY.md` írja le, ez a dokumentum csak a szabályokat rögzíti.

| Tétel | Érték |
|---|---|
| Séma | `RawMeasurements`, `ModelInput`, `PredictionInput` (`src/mlops_project/schemas.py`, Pandera) |
| Séma verziója | 1.0.0 |
| Elfogadási kritériumok verziója | 1.0.0 (`params.yaml`, `acceptance.criteria_version`) |
| Jelentések | `reports/validation.json`, `reports/gate.json` |

## Adatszerződés

### Mezők

| Oszlop | Típus | Megengedett érték vagy tartomány | Hiányzó érték |
|---|---|---|---|
| `Hour` | egész | 0 és 23 között | nem |
| `Month` | egész | 1 és 12 között | nem |
| `Area_Type` | szöveg | `Urban`, `Suburban`, `Rural` | nem |
| `Road_Type` | szöveg | `Interstate`, `Arterial`, `Collector`, `Local` | nem |
| `Intersection_Type` | szöveg | `4-Way`, `T-Junction`, `Roundabout`, `None` | nem |
| `Road_Condition` | szöveg | `Dry`, `Wet`, `Snowy`, `Icy`, `Standing Water` | nem |
| `Weather` | szöveg | `Clear`, `Rain`, `Snow`, `Fog` | nem |
| `Visibility_m` | tizedes tört | 0 felett, legfeljebb 15 000 | igen |
| `Congestion_Index` | tizedes tört | 0 felett, legfeljebb 100 | nem |
| `Dispatch_Priority` | szöveg | `Standard`, `Medium`, `High` | nem |
| `Actual_Response_Time_min` | tizedes tört | 0 felett, legfeljebb 1 000 | nem |

### Táblaszintű szabályok

- Csak a fenti 11 oszlop szerepelhet, mindegyik egyszer (`strict`).
- Nem lehet két teljesen azonos sor (`no_duplicate_rows`).
- A típusokat a séma az ellenőrzés előtt átalakítja (`coerce`).
- A `ModelInput` ugyanezeket a szabályokat rögzített oszlopsorrenddel követeli meg, a `PredictionInput` pedig ugyanezt a célváltozó nélkül.

### Érvényesítés

- A `validate` fázis hibánál nem nulla kilépési kóddal áll le, a jelentést mindig megírja.
- A `prepare` fázis sikeres jelentés nélkül nem fut le.
- A `predict` elutasított kérésnél nem hívja meg a modellt.

