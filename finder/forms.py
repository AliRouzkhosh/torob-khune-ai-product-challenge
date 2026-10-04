from django import forms


class PrecisionFilters(forms.Form):
    neighborhood = forms.ChoiceField(label='محله', required=False)
    neighborhood_scope = forms.ChoiceField(label='محدوده محله', choices=[('exact','فقط این محله'),('nearby','این محله و اطراف'),('preferred','ترجیحی')], required=False)
    max_deposit = forms.IntegerField(label='سقف ودیعه (میلیون تومان)', min_value=0, max_value=100000, required=False, widget=forms.NumberInput(attrs={'inputmode': 'numeric'}))
    max_rent = forms.IntegerField(label='سقف اجاره (میلیون تومان)', min_value=0, max_value=100000, required=False, widget=forms.NumberInput(attrs={'inputmode': 'numeric'}))
    bedrooms = forms.ChoiceField(label='اتاق خواب', choices=[('', 'فرقی ندارد'), ('1', '۱ خواب'), ('2', '۲ خواب'), ('3', '۳ خواب'), ('min4', '۴+ خواب')], required=False)
    amenities = forms.MultipleChoiceField(label='امکانات ضروری', choices=[('parking', 'پارکینگ'), ('elevator', 'آسانسور'), ('storage', 'انباری'), ('balcony', 'بالکن')], required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, neighborhoods=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['neighborhood'].choices = [('', 'همه محله‌ها')] + [(name, name) for name in neighborhoods]
        from .location_registry import display_location
        prior=self.initial.get('neighborhood')
        if prior and prior not in dict(self.fields['neighborhood'].choices):self.fields['neighborhood'].choices.append((prior,'، '.join(display_location(n) for n in prior.split('|'))))
        current = self.data.get('bedrooms') if self.is_bound else self.initial.get('bedrooms')
        if current and current.startswith('min') and current[3:] in ('1','2','3','4','5'):
            self.fields['bedrooms'].choices.append((current, 'حداقل ' + current[3:].translate(str.maketrans('12345', '۱۲۳۴۵')) + ' خواب'))
        if current and current.startswith('max') and current[3:] in ('1','2','3','4','5'):
            self.fields['bedrooms'].choices.append((current, 'حداکثر ' + current[3:].translate(str.maketrans('12345', '۱۲۳۴۵')) + ' خواب'))

        if current and current.startswith('allowed'):
            values = current[7:].split(',')
            if values and all(v in ('1','2','3','4','5') for v in values):
                self.fields['bedrooms'].choices.append((current, ' یا '.join(v.translate(str.maketrans('12345','۱۲۳۴۵')) for v in values) + ' خواب'))
