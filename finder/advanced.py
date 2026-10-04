"""Shared form projection and sparse, validated edits of SearchIntent."""
from copy import deepcopy
from decimal import Decimal
from django import forms
from .forms import PrecisionFilters
from .location_registry import workplace_choices, workplace_label, display_location
from .intent import LABELS
from .search import SearchIntent, filter_initial, AMENITIES
from .patches import IntentPatch
from .compound import logic_labels, clear_related_logic
from .ranking import money, fa
from .calendar import current_jalali_year

PRIORITY_CHOICES=[('ignored','مهم نیست'),('medium','متوسط'),('high','مهم'),('very_high','خیلی مهم')]
GROUPS=[('location','موقعیت و رفت‌وآمد', ['neighborhood','neighborhood_scope','excluded_neighborhoods','workplace','commute']),
        ('budget','بودجه',['max_deposit','max_rent','flexibility','full_deposit','convertible']),
        ('home','مشخصات خانه',['area_min','area_max','bedrooms','floor_mode','floor_value','floor_excluded','age_preset','construction_year_min','renovation_required']),
        ('amenities','پارکینگ و امکانات',['parking','parking_count_min','parking_non_tandem_required','parking_dedicated_required','elevator','storage','balcony']),
        ('lifestyle','سبک زندگی',['pet_policy','furnishing','natural_light','quietness','building_density','security_required']),
        ('hvac','تأسیسات',['hvac_required'])]

def initial_values(intent):
    c=intent.constraints
    result=filter_initial(intent)
    result.update(neighborhood_scope=c['neighborhood_mode'],workplace=intent.work_location,commute=intent.location_priority,
                  flexibility=intent.budget_flexibility,full_deposit=c['full_deposit'],convertible=c['convertible'],
                  area_min=c['area']['min'],area_max=c['area']['max'],floor_mode=c['floor']['mode'],floor_value=c['floor']['value'],
                  floor_excluded=c['floor']['excluded'],parking='required' if 'parking' in c['required_amenities'] else 'irrelevant' if intent.preferences['parking']=='ignored' else 'preferred')
    # Money uses decimal millions, preserving sub-million canonical values on a no-op.
    for k in ('max_deposit','max_rent'): result[k]=None if c[k] is None else Decimal(c[k])/Decimal(1_000_000)
    for k in ('construction_year_min','renovation_required','parking_count_min','parking_non_tandem_required','parking_dedicated_required','pet_policy','furnishing','building_density','security_required','hvac_required'):result[k]=deepcopy(c[k])
    for k in ('natural_light','quietness'):result[k]=intent.preferences[k]
    for k in ('elevator','storage','balcony'):result[k]=k in c['required_amenities']
    result['floor_value']=','.join(map(str,c['floor']['value'])) if c['floor']['mode']=='allowed' else '' if c['floor']['value'] is None else str(c['floor']['value'])
    # Multiple residence choices are preserved and shown rather than silently collapsed.
    result['neighborhood']='|'.join(c['neighborhoods'])
    result['excluded_neighborhoods']=c['excluded_neighborhoods']
    year=c['construction_year_min']
    result['age_preset']='any' if year is None else next((str(age) for age in (3,5,10) if year==current_jalali_year()-age),'custom')
    return result

class AdvancedFilters(PrecisionFilters):
    excluded_neighborhoods=forms.MultipleChoiceField(label='محله‌های حذف‌شده',required=False,help_text='انتخاب‌های فعلی؛ برای آزاد کردن محدوده، انتخاب را بردار.',widget=forms.CheckboxSelectMultiple)
    workplace=forms.ChoiceField(label='محل کار',required=False,help_text='برای محاسبه نزدیکی و اولویت رفت‌وآمد')
    commute=forms.ChoiceField(label='اهمیت رفت‌وآمد',choices=PRIORITY_CHOICES+[('low','کم')])
    flexibility=forms.ChoiceField(label='انعطاف بودجه',choices=[('none','بدون افزایش'),('medium','تا ۲۰٪'),('flexible','تا ۴۰٪')])
    full_deposit=forms.BooleanField(label='رهن کامل',required=False)
    convertible=forms.BooleanField(label='قابل تبدیل (مبلغ جایگزین در آگهی)',required=False)
    area_min=forms.IntegerField(label='حداقل متراژ',min_value=10,max_value=1500,required=False)
    area_max=forms.IntegerField(label='حداکثر متراژ',min_value=10,max_value=1500,required=False)
    floor_mode=forms.ChoiceField(label='محدوده طبقه',choices=[('any','فرقی ندارد'),('exact','دقیقاً'),('min','از این طبقه به بالا'),('max','تا این طبقه'),('allowed','این طبقه‌ها')])
    floor_value=forms.CharField(label='طبقه (برای چند طبقه با ویرگول جدا کن)',required=False,max_length=80)
    floor_excluded=forms.MultipleChoiceField(label='طبقه‌های نامناسب',required=False,choices=[('ground','همکف'),('basement','زیرزمین')],widget=forms.CheckboxSelectMultiple)
    age_preset=forms.ChoiceField(label='سن بنا',choices=[('any','فرقی ندارد'),('3','نوساز — حداکثر ۳ سال'),('5','تا ۵ سال'),('10','تا ۱۰ سال'),('custom','سفارشی')])
    construction_year_min=forms.IntegerField(label='ساخت از سال (شمسی)',min_value=1300,required=False)
    renovation_required=forms.BooleanField(label='بازسازی‌شده ضروری',required=False)
    parking=forms.ChoiceField(label='پارکینگ',choices=[('required','ضروری'),('preferred','ترجیحی'),('irrelevant','مهم نیست')])
    parking_count_min=forms.IntegerField(label='حداقل تعداد پارکینگ',min_value=1,max_value=5,required=False)
    parking_non_tandem_required=forms.BooleanField(label='پارکینگ غیرمزاحم ضروری',required=False)
    parking_dedicated_required=forms.BooleanField(label='پارکینگ اختصاصی ضروری',required=False)
    elevator=forms.BooleanField(label='آسانسور ضروری',required=False)
    storage=forms.BooleanField(label='انباری ضروری',required=False)
    balcony=forms.BooleanField(label='بالکن ضروری',required=False)
    pet_policy=forms.ChoiceField(label='حیوان خانگی',choices=[('any','بدون الزام'),('allowed','مجاز؛ فقط شواهد مثبت آگهی')])
    furnishing=forms.ChoiceField(label='مبله',choices=[('any','بدون الزام'),('furnished','مبله ضروری'),('unfurnished','غیرمبله ضروری')])
    natural_light=forms.ChoiceField(label='نور',choices=list(LABELS.items()))
    quietness=forms.ChoiceField(label='آرامش',choices=list(LABELS.items()))
    building_density=forms.ChoiceField(label='تعداد واحد',choices=[('any','بدون الزام'),('single_unit','تک‌واحدی'),('low_density','کم‌واحد')])
    security_required=forms.MultipleChoiceField(label='امنیت و خدمات ضروری',required=False,choices=[('security_24h','نگهبانی ۲۴ ساعته'),('cctv','دوربین مداربسته'),('concierge','سرایدار'),('lobby','لابی')],widget=forms.CheckboxSelectMultiple)
    hvac_required=forms.MultipleChoiceField(label='تأسیسات ضروری',required=False,choices=[('package_heating','پکیج'),('radiator','رادیاتور'),('split_ac','کولر گازی'),('water_cooler','کولر آبی'),('fan_coil','فن‌کویل'),('chiller','چیلر')],widget=forms.CheckboxSelectMultiple)

    def __init__(self,*args,intent,neighborhoods=(),**kwargs):
        self.intent=intent
        super().__init__(*args,initial=initial_values(intent),neighborhoods=neighborhoods,prefix='advanced',**kwargs)
        self.fields.pop('amenities')
        self.fields['construction_year_min'].max_value=current_jalali_year()
        self.fields['construction_year_min'].widget.attrs['max']=current_jalali_year()
        self.fields['workplace'].choices=workplace_choices()
        self.fields['excluded_neighborhoods'].choices=[(name,display_location(name)) for name in intent.constraints['excluded_neighborhoods']]
        if not intent.constraints['excluded_neighborhoods']:self.fields['excluded_neighborhoods'].help_text='محله‌ای حذف نشده.'
        self.fields['neighborhood_scope'].choices=[('exact','داخل محله'),('nearby','نزدیک محله'),('preferred','ترجیحی')]
        current=self.initial['neighborhood']
        if current and current not in dict(self.fields['neighborhood'].choices):self.fields['neighborhood'].choices.append((current,'، '.join(display_location(n) for n in intent.constraints['neighborhoods'])))
        # Parent dynamic bedroom choices read the prefixed bound key only here.
        bed=self.initial['bedrooms']
        if bed and bed not in dict(self.fields['bedrooms'].choices):self.fields['bedrooms'].choices.append((bed,intent.bedroom_label))
        for k in ('max_deposit','max_rent'):
            self.fields[k]=forms.DecimalField(label=self.fields[k].label,min_value=0,max_value=100000,decimal_places=6,required=False)
        for name,field in self.fields.items():
            if not isinstance(field.widget,forms.CheckboxSelectMultiple): field.widget.attrs['class']='advanced-input'
            else:field.widget.attrs['aria-labelledby']=self[name].auto_id+'_label'
            if field.help_text:field.widget.attrs['aria-describedby']=self[name].auto_id+'_help'
        self.groups=[(key,label,[self[n] for n in names]) for key,label,names in GROUPS]
        simple={'neighborhood','max_deposit','max_rent','bedrooms','parking','elevator','storage','balcony'}
        self.simple_groups=[(key,label,[self[n] for n in names if n in simple]) for key,label,names in GROUPS if set(names)&simple]
        self.advanced_groups=[(key,label,[self[n] for n in names if n not in simple]) for key,label,names in GROUPS if set(names)-simple]

    def clean(self):
        d=super().clean()
        if d.get('construction_year_min') is not None and d['construction_year_min']>current_jalali_year():self.add_error('construction_year_min','سال ساخت نمی‌تواند از سال جاری بیشتر باشد.')
        if d.get('age_preset')=='custom' and d.get('construction_year_min') is None:self.add_error('construction_year_min','برای سن سفارشی، حداقل سال ساخت را وارد کن.')
        if d.get('area_min') is not None and d.get('area_max') is not None and d['area_min']>d['area_max']:self.add_error('area_max','حداکثر متراژ باید از حداقل کمتر نباشد.')
        try:
            value=d.get('floor_value','').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹،','0123456789,'))
            floor_values=[int(x.strip()) for x in value.split(',') if x.strip()]
            if d.get('floor_mode')!='any' and (not floor_values or any(not -5<=n<=100 for n in floor_values) or (d.get('floor_mode')!='allowed' and len(floor_values)!=1)):raise ValueError()
            d['_floor']={'mode':d.get('floor_mode','any'),'value':None if d.get('floor_mode')=='any' else sorted(set(floor_values)) if d.get('floor_mode')=='allowed' else floor_values[0],'excluded':d.get('floor_excluded',[])}
        except ValueError:self.add_error('floor_value','طبقه را به صورت عدد وارد کن؛ مثلاً ۲،۳.')
        return d

    def apply(self):
        """Serialize changed form fields as a sparse patch; preserve untouched intent."""
        if not self.is_valid():raise ValueError('فیلتر معتبر نیست.')
        current=self.intent;c=self.cleaned_data;sets={}
        changed=set(self.changed_data)
        def put(path,value):
            group,key=path.split('.')
            if getattr(current,group)[key]!=value:sets[path]=value
        for k in ('max_deposit','max_rent'):
            if k in changed:put('constraints.'+k,None if c[k] is None else int(c[k]*1_000_000));put('targets.'+k[4:],None if c[k] is None else int(c[k]*1_000_000))
        if 'neighborhood' in changed:put('constraints.neighborhoods',c['neighborhood'].split('|') if c['neighborhood'] else [])
        if 'neighborhood_scope' in changed:put('constraints.neighborhood_mode',c['neighborhood_scope'])
        if 'excluded_neighborhoods' in changed:put('constraints.excluded_neighborhoods',c['excluded_neighborhoods'])
        if 'workplace' in changed:put('context.workplace',c['workplace'] or 'none')
        if 'flexibility' in changed:put('targets.flexibility',c['flexibility'])
        for k in ('commute','natural_light','quietness'):
            if k in changed:put('preferences.'+k,c[k])
        if changed & {'area_min','area_max'}:put('constraints.area',{'min':c['area_min'],'max':c['area_max']})
        if changed & {'floor_mode','floor_value','floor_excluded'}:put('constraints.floor',c['_floor'])
        if 'bedrooms' in changed:
            b=c['bedrooms'];value=None if not b else list(map(int,b[7:].split(','))) if b.startswith('allowed') else int(b[3:]) if b.startswith(('min','max')) else int(b)
            put('constraints.bedrooms',{'mode':'any' if not b else 'allowed' if b.startswith('allowed') else b[:3] if b.startswith(('min','max')) else 'exact','value':value})
        for k in ('full_deposit','convertible','construction_year_min','renovation_required','parking_count_min','parking_non_tandem_required','parking_dedicated_required','pet_policy','furnishing','building_density','security_required','hvac_required'):
            if k in changed:put('constraints.'+k,c[k])
        if 'age_preset' in changed:
            put('constraints.construction_year_min',None if c['age_preset']=='any' else c['construction_year_min'] if c['age_preset']=='custom' else current_jalali_year()-int(c['age_preset']))
        amenities=current.constraints['required_amenities'].copy()
        for k in ('parking','elevator','storage','balcony'):
            if k not in changed:continue
            required=c[k]=='required' if k=='parking' else c[k]
            amenities=[a for a in amenities if a!=k]+([k] if required else [])
            if k!='balcony':put('preferences.'+k,'high' if required else 'medium' if k=='parking' and c[k]=='preferred' else 'ignored')
            if k=='parking' and c[k]=='irrelevant':
                for field in ('parking_count_min','parking_non_tandem_required','parking_dedicated_required'):put('constraints.'+field,None if field=='parking_count_min' else False)
                for field in ('parking_non_tandem','parking_dedicated'):put('evidence_preferences.'+field,'ignored')
        put('constraints.required_amenities',amenities)
        # Same validated patch contract as NLP; cleanup is scoped to explicitly changed fields.
        result=IntentPatch(set=sets,source='filter').merge(current)
        clear_related_logic(result,set(sets))
        result.__post_init__()
        return result

def ui_context(intent,form=None):
    form=form or AdvancedFilters(intent=intent)
    rules=[]
    for group in intent.logic:
        for i,rule in enumerate(intent.logic[group]):
            isolated=intent.copy();isolated.logic={k:[] for k in intent.logic};isolated.logic[group]=[rule]
            rules.append({'key':f'{group}:{i}','label':'؛ '.join(logic_labels(isolated)).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))})
    budget=[label+' تا '+money(intent.constraints[key]) for key,label in [('max_rent','اجاره'),('max_deposit','ودیعه')] if intent.constraints[key] is not None]
    if intent.constraints['full_deposit']:budget.append('رهن کامل')
    if intent.constraints['convertible']:budget.append('قابل تبدیل')
    amenities=[AMENITIES[k]+' ضروری' for k in intent.constraints['required_amenities']]
    preferred_amenities=[AMENITIES[k]+': '+LABELS[intent.preferences[k]] for k in ('parking','elevator','storage') if k not in intent.constraints['required_amenities'] and intent.preferences[k] in ('medium','high','very_high')]
    parking=[s for s in intent.structured_constraint_labels if 'پارکینگ' in s]
    home=[s for s in intent.structured_constraint_labels if any(x in s for x in ('متر','طبقه','ساخت','بازسازی'))]
    excluded=[s for s in intent.structured_constraint_labels if s.startswith('به‌جز')]
    other=[s for s in intent.structured_constraint_labels if s not in parking+home+excluded]
    from .search import active_filter_chips
    active=active_filter_chips(intent)
    return {'advanced_form':form,'advanced_rules':rules,'workplace_choices':workplace_choices(),
            'filter_count':len(active),'visible_filter_chips':active[:4],'extra_filter_count':max(0,len(active)-4),'dialog_filter_chips':active,
            'quick_budget':' · '.join(budget) or 'بدون محدودیت','quick_amenities':fa(len(amenities)+len(parking)+len(other))+' الزام' if amenities or parking or other else fa(len(preferred_amenities))+' ترجیح' if preferred_amenities else 'بدون الزام',
            'criteria_groups':[('home','خانه',[intent.bedroom_label]+home+[label+': '+LABELS[intent.preferences[k]] for k,label in [('building_age','نوساز بودن'),('area','متراژ')] if intent.preferences[k] in ('medium','high','very_high')]),('budget','بودجه',budget or ['بدون سقف']),('location','موقعیت و رفت‌وآمد',[intent.residential_label,'محل کار: '+workplace_label(intent.work_location),'رفت‌وآمد: '+LABELS[intent.location_priority]]+excluded),('amenities','امکانات',amenities+parking+preferred_amenities),('lifestyle','سبک زندگی و تأسیسات',other+['نور: '+LABELS[intent.preferences['natural_light']],'آرامش: '+LABELS[intent.preferences['quietness']]]+intent.evidence_preference_labels),('logic','منطق انتخاب',intent.logic_labels)]}

def remove_logic(intent,key):
    group,index=key.split(':');index=int(index)
    if group not in intent.logic or not 0<=index<len(intent.logic[group]):raise ValueError('منطق معتبر نیست.')
    rows=deepcopy(intent.logic[group]);rows.pop(index)
    return IntentPatch(set={'logic.'+group:rows},source='filter').merge(intent)

def reset_filters():
    result=SearchIntent();result.preferences.update({k:'ignored' for k in result.preferences});result.metadata['source']='filter'
    return result
