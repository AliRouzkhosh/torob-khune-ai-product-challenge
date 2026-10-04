# v0.9-E — reviewed corpus classification

All 320 cases are listed below. A cases have frozen executable checks; B/C/D are recorded limitations, not passing tests. The JSON contains original expectations, unsupported fields, canonical checks, and observed failures.

| Class | Count | Meaning |
|---|---:|---|
| A | 170 | Implemented; fixed executable expectations pass |
| B | 45 | Partially implemented |
| C | 78 | Specified/future, no enabled canonical contract |
| D | 27 | Invalid, ambiguous, or incompatible old expectation |

| ID | Class | Utterance | Review |
|---|---|---|---|
| bedroom_exact_01 | A | دوخوابه می‌خوام | All enabled expectations pass with documented canonical projection. |
| bedroom_min_01 | A | حداقل سه خواب لازم دارم | All enabled expectations pass with documented canonical projection. |
| bedroom_allowed_01 | A | یک یا دو خوابه خوبه | All enabled expectations pass with documented canonical projection. |
| bedroom_unset_01 | A | دوخوابه بودن دیگه مهم نیست | All enabled expectations pass with documented canonical projection. |
| area_min_01 | A | حداقل ۹۰ متر باشه | All enabled expectations pass with documented canonical projection. |
| area_range_01 | A | بین ۸۰ تا ۱۱۰ متر می‌خوام | All enabled expectations pass with documented canonical projection. |
| area_soft_01 | C | خیلی بزرگ لازم نیست، جمع و جور باشه | Expected concept has no activated canonical field. Unsupported: area.preference |
| deposit_01 | A | حداکثر ۸۰۰ میلیون ودیعه | All enabled expectations pass with documented canonical projection. |
| rent_01 | A | اجاره بیشتر از ۲۵ میلیون نشه | All enabled expectations pass with documented canonical projection. |
| rent_patch_01 | A | تا ۳۰ میلیون اجاره هم اوکیه | All enabled expectations pass with documented canonical projection. |
| budget_flex_01 | B | برای گزینه خیلی بهتر کمی بالاتر از بودجه هم می‌رم | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| full_deposit_01 | C | رهن کامل ترجیح می‌دم | Expected concept has no activated canonical field. Unsupported: price_conversion |
| convertible_01 | C | قابل تبدیل باشه | Expected concept has no activated canonical field. Unsupported: price_conversion |
| deposit_rent_tradeoff_01 | C | ودیعه بیشتر می‌دم اجاره کمتر باشه | Expected concept has no activated canonical field. Unsupported: price_conversion |
| location_exact_01 | A | فقط ونک باشه | All enabled expectations pass with documented canonical projection. |
| location_nearby_01 | A | نزدیک ونک می‌خوام | All enabled expectations pass with documented canonical projection. |
| location_preferred_01 | C | ترجیحاً یوسف‌آباد | Expected concept has no activated canonical field. Unsupported: desired_location |
| location_unset_01 | A | محله دیگه مهم نیست | All enabled expectations pass with documented canonical projection. |
| workplace_01 | A | حوالی ونک کار می‌کنم | All enabled expectations pass with documented canonical projection. |
| workplace_commute_01 | A | حوالی ونک کار می‌کنم و نزدیک محل کار بودن خیلی مهمه | All enabled expectations pass with documented canonical projection. |
| workplace_reference_exact_01 | A | داخل محل کارم خانه پیدا کن | All enabled expectations pass with documented canonical projection. |
| workplace_reference_nearby_01 | A | اطراف محل کارم هم خوبه | All enabled expectations pass with documented canonical projection. |
| workplace_unknown_01 | A | نزدیک محل کارم باشه | All enabled expectations pass with documented canonical projection. |
| current_location_ref_01 | A | اطرافش هم خوبه | All enabled expectations pass with documented canonical projection. |
| floor_exact_01 | A | طبقه سوم باشه | All enabled expectations pass with documented canonical projection. |
| floor_allowed_01 | A | طبقه دوم یا سوم بهتره | All enabled expectations pass with documented canonical projection. |
| floor_exclude_01 | A | همکف و زیرزمین نه | All enabled expectations pass with documented canonical projection. |
| floor_max_01 | A | بالاتر از طبقه چهار نباشه | All enabled expectations pass with documented canonical projection. |
| age_pref_01 | A | نوساز ترجیح می‌دم | All enabled expectations pass with documented canonical projection. |
| age_required_01 | C | قدیمی اصلاً نمی‌خوام | Expected concept has no activated canonical field. Unsupported: building_age.newer_required |
| renovated_old_01 | A | خونه قدیمی اشکال نداره اگه کامل بازسازی شده باشه | All enabled expectations pass with documented canonical projection. |
| renovation_required_01 | B | قدیمی فقط بازسازی‌شده | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| elevator_required_01 | A | حتماً آسانسور داشته باشه | All enabled expectations pass with documented canonical projection. |
| elevator_ignore_01 | B | بدون آسانسور هم اوکیه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| parking_required_01 | A | پارکینگ الزامیه | All enabled expectations pass with documented canonical projection. |
| parking_ignore_01 | D | ماشین ندارم، پارکینگ لازم نیست | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| parking_count_01 | A | دو تا پارکینگ لازم دارم | All enabled expectations pass with documented canonical projection. |
| parking_nontandem_01 | A | پارکینگ مزاحم نباشه | All enabled expectations pass with documented canonical projection. |
| parking_dedicated_01 | A | پارکینگ اختصاصی و غیرمزاحم می‌خوام | All enabled expectations pass with documented canonical projection. |
| storage_required_01 | A | انباری حتماً داشته باشه | All enabled expectations pass with documented canonical projection. |
| balcony_pref_01 | C | بالکن قابل استفاده برام مهمه | Expected concept has no activated canonical field. Unsupported: balcony.priority, balcony.usable_preferred |
| yard_01 | C | حیاط اختصاصی می‌خوام | Expected concept has no activated canonical field. Unsupported: outdoor |
| roof_garden_01 | C | روف‌گاردن مزیت حساب بشه | Expected concept has no activated canonical field. Unsupported: building_amenities |
| pets_cat_01 | A | گربه دارم، ساختمون باید حیوان خانگی رو قبول کنه | All enabled expectations pass with documented canonical projection. |
| pets_dog_01 | A | سگ کوچیک دارم، پت ممنوع نباشه | All enabled expectations pass with documented canonical projection. |
| pets_unknown_policy_01 | B | حیوان خانگی حتماً مجاز باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: pets.unknown_satisfies_requirement |
| furnished_01 | A | مبله باشه | All enabled expectations pass with documented canonical projection. |
| unfurnished_01 | A | بدون وسایل می‌خوام | All enabled expectations pass with documented canonical projection. |
| semi_furnished_01 | C | نیمه مبله هم قبوله | Expected concept has no activated canonical field. Unsupported: furnishing |
| wardrobe_01 | C | کمد دیواری زیاد می‌خوام | Expected concept has no activated canonical field. Unsupported: appliances |
| dishwasher_01 | C | ماشین ظرفشویی داشته باشه | Expected concept has no activated canonical field. Unsupported: appliances |
| split_ac_01 | A | حتماً کولر گازی داشته باشه | All enabled expectations pass with documented canonical projection. |
| package_pref_01 | A | پکیج ترجیح می‌دم | All enabled expectations pass with documented canonical projection. |
| light_high_01 | A | نور خوب خیلی مهمه | All enabled expectations pass with documented canonical projection. |
| light_negative_01 | A | خونه تاریک نباشه | All enabled expectations pass with documented canonical projection. |
| light_unset_01 | D | نور دیگه مهم نیست | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| quiet_01 | A | محله آروم و کوچه دنج می‌خوام | All enabled expectations pass with documented canonical projection. |
| avoid_main_road_01 | C | بر خیابون اصلی نباشه | Expected concept has no activated canonical field. Unsupported: quietness.avoid_main_street |
| layout_01 | C | خوش نقشه و بدون پرتی باشه | Expected concept has no activated canonical field. Unsupported: layout.priority, layout.avoid_wasted_space |
| large_living_01 | C | سالن بزرگ می‌خوام | Expected concept has no activated canonical field. Unsupported: layout.living_room_size |
| single_unit_01 | A | ترجیحاً تک‌واحدی باشه | All enabled expectations pass with documented canonical projection. |
| max_units_01 | C | در هر طبقه بیشتر از دو واحد نباشه | Expected concept has no activated canonical field. Unsupported: building_density.units_per_floor_max |
| security_01 | A | نگهبانی ۲۴ ساعته برام مهمه | All enabled expectations pass with documented canonical projection. |
| cctv_01 | A | دوربین مداربسته داشته باشه | All enabled expectations pass with documented canonical projection. |
| view_01 | A | ویو باز داشته باشه | All enabled expectations pass with documented canonical projection. |
| privacy_01 | A | مشرف نباشه | All enabled expectations pass with documented canonical projection. |
| elderly_01 | C | برای سالمند می‌خوام، پله زیاد مناسب نیست | Expected concept has no activated canonical field. Unsupported: accessibility.elderly_friendly, accessibility.prefer_lower_floor |
| step_free_01 | A | ورودی بدون پله لازم دارم | All enabled expectations pass with documented canonical projection. |
| wheelchair_01 | A | ویلچر بتونه راحت وارد بشه | All enabled expectations pass with documented canonical projection. |
| elevator_from_parking_01 | A | آسانسور از پارکینگ تا واحد بره | All enabled expectations pass with documented canonical projection. |
| metro_01 | A | پیاده تا مترو برسم | All enabled expectations pass with documented canonical projection. |
| metro_over_parking_01 | B | مترو مهم‌تر از پارکینگه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| highway_01 | B | دسترسی به همت مهمه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: transport_access.target |
| vacant_01 | C | تخلیه باشه | Expected concept has no activated canonical field. Unsupported: availability |
| immediate_01 | C | برای همین ماه می‌خوام | Expected concept has no activated canonical field. Unsupported: availability |
| first_occupancy_01 | C | کلید نخورده باشه | Expected concept has no activated canonical field. Unsupported: availability |
| short_term_01 | C | اجاره چند ماهه می‌خوام | Expected concept has no activated canonical field. Unsupported: lease_terms |
| relative_01 | A | نور از متراژ مهم‌تره | All enabled expectations pass with documented canonical projection. |
| superlative_01 | A | رفت‌وآمد از همه چیز مهم‌تره | All enabled expectations pass with documented canonical projection. |
| conditional_floor_elevator_01 | A | طبقه چهار به بالا فقط اگر آسانسور داشته باشه | All enabled expectations pass with documented canonical projection. |
| conditional_age_elevator_01 | A | نوساز بهتره ولی اگه قدیمیه حتما آسانسور داشته باشه | All enabled expectations pass with documented canonical projection. |
| conditional_parking_commute_01 | A | پارکینگ مهم نیست اگر نزدیک محل کار باشه | All enabled expectations pass with documented canonical projection. |
| conditional_budget_commute_01 | D | تا ۳۰ میلیون اجاره اوکیه ولی فقط اگر خیلی نزدیک محل کار باشه | Conditional expansion/relaxation lacks required prior numeric base in this NEW_SEARCH fixture. |
| fallback_location_01 | A | اول فقط ونک رو بگرد، اگه چیزی نبود اطرافش رو هم ببین | All enabled expectations pass with documented canonical projection. |
| fallback_budget_01 | A | اگه با ۲۵ میلیون چیزی نبود تا ۳۰ میلیون هم برو | All enabled expectations pass with documented canonical projection. |
| fallback_age_01 | A | اول نوسازها، اگه کم بود قدیمی‌های بازسازی‌شده رو هم نشون بده | All enabled expectations pass with documented canonical projection. |
| patch_add_01 | A | حالا آسانسور هم حتما داشته باشه | All enabled expectations pass with documented canonical projection. |
| patch_multi_01 | D | پارکینگ دیگه مهم نیست و تا ۳۰ میلیون اجاره هم اوکیه | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| new_search_replace_01 | A | برای خانواده سه نفره خونه دو یا سه خوابه می‌خوایم. محله آروم و خونه نسبتاً نوساز باشه. انباری و پارکینگ مهمه. | All enabled expectations pass with documented canonical projection. |
| force_new_01 | A | جستجوی جدید: یه خونه یک‌خوابه نزدیک ولیعصر می‌خوام | All enabled expectations pass with documented canonical projection. |
| unknown_parking_count_01 | D | حداقل دو پارکینگ می‌خوام | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: unknown_count |
| seller_claim_01 | D | نورگیر عالی باشه | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: ui_wording |
| colloquial_parking_01 | D | پارکینگ نمیخوام، ماشین ندارم | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| colloquial_light_01 | A | خونه دلگیر و تاریک نباشه | All enabled expectations pass with documented canonical projection. |
| colloquial_quiet_01 | A | یه جای دنج و بی‌سروصدا می‌خوام | All enabled expectations pass with documented canonical projection. |
| colloquial_budget_01 | C | اگه خیلی خوب بود یه ذره بیشترم میدم | Expected concept has no activated canonical field. Unsupported: budget_flexibility |
| colloquial_location_01 | A | نزدیکای ونک باشه | All enabled expectations pass with documented canonical projection. |
| location_exact_02 | A | فقط خود ونک رو می‌خوام | All enabled expectations pass with documented canonical projection. |
| location_exact_03 | A | حتماً داخل یوسف‌آباد باشه | All enabled expectations pass with documented canonical projection. |
| location_exact_04 | A | دقیقاً عباس‌آباد باشه | All enabled expectations pass with documented canonical projection. |
| location_nearby_02 | A | دور و بر میرداماد خوبه | All enabled expectations pass with documented canonical projection. |
| location_nearby_03 | A | یوسف‌آباد یا اطرافش | All enabled expectations pass with documented canonical projection. |
| location_preferred_02 | C | اولویت با ونکه ولی اجباری نیست | Expected concept has no activated canonical field. Unsupported: desired_location |
| location_preferred_03 | C | اگر میرداماد باشه بهتره | Expected concept has no activated canonical field. Unsupported: desired_location |
| location_unset_02 | A | هر جا باشه اوکیه، محله مهم نیست | All enabled expectations pass with documented canonical projection. |
| location_unset_03 | A | محدوده رو بیخیال، بقیه چیزها مهم‌تره | All enabled expectations pass with documented canonical projection. |
| workplace_02 | B | دفترم ونکه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| workplace_03 | B | شرکتم حوالی ولیعصره | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| workplace_04 | B | هر روز برای کار می‌رم میرداماد | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: workplace: unsupported place |
| workplace_05 | B | اداره‌م یوسف‌آباده | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: workplace: unsupported place |
| commute_01 | A | فاصله تا محل کار کم باشه | All enabled expectations pass with documented canonical projection. |
| commute_02 | A | زمان رفت‌وآمد اولویت اولمه | All enabled expectations pass with documented canonical projection. |
| commute_03 | B | با مسیر طولانی مشکلی ندارم | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| deposit_02 | A | پول پیش بیشتر از ۷۰۰ میلیون نشه | All enabled expectations pass with documented canonical projection. |
| deposit_03 | A | سقف رهن ۱ میلیارد | All enabled expectations pass with documented canonical projection. |
| deposit_04 | A | می‌تونم تا ۹۰۰ میلیون پیش بدم | All enabled expectations pass with documented canonical projection. |
| deposit_05 | A | محدودیت ودیعه ندارم | All enabled expectations pass with documented canonical projection. |
| rent_02 | A | سقف اجاره ۲۰ میلیونه | All enabled expectations pass with documented canonical projection. |
| rent_03 | B | ماهانه بیشتر از ۳۵ میلیون ندم | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| rent_04 | A | برای گزینه بهتر تا ۳۰ میلیون اجاره می‌دم | All enabled expectations pass with documented canonical projection. |
| rent_05 | C | اجاره پایین‌تر باشه | Expected concept has no activated canonical field. Unsupported: rent |
| budget_flex_02 | B | بودجه‌م یه کم منعطفه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| budget_flex_03 | B | اگر خیلی خوب بود بیشتر می‌دم | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| budget_flex_04 | A | اصلاً بالاتر از بودجه نمی‌رم | All enabled expectations pass with documented canonical projection. |
| budget_flex_05 | C | تا ۱۰ درصد بیشتر هم اوکیه | Expected concept has no activated canonical field. Unsupported: budget_flexibility |
| price_conversion_01 | C | فقط رهن کامل می‌خوام | Expected concept has no activated canonical field. Unsupported: price_conversion |
| price_conversion_02 | C | بتونم رهن و اجاره رو تبدیل کنم | Expected concept has no activated canonical field. Unsupported: price_conversion |
| price_conversion_03 | C | پیش کمتر باشه اجاره بیشتر مشکلی نیست | Expected concept has no activated canonical field. Unsupported: price_conversion |
| price_conversion_04 | C | قیمت جای صحبت داشته باشه | Expected concept has no activated canonical field. Unsupported: price_conversion |
| bedroom_exact_02 | A | یک خوابه می‌خوام | All enabled expectations pass with documented canonical projection. |
| bedroom_exact_03 | A | سه‌خوابه باشه | All enabled expectations pass with documented canonical projection. |
| bedroom_min_02 | A | سه خواب به بالا | All enabled expectations pass with documented canonical projection. |
| bedroom_max_01 | A | بیشتر از دو خواب لازم ندارم | All enabled expectations pass with documented canonical projection. |
| bedroom_allowed_02 | A | دو یا سه خوابه | All enabled expectations pass with documented canonical projection. |
| bedroom_allowed_03 | A | یک تا دو خواب اوکیه | All enabled expectations pass with documented canonical projection. |
| bedroom_unset_02 | A | هر تعداد اتاق خواب اوکیه | All enabled expectations pass with documented canonical projection. |
| bathroom_01 | C | حداقل دو حمام لازم دارم | Expected concept has no activated canonical field. Unsupported: bathrooms |
| bathroom_02 | C | دو تا سرویس داشته باشه | Expected concept has no activated canonical field. Unsupported: bathrooms |
| bathroom_03 | C | حداقل یک خواب مستر داشته باشه | Expected concept has no activated canonical field. Unsupported: bathrooms |
| bathroom_04 | C | سرویس ایرانی و فرنگی هر دو داشته باشه | Expected concept has no activated canonical field. Unsupported: bathrooms |
| bathroom_05 | C | توالت فرنگی لازمه | Expected concept has no activated canonical field. Unsupported: bathrooms |
| area_min_02 | A | کمتر از ۱۰۰ متر نباشه | All enabled expectations pass with documented canonical projection. |
| area_min_03 | A | ۱۲۰ متر به بالا | All enabled expectations pass with documented canonical projection. |
| area_max_01 | A | حداکثر ۹۰ متر | All enabled expectations pass with documented canonical projection. |
| area_range_02 | A | ۹۰ تا ۱۲۰ متری خوبه | All enabled expectations pass with documented canonical projection. |
| area_soft_02 | A | جادار باشه | All enabled expectations pass with documented canonical projection. |
| area_soft_03 | C | جمع و جور باشه | Expected concept has no activated canonical field. Unsupported: area.preference |
| floor_exact_02 | A | طبقه دوم باشه | All enabled expectations pass with documented canonical projection. |
| floor_allowed_02 | A | طبقه دوم یا سوم | All enabled expectations pass with documented canonical projection. |
| floor_exclude_02 | C | طبقه آخر نمی‌خوام | Expected concept has no activated canonical field. Unsupported: floor.top: building floor count unavailable |
| floor_exclude_03 | A | همکف نباشه | All enabled expectations pass with documented canonical projection. |
| floor_exclude_04 | A | زیرزمین اصلاً نه | All enabled expectations pass with documented canonical projection. |
| floor_pref_01 | C | طبقات بالا ترجیح می‌دم | Expected concept has no activated canonical field. Unsupported: floor.preference |
| floor_pref_02 | C | طبقه پایین بهتره | Expected concept has no activated canonical field. Unsupported: floor.preference |
| building_age_01 | A | ساختمان تازه‌ساز می‌خوام | All enabled expectations pass with documented canonical projection. |
| building_age_02 | A | سن بنا پایین باشه | All enabled expectations pass with documented canonical projection. |
| building_age_03 | A | بیشتر از ۱۰ ساله نباشه | All enabled expectations pass with documented canonical projection. |
| building_age_04 | A | زیر ۵ سال ساخت | All enabled expectations pass with documented canonical projection. |
| building_age_05 | C | سن بنا مهم نیست | Expected concept has no activated canonical field. Unsupported: building_age.preference |
| renovation_01 | A | فول بازسازی باشه | All enabled expectations pass with documented canonical projection. |
| renovation_02 | B | اگه قدیمیه حتماً بازسازی کامل شده باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| renovation_03 | C | خونه بازسازی‌شده ترجیح می‌دم | Expected concept has no activated canonical field. Unsupported: renovation |
| renovation_04 | C | تمیز و به‌روز باشه | Expected concept has no activated canonical field. Unsupported: renovation |
| elevator_01 | A | اسانسور حتما داشته باشه | All enabled expectations pass with documented canonical projection. |
| elevator_02 | A | آسانسور بهتره ولی ضروری نیست | All enabled expectations pass with documented canonical projection. |
| elevator_03 | D | اسانسور لازم نیست | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| parking_01 | A | جای پارک لازمه | All enabled expectations pass with documented canonical projection. |
| parking_02 | D | بدون پارکینگ هم اوکیه | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| parking_03 | A | حداقل دو جای پارک می‌خوام | All enabled expectations pass with documented canonical projection. |
| parking_04 | A | سه پارکینگ لازم دارم | All enabled expectations pass with documented canonical projection. |
| parking_05 | A | پارکینگ سندی باشه | All enabled expectations pass with documented canonical projection. |
| parking_06 | C | پارکینگ مسقف می‌خوام | Expected concept has no activated canonical field. Unsupported: parking.covered |
| parking_07 | A | پارکینگ اختصاصی و غیرمزاحم باشه | All enabled expectations pass with documented canonical projection. |
| storage_01 | B | بدون انباری نمی‌خوام | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| storage_02 | D | انبار لازم ندارم | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| outdoor_01 | C | بالکون می‌خوام | Expected concept has no activated canonical field. Unsupported: balcony.priority |
| outdoor_02 | C | بالکن بزرگ و قابل استفاده باشه | Expected concept has no activated canonical field. Unsupported: balcony.priority, balcony.usable_preferred |
| outdoor_03 | C | تراس بزرگ برام مهمه | Expected concept has no activated canonical field. Unsupported: outdoor |
| outdoor_04 | C | حیاط داشته باشه | Expected concept has no activated canonical field. Unsupported: outdoor |
| outdoor_05 | C | روف گاردن داشته باشه | Expected concept has no activated canonical field. Unsupported: building_amenities |
| pets_01 | A | حیوون خونگی دارم | All enabled expectations pass with documented canonical projection. |
| pets_02 | A | پت دارم، ساختمون باید قبول کنه | All enabled expectations pass with documented canonical projection. |
| pets_03 | A | گربه دارم و پت ممنوع نباشه | All enabled expectations pass with documented canonical projection. |
| pets_04 | A | سگ دارم، حتماً حیوان خانگی مجاز باشه | All enabled expectations pass with documented canonical projection. |
| pets_05 | A | حیوان خانگی برام مهم نیست | All enabled expectations pass with documented canonical projection. |
| furnishing_01 | A | کامل مبله باشه | All enabled expectations pass with documented canonical projection. |
| furnishing_02 | A | فول فرنیش می‌خوام | All enabled expectations pass with documented canonical projection. |
| furnishing_03 | C | نیمه فرنیش هم اوکیه | Expected concept has no activated canonical field. Unsupported: furnishing |
| furnishing_04 | B | خونه خالی می‌خوام | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| furnishing_05 | A | مبله بودن مهم نیست | All enabled expectations pass with documented canonical projection. |
| appliance_01 | C | کمد دیواری داشته باشه | Expected concept has no activated canonical field. Unsupported: appliances |
| appliance_02 | C | کمد سرتاسری ترجیح می‌دم | Expected concept has no activated canonical field. Unsupported: appliances |
| appliance_03 | C | ماشین لباسشویی داشته باشه | Expected concept has no activated canonical field. Unsupported: appliances |
| appliance_04 | C | یخچال و گاز داشته باشه | Expected concept has no activated canonical field. Unsupported: appliances |
| appliance_05 | C | هود و فر مهمه | Expected concept has no activated canonical field. Unsupported: appliances |
| hvac_01 | A | اسپلیت حتماً داشته باشه | All enabled expectations pass with documented canonical projection. |
| hvac_02 | A | کولر آبی هم قبوله | All enabled expectations pass with documented canonical projection. |
| hvac_03 | A | فن کویل ترجیح می‌دم | All enabled expectations pass with documented canonical projection. |
| hvac_04 | A | چیلر برام مهم نیست | All enabled expectations pass with documented canonical projection. |
| hvac_05 | A | شوفاژ داشته باشه | All enabled expectations pass with documented canonical projection. |
| light_01 | A | خونه دلگیر نباشه | All enabled expectations pass with documented canonical projection. |
| light_02 | B | پنجره قدی امتیازه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: natural_light.large_windows_preferred |
| light_03 | A | آفتاب‌گیر باشه | All enabled expectations pass with documented canonical projection. |
| light_04 | D | نورگیری فرقی نداره | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| quiet_02 | A | یه جای بی‌سروصدا می‌خوام | All enabled expectations pass with documented canonical projection. |
| quiet_03 | C | جای پرتردد نمی‌خوام | Expected concept has no activated canonical field. Unsupported: quietness.avoid_high_traffic |
| quiet_04 | A | کوچه خلوت باشه | All enabled expectations pass with documented canonical projection. |
| quiet_05 | D | شلوغی مهم نیست | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| layout_02 | C | فضای پرت نداشته باشه | Expected concept has no activated canonical field. Unsupported: layout.avoid_wasted_space |
| layout_03 | C | چیدمان خوب برام مهمه | Expected concept has no activated canonical field. Unsupported: layout.priority |
| layout_04 | C | اتاق‌ها جادار باشن | Expected concept has no activated canonical field. Unsupported: layout.bedroom_size |
| layout_05 | C | سالن جادار ترجیح می‌دم | Expected concept has no activated canonical field. Unsupported: layout.living_room_size |
| density_01 | A | ساختمان کم‌واحد باشه | All enabled expectations pass with documented canonical projection. |
| density_02 | B | هر طبقه یک واحد می‌خوام | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| density_03 | C | حداکثر دو واحد در هر طبقه | Expected concept has no activated canonical field. Unsupported: building_density.units_per_floor_max |
| density_04 | A | ساختمون شلوغ نمی‌خوام | All enabled expectations pass with documented canonical projection. |
| security_02 | C | ساختمان امن می‌خوام | Expected concept has no activated canonical field. Unsupported: security.priority |
| security_03 | A | سرایدار داشته باشه | All enabled expectations pass with documented canonical projection. |
| security_04 | A | لابی‌من داشته باشه | All enabled expectations pass with documented canonical projection. |
| security_05 | A | نگهبان شبانه روزی لازم دارم | All enabled expectations pass with documented canonical projection. |
| view_02 | A | دید باز مهمه | All enabled expectations pass with documented canonical projection. |
| view_03 | A | ویو کوه امتیاز حساب می‌شه | All enabled expectations pass with documented canonical projection. |
| view_04 | C | پنجره رو به دیوار نباشه | Expected concept has no activated canonical field. Unsupported: view_privacy.avoid_wall_view |
| view_05 | A | حریم خصوصی مهمه، مشرف نباشه | All enabled expectations pass with documented canonical projection. |
| accessibility_01 | C | برای پدر و مادرم می‌خوام، طبقه پایین بهتره | Expected concept has no activated canonical field. Unsupported: accessibility.elderly_friendly, accessibility.prefer_lower_floor |
| accessibility_02 | A | رمپ داشته باشه | All enabled expectations pass with documented canonical projection. |
| accessibility_03 | A | مناسب ویلچر باشه | All enabled expectations pass with documented canonical projection. |
| accessibility_04 | A | پله نخواد | All enabled expectations pass with documented canonical projection. |
| accessibility_05 | A | آسانسور از پارکینگ مستقیم به واحد برسه | All enabled expectations pass with documented canonical projection. |
| transport_01 | A | مترو دم دست باشه | All enabled expectations pass with documented canonical projection. |
| transport_02 | B | نزدیک ایستگاه مترو باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| transport_03 | A | نزدیک بی‌آرتی باشه | All enabled expectations pass with documented canonical projection. |
| transport_04 | B | دسترسی به مدرس برام مهمه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: transport_access.target |
| transport_05 | B | دسترسی به چمران خوب باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: transport_access.target |
| availability_01 | C | خونه خالی باشه | Expected concept has no activated canonical field. Unsupported: availability |
| availability_02 | C | آماده تحویل باشه | Expected concept has no activated canonical field. Unsupported: availability |
| availability_03 | C | اولین سکونت باشه | Expected concept has no activated canonical field. Unsupported: availability |
| lease_01 | C | کوتاه مدت می‌خوام | Expected concept has no activated canonical field. Unsupported: lease_terms |
| lease_02 | C | قرارداد یک ساله یا بیشتر | Expected concept has no activated canonical field. Unsupported: lease_terms |
| lease_03 | C | مدت قرارداد منعطف باشه | Expected concept has no activated canonical field. Unsupported: lease_terms |
| amenity_01 | C | باشگاه داشته باشه | Expected concept has no activated canonical field. Unsupported: building_amenities |
| amenity_02 | C | استخر برام مزیت حساب می‌شه | Expected concept has no activated canonical field. Unsupported: building_amenities |
| amenity_03 | C | سالن اجتماعات داشته باشه | Expected concept has no activated canonical field. Unsupported: building_amenities |
| compound_cond_01 | A | اگر طبقه چهار یا بالاتره حتماً آسانسور داشته باشه | All enabled expectations pass with documented canonical projection. |
| compound_cond_02 | A | خونه قدیمی باشه مشکلی نیست به شرطی که کامل بازسازی شده باشه | All enabled expectations pass with documented canonical projection. |
| compound_cond_03 | C | اگه پارکینگ نداره فقط وقتی قبوله که خیلی نزدیک محل کار باشه | Expected concept has no activated canonical field. Unsupported: conditional |
| compound_cond_04 | B | طبقه بالا دوست دارم ولی بدون آسانسور حداکثر طبقه دوم | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: floor.preference |
| compound_exception_01 | A | نوساز بهتره اما قدیمی بازسازی‌شده هم مشکلی نیست | All enabled expectations pass with documented canonical projection. |
| compound_exception_02 | C | دو خواب ترجیح می‌دم ولی اگه متراژ خیلی خوبه یک خواب هم قبوله | Expected concept has no activated canonical field. Unsupported: bedrooms.preferred, exception |
| compound_relax_01 | A | پارکینگ رو می‌تونم بیخیال شم اگه مترو خیلی نزدیک باشه | All enabled expectations pass with documented canonical projection. |
| compound_relax_02 | D | متراژ کمتر اوکیه اگر رفت‌وآمد خیلی بهتر بشه | Conditional expansion/relaxation lacks required prior numeric base in this NEW_SEARCH fixture. |
| compound_priority_01 | A | نور رو به متراژ ترجیح می‌دم | All enabled expectations pass with documented canonical projection. |
| compound_priority_02 | A | آرامش از نزدیکی به مترو مهم‌تره | All enabled expectations pass with documented canonical projection. |
| compound_priority_03 | A | پارکینگ از همه چی کم‌اهمیت‌تره | All enabled expectations pass with documented canonical projection. |
| compound_add_01 | A | حالا انباری هم حتماً داشته باشه | All enabled expectations pass with documented canonical projection. |
| compound_unset_01 | D | بیخیال نور، بقیه چیزها همون باشه | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| fallback_01 | A | اول خود ونک، اگه نبود نزدیکای ونک رو هم بیار | All enabled expectations pass with documented canonical projection. |
| fallback_02 | A | اول تا ۲۰ میلیون اجاره بگرد، اگه نبود تا ۲۵ هم اوکیه | All enabled expectations pass with documented canonical projection. |
| fallback_03 | A | اول دوخوابه‌ها، اگه کم بود سه خوابه هم نشون بده | All enabled expectations pass with documented canonical projection. |
| fallback_04 | A | اول پارکینگ‌دارها، اگر چیزی نبود بدون پارکینگ هم ببین | All enabled expectations pass with documented canonical projection. |
| fallback_05 | A | اول نوساز، اگه پیدا نشد قدیمی بازسازی‌شده هم بیار | All enabled expectations pass with documented canonical projection. |
| stateful_patch_01 | A | حالا پارکینگ هم مهمه | All enabled expectations pass with documented canonical projection. |
| stateful_patch_02 | D | آسانسور دیگه مهم نیست ولی بقیه همون باشه | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| stateful_context_01 | A | نزدیکش هم خوبه | All enabled expectations pass with documented canonical projection. |
| stateful_context_02 | A | خود محل کارم باشه | All enabled expectations pass with documented canonical projection. |
| stateful_context_03 | B | نزدیک دفترم باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: workplace: unsupported place, workplace: unsupported place |
| stateful_new_01 | B | برای یه نفر خونه یک خوابه نزدیک ولیعصر می‌خوام، مترو هم مهمه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| colloquial_01 | A | یه خونه دو خواب دوروبر ونک میخام | All enabled expectations pass with documented canonical projection. |
| colloquial_02 | A | اسانسور برام واجبه | All enabled expectations pass with documented canonical projection. |
| colloquial_03 | B | پاركينگ زیاد مهم نیس | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| colloquial_04 | A | خونه نورگير و دلباز باشه | All enabled expectations pass with documented canonical projection. |
| colloquial_05 | A | یه جای آروم و خلوت میخوام | All enabled expectations pass with documented canonical projection. |
| colloquial_06 | B | اگه مورد خفن بود یه کم بیشترم میدم | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| colloquial_07 | A | خونه قديمی باشه اوکیه اگه بازسازی شده | All enabled expectations pass with documented canonical projection. |
| colloquial_08 | A | دو تا جای پارک میخوام | All enabled expectations pass with documented canonical projection. |
| colloquial_09 | C | بالکون داشته باشه | Expected concept has no activated canonical field. Unsupported: balcony.priority |
| colloquial_10 | A | پت دارم، ممنوع نباشه | All enabled expectations pass with documented canonical projection. |
| showcase_01 | A | دوخوابه نزدیک ونک می‌خوام، نور خوب باشه، پارکینگ مهمه و آسانسور ترجیحیه | All enabled expectations pass with documented canonical projection. |
| showcase_02 | B | برای خانواده سه نفره دو یا سه خواب می‌خوایم، محله آروم، انباری و پارکینگ مهمه و نوساز بهتره | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| showcase_03 | B | برای سالمند می‌خوام، ورودی بدون پله، آسانسور و طبقه پایین خیلی مهمه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: accessibility.elderly_friendly, accessibility.prefer_lower_floor |
| showcase_04 | B | گربه دارم، خونه دوخوابه می‌خوام و حیوان خانگی حتماً مجاز باشه، بالکن هم مزیت حساب می‌شه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: balcony.priority |
| showcase_05 | B | دو تا پارکینگ غیرمزاحم لازم دارم و ساختمون کم‌واحد و امن ترجیح می‌دم | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: security.priority |
| showcase_06 | B | حداقل ۱۰۰ متر و دو خواب، نور از متراژ مهم‌تره و کوچه شلوغ نباشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| showcase_07 | B | مبله نمی‌خوام، ولی کمد دیواری زیاد و کولر گازی لازم دارم | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: appliances |
| showcase_08 | C | رهن کامل ترجیح می‌دم، ولی اگر قابل تبدیل باشه رهن و اجاره هم قبوله | Expected concept has no activated canonical field. Unsupported: price_conversion |
| showcase_09 | B | طبقه بالا دوست دارم، ولی اگر آسانسور نداره بالاتر از دوم نباشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: floor.preference |
| showcase_10 | A | ویو باز خوبه ولی آرامش محله از ویو مهم‌تره | All enabled expectations pass with documented canonical projection. |
| stateful_patch_03 | D | حالا نور مهم نیست ولی پارکینگ همون‌قدر مهم بمونه | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| stateful_patch_04 | A | این بار فقط خود ونک باشه، بقیه چیزها همون | All enabled expectations pass with documented canonical projection. |
| stateful_patch_05 | A | حالا یک یا دو خواب هم قبوله | All enabled expectations pass with documented canonical projection. |
| stateful_patch_06 | A | ودیعه رو بیخیال ولی اجاره همون ۲۵ بمونه | All enabled expectations pass with documented canonical projection. |
| stateful_patch_07 | D | پارکینگ رو حذف کن و انباری رو حتماً اضافه کن | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| stateful_patch_08 | B | اطرافش هم قبوله ولی خود محله امتیاز بیشتری داشته باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: desired_location.prefer_exact_center |
| stateful_patch_09 | A | حالا تا ۳۵ میلیون اجاره اوکیه، ولی ودیعه قبلی عوض نشه | All enabled expectations pass with documented canonical projection. |
| stateful_patch_10 | A | آسانسور رو ضروری کن ولی طبقه همون شرط قبلی بمونه | All enabled expectations pass with documented canonical projection. |
| negation_01 | D | پارکینگ نداشته باشه هم مهم نیست | v0.2 ignored expectation conflicts with existing canonical low-priority relaxation contract; old tests retained. |
| negation_02 | A | نمی‌خوام همکف باشه | All enabled expectations pass with documented canonical projection. |
| negation_03 | B | خونه تاریک اصلاً نمی‌خوام | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| negation_04 | A | ساختمون شلوغ نباشه | All enabled expectations pass with documented canonical projection. |
| negation_05 | A | پت ممنوع نباشه | All enabled expectations pass with documented canonical projection. |
| negation_06 | B | بر خیابون اصلی نباشه ولی دسترسی خوب داشته باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: quietness.avoid_main_street |
| negation_07 | B | پارکینگ مزاحم نمی‌خوام | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| negation_08 | B | بدون انباری ردش کن | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| location_nuance_01 | B | محل کارم ونکه ولی نمی‌خوام حتماً خود ونک باشه، نزدیکش کافیه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| location_nuance_02 | B | دفترم ولیعصره و ترجیح می‌دم خونه نزدیک محل کار باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| location_nuance_03 | B | ونک کار می‌کنم ولی محله خونه مهم نیست، فقط مسیر کوتاه باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| location_nuance_04 | B | میرداماد کار می‌کنم و خود میرداماد خونه نمی‌خوام، فقط اطرافش | Enabled subset only / supported concept has a phrase or semantic coverage gap. Unsupported: workplace: unsupported place, desired_location.exclude_exact |
| location_nuance_05 | C | نزدیک محل کارم باشه ولی لازم نیست داخل همون محله باشه | Expected concept has no activated canonical field. Unsupported: desired_location |
| location_nuance_06 | C | خود محل کارم نه، یکی دو محله اطرافش خوبه | Expected concept has no activated canonical field. Unsupported: desired_location |
| location_nuance_07 | B | اول نزدیک محل کار، بعد نور مهمه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| location_nuance_08 | B | محله رو آزاد بذار ولی فاصله تا دفتر کم باشه | Enabled subset only / supported concept has a phrase or semantic coverage gap. |
| evidence_policy_01 | D | اگه آگهی چیزی درباره حیوان خانگی نگفته، قطعی حسابش نکن | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: pets.unknown_policy |
| evidence_policy_02 | D | اگه تعداد پارکینگ معلوم نیست، دو پارکینگ فرض نکن | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: parking.unknown_count_policy |
| evidence_policy_03 | D | نورگیر بودن فقط از متن آگهی معلومه، به عنوان ادعا نشون بده | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: natural_light.evidence_policy |
| evidence_policy_04 | D | اگه درباره آسانسور اطلاعات نداریم، نبودنش رو فرض نکن | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: elevator.unknown_policy |
| evidence_policy_05 | D | اگه بازسازی در متن نیومده، بازسازی‌شده حسابش نکن | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: renovation |
| evidence_policy_06 | D | اگر ویلچرپذیری مشخص نیست، گزینه تاییدشده نشون نده | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: accessibility.wheelchair_unknown_policy |
| evidence_policy_07 | D | اگه فاصله دقیق مترو نداریم، کیلومتر جعلی نساز | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: transport_access.distance_policy |
| evidence_policy_08 | D | اگر سرویس دوم معلوم نیست، دو سرویس فرض نکن | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: bathrooms |
| evidence_policy_09 | D | اگر درباره مجاز بودن حیوان خانگی چیزی نوشته نشده، گزینه رو تاییدشده حساب نکن | Policy instruction or UI prose is not a runtime SearchIntent expectation; verified separately by invariant tests. Unsupported: pets.unknown_policy |
