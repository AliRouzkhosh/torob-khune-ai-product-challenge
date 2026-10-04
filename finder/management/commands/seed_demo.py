from django.core.management.base import BaseCommand
from finder.models import Listing

# Curated synthetic ads. Distances are illustrative straight-line proxies, not routes.
ROWS = [
    ('دوخوابه روشن با بالکن', 'یوسف‌آباد', 800, 25, 92, 2, 3, 1395, True, True, True, True, 3.8, 2.5, .98, .78),
    ('دوخوابه نزدیک میدان ونک', 'ونک', 800, 25, 86, 2, 2, 1394, False, True, True, False, .4, 6.1, .82, .68),
    ('نور جنوب، فضای بازتر', 'شیخ بهایی', 850, 27, 105, 2, 4, 1398, True, True, True, True, 2.0, 7.1, 1.0, .8),
    ('دوخوابه اقتصادی', 'جنت‌آباد', 550, 18, 90, 2, 2, 1390, True, False, True, False, 7.8, 10.8, .65, .82),
    ('نوساز با امکانات کامل', 'ملاصدرا', 1100, 35, 116, 2, 5, 1403, True, True, True, True, 1.5, 6.4, .92, .85),
    ('بازسازی‌شده با آشپزخانه باز', 'امیرآباد', 700, 22, 96, 2, 1, 1387, True, False, True, True, 4.1, 3.3, .84, .76),
    ('سه‌خوابه برای خانواده', 'پاسداران', 900, 28, 125, 3, 3, 1400, True, True, True, True, 5.4, 9.2, .88, .95),
    ('یک‌خوابه جمع‌وجور', 'ولیعصر', 450, 19, 58, 1, 4, 1397, False, True, False, False, 6.2, .6, .8, .55),
    ('دوخوابه در کوچه آرام', 'سعادت‌آباد', 780, 24, 100, 2, 3, 1399, True, True, True, False, 5.8, 9.8, .78, .94),
    ('دوخوابه با اطلاعات مبهم', 'عباس‌آباد', 650, 20, 84, 2, 2, 1393, True, True, False, False, 3.2, 4.3, .86, .7),
    ('دوخوابه با ودیعه کمتر', 'تهرانپارس', 500, 17, 80, 2, 3, 1392, False, True, True, False, 12.0, 13.5, .5, .5),
    ('یک‌خوابه نزدیک مترو', 'فاطمی', 500, 18, 64, 1, 2, 1398, False, True, True, True, 5.0, 1.4, .74, .72),
]


class Command(BaseCommand):
    help = 'Load or update the 12 synthetic demo homes (idempotent).'

    def handle(self, *args, **options):
        for index, row in enumerate(ROWS, 1):
            title, neighborhood, deposit, rent, area, beds, floor, year, parking, elevator, storage, balcony, vanak, valiasr, light, quiet = row
            evidence = [] if index == 11 else [
                {'factor': 'natural_light', 'text': ('پنجره شرقی پذیرایی و نور صبح' if index == 2 else 'پنجره‌های بزرگ و نور جنوب') if light >= .8 else 'نورگیری معمولی'},
                {'factor': 'quietness', 'text': 'کوچه کم‌رفت‌وآمد و آرام' if quiet >= .8 else 'دسترسی به خیابان اصلی'},
            ]
            conflicts = ['عنوان آگهی پارکینگ دارد، اما در توضیحات «بدون پارکینگ» نوشته شده است.'] if index == 10 else []
            Listing.objects.update_or_create(id=index, defaults={
                'data_source': 'synthetic', 'source_id': None,
                'title': title, 'neighborhood': neighborhood,
                'description': '؛ '.join(e['text'] for e in evidence) + ('؛ بازسازی کامل در سال ۱۴۰۲' if index == 6 else '') if evidence else 'آپارتمان مناسب، جهت بازدید تماس بگیرید.',
                'deposit': deposit * 1_000_000, 'monthly_rent': rent * 1_000_000,
                'alternative_deposit': (deposit + 150) * 1_000_000 if index in (1, 3, 7) else None,
                'alternative_rent': (rent - 5) * 1_000_000 if index in (1, 3, 7) else None,
                'area_m2': area, 'bedrooms': beds, 'floor': floor, 'construction_year': year,
                'renovated': index == 6, 'parking': parking, 'elevator': elevator, 'storage': storage, 'balcony': balcony,
                'distance_to_work_km': vanak, 'distances': {'vanak': vanak, 'valiasr': valiasr},
                'natural_light': light, 'quietness': quiet, 'layout_quality': .85 if area >= 90 else .65,
                'access_quality': .8 if elevator else .4, 'evidence': evidence, 'data_conflicts': conflicts,
                'image_name': f'home-{(index - 1) % 10 + 1:02}.jpg',
            })
        self.stdout.write(self.style.SUCCESS('12 demo homes loaded.'))
