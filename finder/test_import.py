"""Representative schema fixtures below are synthetic test inputs, not downloaded ads."""
import csv
import io
import json
import tempfile
import importlib.util
from unittest import skipUnless
from unittest.mock import patch
from pathlib import Path
from time import perf_counter
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.management import call_command, CommandError
from .importing import bedrooms, money, boolean, enrich, normalize_record, neighborhood, SkipRecord
from .locations import haversine, location_matches, residential_fit, WORKPLACE_ANCHORS
from .models import Listing
from .search import SearchIntent
from .selectors import listings, filter_listings
from .ai import get_ai_service
from .intent import SCENARIOS
from .ranking import score_listing, rank_listings


def sample(**changes):
    row = {'source_id':'test-1', 'cat2_slug':'residential-rent', 'cat3_slug':'apartment-rent',
           'city_slug':'tehran', 'neighborhood_slug':'vanak', 'title':'آگهی آزمایشی؛ داده واقعی نیست',
           'description':'نورگیر عالی؛ کوچه خلوت؛ خوش نقشه؛ نزدیک مترو؛ بازسازی شده',
           'credit_value':'۸۰۰۰۰۰۰۰۰', 'rent_value':'۲۵۰۰۰۰۰۰', 'building_size':'۹۰', 'rooms_count':'دو',
           'construction_year':'۱۳۹۸', 'floor':'3', 'has_parking':True, 'has_elevator':True,
           'has_warehouse':True, 'has_balcony':None, 'is_rebuilt':False,
           'location_latitude':35.7575, 'location_longitude':51.4099, 'location_radius':500}
    row.update(changes)
    return row


class NormalizationTests(SimpleTestCase):
    def test_persian_bedrooms(self):
        for value, expected in [('یک',1),('دو',2),('سه',3),('چهار',4),('پنج',5),('۲',2),('٣',3),('بدون اتاق',0),('',None),('بیشتر از چهار',None)]:
            self.assertEqual(bedrooms(value),expected)

    def test_money_units_and_unknowns(self):
        for value,unit,expected in [('۸۰۰٬۰۰۰٬۰۰۰','toman',800000000),('۲۵ میلیون','toman',25000000),('١.٥ میلیارد','toman',1500000000),('250000000','rial',25000000),('۲۵ میلیون تومان','rial',25000000),('۲۵۰ میلیون ریال','toman',25000000),('NaN','toman',None),('توافقی','toman',None),('-3','toman',None),('0','toman',0)]:
            self.assertEqual(money(value,unit),expected)

    def test_nullable_booleans(self):
        for value,expected in [(True,True),('true',True),('دارد',True),('۱',True),(False,False),('ندارد',False),('',None),(None,None),('maybe',None)]:
            self.assertIs(boolean(value),expected)

    def test_zero_rent_and_unknown_rent(self):
        self.assertEqual(normalize_record(sample(rent_value=0))['monthly_rent'],0)
        self.assertEqual(normalize_record(sample(rent_value=None,rent_mode='رهن کامل'))['monthly_rent'],0)
        with self.assertRaises(SkipRecord): normalize_record(sample(rent_value=None))
        with self.assertRaises(SkipRecord): normalize_record(sample(rent_value=0,credit_value=0))
        with self.assertRaises(SkipRecord): normalize_record(sample(rent_value=1))

    def test_alternative_prices_not_invented(self):
        row=normalize_record(sample(transformed_credit=900000000,transformed_rent=1,transformable_credit=800000000))
        self.assertIsNone(row['alternative_deposit']);self.assertIsNone(row['alternative_rent'])
        self.assertEqual(row['deposit'],800000000)

    def test_missing_signals_and_negated_claims(self):
        result=enrich('برای بازدید تماس بگیرید')
        for key in ('natural_light','quietness','layout_quality','access_quality','renovation_claim'): self.assertIsNone(result[key])
        self.assertEqual(result['evidence'],[])
        self.assertIsNone(enrich('نورگیر نیست')['natural_light'])
        self.assertIsNone(enrich('نیاز به بازسازی دارد')['renovation_claim'])

    def test_phrase_families_and_evidence(self):
        examples={'natural_light':['نور گیر','آفتاب‌گیر','پنجره‌های قدی','روشن','نور طبیعی'],
                  'quietness':['دنج','آروم','ساکت','کوچه خلوت','کم‌تردد'],
                  'layout_quality':['بدون پرتی','بدون فضای پرت','خوش‌نقشه','نقشه عالی'],
                  'access_quality':['دسترسی عالی','نزدیک مترو','BRT','حمل و نقل عمومی'],
                  'renovation_claim':['بازسازی شده','نقاشی شده','نوسازی']}
        for key,phrases in examples.items():
            for phrase in phrases:
                result=enrich(phrase)
                self.assertIsNotNone(result[key],(key,phrase))
                evidence=next(e for e in result['evidence'] if e['factor']==key)
                self.assertEqual(evidence['source'],'listing_text')
                self.assertTrue(evidence['text'])
        result=enrich('کوچه خلوت؛ نورگیر عالی')
        self.assertIn({'factor':'natural_light','text':'نورگیر عالی','source':'listing_text'},result['evidence'])

    def test_audit_detected_noise_and_false_light_match(self):
        self.assertIsNone(enrich('طراحی روشنک تهرانی')['natural_light'])
        for description in ('دنبال چنین اپارتمانی برای اجاره میگردم','فقط جهت تولیدی پوشاک'):
            with self.assertRaises(SkipRecord): normalize_record(sample(description=description))
        with self.assertRaises(SkipRecord): normalize_record(sample(title='دهدخدهدهدخدههد',description='اخخاخااخخادخ'))
        row=normalize_record(sample(credit_value=23000000,rent_value=1000000000))
        self.assertTrue(row['data_conflicts'])
        self.assertEqual(row['monthly_rent'],1000000000)
        self.assertTrue(normalize_record(sample(title='آپارتمان 115 متر',building_size=100))['data_conflicts'])

    def test_year_coordinates_and_neighborhoods(self):
        row=normalize_record(sample(construction_year='قبل از ۱۳۷۰',location_latitude=None))
        self.assertIsNone(row['construction_year']);self.assertIsNone(row['latitude']);self.assertIsNone(row['longitude'])
        self.assertIsNone(normalize_record(sample(location_latitude=99))['latitude'])
        self.assertEqual(neighborhood('یوسف آباد'),'یوسف‌آباد')
        self.assertEqual(neighborhood('unknown-slug'),'unknown-slug')
        self.assertEqual(neighborhood(None),'')

    def test_conflicts_and_stable_identity_images(self):
        row=sample(description='یک اتاق خواب حذف شده است')
        first=normalize_record(row);second=normalize_record(dict(row))
        self.assertTrue(first['data_conflicts'])
        for key in ('id','source_id','image_name'): self.assertEqual(first[key],second[key])
        self.assertGreater(first['id'],1000000)

    def test_haversine(self):
        self.assertEqual(haversine(35.7,51.4,35.7,51.4),0)
        self.assertAlmostEqual(haversine(0,0,0,1),111.195,places=2)
        a,b=WORKPLACE_ANCHORS.values()
        self.assertGreater(haversine(*a,*b),5)
        self.assertLess(haversine(*a,*b),5.2)


@override_settings(DATA_MODE='real')
class ImportIntegrationTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'representative-test.csv'

    def load(self,rows,**options):
        fields=sorted({k for row in rows for k in row})
        with self.path.open('w',encoding='utf8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        output=io.StringIO()
        call_command('import_divar_rentals',source=str(self.path),stdout=output,**options)
        return json.loads(output.getvalue())

    def test_filter_summary_and_idempotent_update(self):
        rows=[sample(),sample(source_id='outside',city_slug='karaj'),sample(source_id='sale',cat3_slug='apartment-sell'),sample(source_id='bad',building_size=None)]
        report=self.load(rows)
        self.assertEqual((report['raw_rows_read'],report['tehran_rows'],report['rental_apartment_rows'],report['imported']),(4,3,2,1))
        self.assertEqual(report['skipped_reasons'],{'other_city':1,'other_category':1,'invalid_area':1})
        self.assertEqual(report['parking_known'],1)
        before=listings().get()
        report=self.load([sample(rent_value=26000000)])
        self.assertEqual(report['updated'],1);self.assertEqual(listings().get().pk,before.pk)
        self.assertEqual(listings().get().monthly_rent,26000000)

    def test_clear_preserves_synthetic_and_failure_is_atomic(self):
        call_command('seed_demo',stdout=io.StringIO())
        self.load([sample(),sample(source_id='second')])
        self.load([sample()],clear=True)
        self.assertEqual(listings().count(),1)
        self.assertEqual(Listing.objects.filter(data_source='synthetic').count(),12)
        with self.assertRaises(CommandError): self.load([sample(rent_value=None)],clear=True)
        self.assertEqual(listings().count(),1)
        with override_settings(DATA_MODE='synthetic'):
            self.assertEqual(listings().count(),12)
            self.assertEqual(self.client.get('/browse/').context['eligible_count'],12)

    def test_unknown_values_do_not_claim_absence_or_break_pages(self):
        self.load([sample(description='',has_parking=None,has_elevator=None,has_warehouse=None,construction_year=None,location_latitude=None)])
        intent=get_ai_service().parse_full_intent(SCENARIOS['a'][1],['ونک'])
        item=score_listing(listings().get(),intent)
        self.assertIsNone(item.distance)
        self.assertFalse(any('پارکینگ ندارد' in r for r in item.tradeoffs))
        self.assertFalse(any('کیلومتر' in r for r in item.reasons+item.tradeoffs))
        light=next(r for r in item.breakdown if r['key']=='natural_light')
        self.assertIsNone(light['fit']);self.assertEqual(light['points'],light['weight']*.5)
        self.client.post('/intent/',{'query':SCENARIOS['a'][1]})
        pk=listings().get().pk
        self.client.post('/compare/toggle/',{'listing':pk})
        for route in ['/browse/','/results/',f'/homes/{pk}/','/compare/']:
            self.assertEqual(self.client.get(route).status_code,200)
        self.assertContains(self.client.get(f'/homes/{pk}/'),'نامشخص')

    def test_exact_nearby_and_unknown_geography(self):
        self.load([sample(),sample(source_id='near',neighborhood_slug='test-near',location_latitude=35.75),sample(source_id='far',neighborhood_slug='test-far',location_latitude=35.5),sample(source_id='unknown',neighborhood_slug='test-unknown',location_latitude=None)])
        intent=SearchIntent();intent.constraints['neighborhoods']=['ونک']
        self.assertEqual(filter_listings(listings(),intent).count(),1)
        intent.constraints['neighborhood_mode']='nearby'
        candidates=list(filter_listings(listings(),intent))
        self.assertEqual(len(candidates),2)
        self.assertTrue(all(location_matches(r,intent) for r in candidates))
        self.assertEqual(len(rank_listings(listings(),intent)),2)
        target=listings().get(neighborhood='ونک');near=listings().get(neighborhood='test-near')
        self.assertGreater(residential_fit(target,intent),residential_fit(near,intent))

    def test_conversational_flows_and_utilities_with_imported_test_rows(self):
        self.load([sample(),sample(source_id='near',neighborhood_slug='yousef-abad',location_latitude=35.745,has_parking=False),sample(source_id='single',neighborhood_slug='valiasr',rooms_count='یک',rent_value=19000000,location_latitude=35.7117)])
        service=get_ai_service()
        for _,query in SCENARIOS.values():
            intent=service.parse_full_intent(query,['ونک','ولیعصر','یوسف‌آباد'])
            self.assertTrue(rank_listings(listings(),intent))
        self.client.post('/browse/',{'action':'search','q':'خونه دوخوابه نزدیک ونک، نور خوب و پارکینگ مهمه'})
        self.client.post('/results/',{'update':'حالا آسانسور هم حتما داشته باشه'})
        state=SearchIntent(**self.client.session['intent'])
        self.assertEqual(state.constraints['bedrooms']['value'],2)
        self.assertIn('elevator',state.constraints['required_amenities'])
        self.client.post('/results/',{'update':'پارکینگ دیگه مهم نیست و تا ۳۰ میلیون اجاره هم اوکیه'})
        self.assertEqual(self.client.session['intent']['preferences']['parking'],'low')
        self.client.post('/results/',{'update':'حتما داخل ونک باشه'})
        self.client.post('/results/',{'update':SCENARIOS['c'][1]})
        self.assertFalse(self.client.session['intent']['constraints']['neighborhoods'])
        self.client.post('/results/',{'update':SCENARIOS['a'][1],'operation':'NEW_SEARCH'})
        self.client.post('/results/',{'update':'داخل محل کارم خانه پیدا کن'})
        self.assertEqual(self.client.session['intent']['constraints']['neighborhoods'],['ونک'])
        pk=listings().first().pk
        self.client.post('/saved/toggle/',{'listing':pk})
        self.client.post('/compare/toggle/',{'listing':pk})
        response=self.client.post('/saved/toggle/',{'listing':pk},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json()['id'],str(pk))
        self.client.post('/saved/toggle/',{'listing':pk})
        self.assertIn(pk,self.client.session['saved_listing_ids'])
        self.assertEqual([r.listing.pk for r in self.client.get('/saved/').context['items']],[pk])
        self.assertEqual(self.client.get('/compare/').status_code,200)

    def test_modes_do_not_mix_bookmarks_or_comparison_limits(self):
        call_command('seed_demo',stdout=io.StringIO())
        self.load([sample(source_id=str(i)) for i in range(4)])
        session=self.client.session;session['comparison']=[1,2,3];session['saved_listing_ids']=[1];session.save()
        for pk in listings().values_list('pk',flat=True): self.client.post('/compare/toggle/',{'listing':pk})
        self.assertEqual(self.client.get('/compare/').context['comparison_count'],3)
        self.assertEqual(self.client.get('/saved/').context['saved_count'],0)
        self.assertEqual(self.client.get('/homes/1/').status_code,404)
        with override_settings(DATA_MODE='synthetic'):
            self.assertEqual(self.client.get('/compare/').context['comparison_count'],3)
            self.assertEqual(self.client.get('/saved/').context['saved_count'],1)

    def test_bounded_3000_row_import_and_render_cap(self):
        # Scale check on generated test records in the temporary test DB, never real inventory.
        started=perf_counter()
        report=self.load([sample(source_id=f'scale-{i}') for i in range(3002)],limit=3000)
        self.assertEqual(report['imported'],3000);self.assertEqual(report['raw_rows_read'],3000)
        response=self.client.get('/browse/')
        self.assertEqual(response.context['eligible_count'],3000)
        self.assertEqual(len(response.context['items']),60)
        self.assertContains(response,'نمایش ۶۰ خانه')
        print(f'3000 representative test rows: import + browse {perf_counter()-started:.2f}s')

    def test_scan_cap_duplicate_and_bad_source(self):
        report=self.load([sample(),sample(),sample(source_id='second')],max_rows=2)
        self.assertEqual(report['imported'],1);self.assertEqual(report['skipped_reasons']['duplicate'],1)
        self.assertTrue(report['scan_cap_reached'])
        self.path.write_text('wrong,columns\n1,2\n',encoding='utf8')
        with self.assertRaises(CommandError): call_command('import_divar_rentals',source=str(self.path),clear=True)
        self.assertEqual(listings().count(),1)


    def test_missing_parquet_dependency_has_actionable_error(self):
        parquet=self.path.with_suffix('.parquet');parquet.write_bytes(b'')
        with patch.dict('sys.modules',{'pyarrow':None}):
            with self.assertRaisesMessage(CommandError,'requirements-import.txt'):
                call_command('import_divar_rentals',source=str(parquet))
        self.assertEqual(listings().count(),0)

    @skipUnless(importlib.util.find_spec('pyarrow'), 'Optional pyarrow is unavailable; network installation was unavailable.')
    def test_parquet_roundtrip_matches_csv(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        row=sample();self.load([row]);first=listings().get()
        path=self.path.with_suffix('.parquet')
        pq.write_table(pa.Table.from_pylist([row]),path)
        call_command('import_divar_rentals',source=str(path),stdout=io.StringIO())
        self.assertEqual(listings().count(),1)
        self.assertEqual(listings().get().pk,first.pk)
        self.assertEqual(listings().get().evidence,first.evidence)
