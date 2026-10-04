# KhaneYab Search Language Coverage Report — v0.2

## Summary

- Canonical concepts: **32**
- Phrase-bank concept families: **32**
- Approximate phrase/template entries: **538**
- Regression cases: **320**
- Compound grammar families in spec: **11**
- Conditional rule examples: **6**
- Progressive fallback examples: **3**

## Regression operations

- NEW_SEARCH: **295**
- PATCH: **18**
- CONTEXTUAL_PATCH: **7**

## Regression coverage by category

- `location`: **22**
- `budget`: **20**
- `compound`: **19**
- `stateful`: **18**
- `colloquial`: **15**
- `access_and_availability`: **14**
- `building_features`: **12**
- `parking`: **12**
- `quality`: **12**
- `workplace`: **12**
- `bedrooms`: **11**
- `evidence`: **11**
- `floor`: **11**
- `equipment`: **10**
- `showcase`: **10**
- `accessibility`: **9**
- `area`: **9**
- `building_condition`: **9**
- `fallback`: **8**
- `furnishing`: **8**
- `negation`: **8**
- `outdoor`: **8**
- `pets`: **8**
- `bathrooms`: **5**
- `elevator`: **5**
- `availability`: **3**
- `natural_light`: **3**
- `rental_terms`: **3**
- `storage`: **3**
- `transport_access`: **3**
- `appliances`: **2**
- `building_age`: **2**
- `building_density`: **2**
- `heating_cooling`: **2**
- `layout`: **2**
- `quietness`: **2**
- `renovation`: **2**
- `security`: **2**
- `view_privacy`: **2**
- `lease_terms`: **1**

## What v0.2 adds over v0.1

1. Common Persian colloquial forms and spelling variants such as `میخوام`, `میخام`, `اسانسور`, `پاركينگ`, `بالکون`, and `نورگير`.
2. Tehran rental-market vocabulary such as `رهن کامل`, `قابل تبدیل`, `پارکینگ غیرمزاحم`, `تک واحدی`, `کلید نخورده`, `خوش نقشه`, `بدون پرتی`, and `لابی‌من`.
3. Richer concepts: parking count/type, pets, renovation, accessibility, furnishing, HVAC, building density, security, privacy/view, availability, and lease terms.
4. Harder conversational semantics: conditional requirements, exceptions, conditional relaxations, relative priorities, multi-field patches, contextual references, and staged fallbacks.
5. Evidence-aware cases making explicit that UNKNOWN is not false/yes and listing-text signals remain seller/ad claims.

## Showcase examples now represented

- `طبقه بالا دوست دارم، ولی اگر آسانسور نداره بالاتر از دوم نباشه`
- `دو تا پارکینگ غیرمزاحم لازم دارم و ساختمون کم‌واحد و امن ترجیح می‌دم`
- `گربه دارم، خونه دوخوابه می‌خوام و حیوان خانگی حتماً مجاز باشه`
- `نوساز بهتره اما قدیمی بازسازی‌شده هم مشکلی نیست`
- `پارکینگ رو می‌تونم بیخیال شم اگه مترو خیلی نزدیک باشه`
- `اول خود ونک، اگه نبود نزدیکای ونک رو هم بیار`
- `ونک کار می‌کنم ولی محله خونه مهم نیست، فقط مسیر کوتاه باشه`
- `حالا تا ۳۵ میلیون اجاره اوکیه، ولی ودیعه قبلی عوض نشه`

## Implementation recommendation

Do **not** enable all 32 concepts in one parser rewrite.

Suggested rollout:

1. Shared normalization + matcher utilities.
2. Tier A structured concepts and new phrase variants.
3. Stateful PATCH / NEW_SEARCH regression corpus.
4. Tier B text-evidence extractors.
5. Relative-priority and conditional rule representation.
6. Progressive fallback plans.
7. Tier C sparse concepts only after graceful UNKNOWN handling exists.

Every enabled family should be backed by the regression corpus before it is used in ranking.
